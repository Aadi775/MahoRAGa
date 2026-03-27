import sys
import importlib

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from src import main


def test_http_transport_defaults_to_localhost(monkeypatch):
    captured = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs

    monkeypatch.setattr(main.mcp, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["mahoraga-kg", "--transport", "sse"])

    main.main()

    assert captured["kwargs"]["host"] == "127.0.0.1"
    assert captured["kwargs"]["port"] == 8000
    assert captured["kwargs"]["transport"] == "sse"
    assert "middleware" in captured["kwargs"]


def test_body_size_limit_middleware_rejects_oversized_body():
    async def ok(_request):
        return JSONResponse({"ok": True})

    app = Starlette(
        routes=[Route("/", ok, methods=["POST"])],
        middleware=[Middleware(main.BodySizeLimitMiddleware, max_body_bytes=8)],
    )
    client = TestClient(app)

    response = client.post("/", content=b"123456789")
    assert response.status_code == 413
    payload = response.json()
    assert payload["error"] == "request body too large"


def test_body_size_limit_middleware_preserves_body_for_handler():
    async def echo_length(request):
        body = await request.body()
        return JSONResponse({"length": len(body)})

    app = Starlette(
        routes=[Route("/", echo_length, methods=["POST"])],
        middleware=[Middleware(main.BodySizeLimitMiddleware, max_body_bytes=32)],
    )
    client = TestClient(app)

    response = client.post("/", content=b"12345678")
    assert response.status_code == 200
    assert response.json() == {"length": 8}


def test_simple_rate_limit_middleware_limits_by_client():
    async def ok(_request):
        return JSONResponse({"ok": True})

    app = Starlette(
        routes=[Route("/", ok, methods=["GET"])],
        middleware=[Middleware(main.SimpleRateLimitMiddleware, max_requests=2, window_seconds=60)],
    )
    client = TestClient(app)

    assert client.get("/").status_code == 200
    assert client.get("/").status_code == 200
    third = client.get("/")
    assert third.status_code == 429
    assert third.json()["error"] == "rate limit exceeded"


def test_error_sanitization_middleware_masks_internal_errors():
    async def boom(_request):
        raise RuntimeError("secret internals")

    app = Starlette(
        routes=[Route("/", boom, methods=["GET"])],
        middleware=[Middleware(main.ErrorSanitizationMiddleware)],
    )
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/")
    assert response.status_code == 500
    assert response.json() == {"error": "internal server error"}


def test_invalid_env_values_fallback_to_defaults(monkeypatch):
    monkeypatch.setenv("MAHORAGA_MAX_HTTP_BODY_BYTES", "bad")
    monkeypatch.setenv("MAHORAGA_RATE_LIMIT_REQUESTS", "nope")
    monkeypatch.setenv("MAHORAGA_RATE_LIMIT_WINDOW_SECONDS", "-5")

    reloaded = importlib.reload(main)

    assert reloaded.DEFAULT_MAX_HTTP_BODY_BYTES == 1048576
    assert reloaded.DEFAULT_RATE_LIMIT_REQUESTS == 60
    assert reloaded.DEFAULT_RATE_LIMIT_WINDOW_SECONDS == 1
