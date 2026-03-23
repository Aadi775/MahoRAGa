from fastmcp import FastMCP
from .tools import register_tools
from .embeddings import warmup

mcp = FastMCP("knowledge-graph")

register_tools(mcp)

warmup()


if __name__ == "__main__":
    mcp.run()
