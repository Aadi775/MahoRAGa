import argparse
import logging
import os
import threading
import time
from collections import deque
from json import dumps

from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from fastmcp import FastMCP
from .tools import register_tools


LOGGER = logging.getLogger(__name__)

mcp = FastMCP("knowledge-graph")

register_tools(mcp)


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        LOGGER.warning("Invalid %s=%r; using default=%d", name, raw, default)
        return default


DEFAULT_MAX_HTTP_BODY_BYTES = _env_int("MAHORAGA_MAX_HTTP_BODY_BYTES", 1048576)
DEFAULT_RATE_LIMIT_REQUESTS = _env_int("MAHORAGA_RATE_LIMIT_REQUESTS", 60)
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = _env_int("MAHORAGA_RATE_LIMIT_WINDOW_SECONDS", 60)


async def _send_json(scope, send, status_code: int, payload: dict) -> None:
    body = dumps(payload).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class BodySizeLimitMiddleware:
    def __init__(self, app, max_body_bytes: int = DEFAULT_MAX_HTTP_BODY_BYTES):
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin1").lower(): value.decode("latin1")
            for key, value in scope.get("headers", [])
        }
        content_length = headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_body_bytes:
                    await _send_json(
                        scope,
                        send,
                        413,
                        {
                            "error": "request body too large",
                            "max_bytes": self.max_body_bytes,
                        },
                    )
                    return
            except ValueError:
                await _send_json(scope, send, 400, {"error": "invalid content-length header"})
                return

        total = 0
        chunks = []
        while True:
            message = await receive()
            if message["type"] != "http.request":
                continue
            body = message.get("body", b"")
            total += len(body)
            if total > self.max_body_bytes:
                await _send_json(
                    scope,
                    send,
                    413,
                    {
                        "error": "request body too large",
                        "max_bytes": self.max_body_bytes,
                    },
                )
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break

        buffered_body = b"".join(chunks)
        sent = False

        async def replay_receive():
            nonlocal sent
            if sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            sent = True
            return {"type": "http.request", "body": buffered_body, "more_body": False}

        await self.app(scope, replay_receive, send)


class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        max_requests: int = DEFAULT_RATE_LIMIT_REQUESTS,
        window_seconds: int = DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
    ):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._request_times: dict[str, deque[float]] = {}

    async def dispatch(self, request: Request, call_next):
        client_host = request.client.host if request.client else "unknown"
        now = time.monotonic()

        with self._lock:
            history = self._request_times.setdefault(client_host, deque())
            cutoff = now - self.window_seconds
            while history and history[0] <= cutoff:
                history.popleft()

            if len(history) >= self.max_requests:
                return JSONResponse(
                    {
                        "error": "rate limit exceeded",
                        "limit": self.max_requests,
                        "window_seconds": self.window_seconds,
                    },
                    status_code=429,
                )

            history.append(now)

        return await call_next(request)


class ErrorSanitizationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            LOGGER.exception("Unhandled HTTP transport error")
            return JSONResponse({"error": "internal server error"}, status_code=500)


def _http_middleware() -> list[Middleware]:
    return [
        Middleware(ErrorSanitizationMiddleware),
        Middleware(SimpleRateLimitMiddleware),
        Middleware(BodySizeLimitMiddleware),
    ]


def main() -> None:
    """Entry point for the MCP server CLI.

    Supports multiple transports:
      - stdio   (default) : one client per process (classic MCP)
      - sse              : shared HTTP server, multiple clients can connect
      - streamable-http  : modern bidirectional HTTP (recommended for multi-client)

    Usage:
      mahoraga-kg                          # stdio (default)
      mahoraga-kg --transport sse          # SSE on port 8000
      mahoraga-kg --transport sse --port 8080
    """
    parser = argparse.ArgumentParser(
        prog="mahoraga-kg",
        description="MahoRAGa Knowledge-Graph MCP Server",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport protocol (default: stdio). Use 'sse' or 'streamable-http' to run a shared server that multiple clients can connect to simultaneously.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind the HTTP server to (default: 127.0.0.1). Only used with sse/streamable-http.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for the HTTP server (default: 8000). Only used with sse/streamable-http.",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(
            transport=args.transport,
            host=args.host,
            port=args.port,
            middleware=_http_middleware(),
        )


if __name__ == "__main__":
    main()
