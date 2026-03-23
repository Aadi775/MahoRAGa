from fastmcp import FastMCP
from .tools import register_tools

mcp = FastMCP("knowledge-graph")

register_tools(mcp)


def main() -> None:
    """Entry point for the MCP server CLI."""
    mcp.run()


if __name__ == "__main__":
    main()
