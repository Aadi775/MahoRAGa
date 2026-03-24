import argparse

from fastmcp import FastMCP
from .tools import register_tools

mcp = FastMCP("knowledge-graph")

register_tools(mcp)


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
        default="0.0.0.0",
        help="Host to bind the HTTP server to (default: 0.0.0.0). Only used with sse/streamable-http.",
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
        mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
