#!/usr/bin/env python3
"""
Super Memory MCP Server
======================
MCP (Model Context Protocol) server for AI agents.
Exposes memory tools to Claude Code, Cursor, and other MCP-aware AI.

Usage:
    python memory_agent.py &    # Start daemon
    python -m mem.mcp_server   # Start MCP server
"""
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp.server import FastMCP
import mem.api as api


# Create MCP server
mcp = FastMCP("super-memory")


def tool_response(tool_name: str, result: dict) -> str:
    """Convert API result to MCP response string. ASCII-safe."""
    if "error" in result:
        return f"Error: {result['error']}"

    if tool_name == "memory_search":
        results = result.get("results", [])
        if not results:
            return "No results found."
        return "\n".join([
            f"[{r.get('type', '?')}] {r.get('text', '')[:100]}"
            for r in results[:10]
        ])

    elif tool_name == "memory_context":
        return result.get("context", "No context available.")

    elif tool_name == "memory_summary":
        return (
            f"Total: {result.get('total', 0)}\n"
            f"Completed: {result.get('completed', 0)}\n"
            f"Decisions: {result.get('decisions', 0)}\n"
            f"Blockers: {result.get('blockers', 0)}"
        )

    elif tool_name == "memory_recent":
        memories = result.get("memories", [])
        if not memories:
            return "No entries yet."
        return "\n".join([
            f"[{m.get('type', '?')}] {m.get('text', '')[:100]}"
            for m in memories[:10]
        ])

    elif tool_name in ("memory_add", "memory_done", "memory_decision", "memory_blocked"):
        return "Success"

    return str(result)


@mcp.tool()
def memory_search(query: str) -> str:
    """Search memory entries by query."""
    if not api.is_agent_running():
        return "Error: Super Memory daemon is not running. Start with: mem daemon start"
    result = api.api_get(f"/search?q={query}")
    return tool_response("memory_search", result)


@mcp.tool()
def memory_add(text: str) -> str:
    """Add a general entry to memory."""
    if not api.is_agent_running():
        return "Error: Super Memory daemon is not running. Start with: mem daemon start"
    result = api.api_post("/add", {"text": text, "type": "general", "source": "mcp"})
    return tool_response("memory_add", result)


@mcp.tool()
def memory_done(task: str) -> str:
    """Mark a task as completed."""
    if not api.is_agent_running():
        return "Error: Super Memory daemon is not running. Start with: mem daemon start"
    result = api.api_post("/add_completed", {"task": task, "source": "mcp"})
    return tool_response("memory_done", result)


@mcp.tool()
def memory_decision(topic: str, reason: str = "") -> str:
    """Record a decision made."""
    if not api.is_agent_running():
        return "Error: Super Memory daemon is not running. Start with: mem daemon start"
    result = api.api_post("/add_decision", {
        "topic": topic,
        "reason": reason,
        "source": "mcp"
    })
    return tool_response("memory_decision", result)


@mcp.tool()
def memory_blocked(task: str, blocker: str = "unknown", needed: str = "TBD") -> str:
    """Add a blocker."""
    if not api.is_agent_running():
        return "Error: Super Memory daemon is not running. Start with: mem daemon start"
    result = api.api_post("/add_blocker", {
        "task": task,
        "blocker": blocker,
        "needed": needed,
        "source": "mcp"
    })
    return tool_response("memory_blocked", result)


@mcp.tool()
def memory_context() -> str:
    """Get AI context (recent completed, decisions, blockers)."""
    if not api.is_agent_running():
        return "Error: Super Memory daemon is not running. Start with: mem daemon start"
    result = api.api_get("/context")
    return tool_response("memory_context", result)


@mcp.tool()
def memory_summary() -> str:
    """Get memory statistics."""
    if not api.is_agent_running():
        return "Error: Super Memory daemon is not running. Start with: mem daemon start"
    result = api.api_get("/summary")
    return tool_response("memory_summary", result)


@mcp.tool()
def memory_recent(limit: int = 10) -> str:
    """Get recent memory entries."""
    if not api.is_agent_running():
        return "Error: Super Memory daemon is not running. Start with: mem daemon start"
    result = api.api_get(f"/recent?limit={limit}")
    return tool_response("memory_recent", result)


def run_mcp():
    """Run the MCP server on stdio (for Claude Code integration)."""
    print("Super Memory MCP Server starting...", file=sys.stderr)
    print("Tools: memory_search, memory_add, memory_done, memory_decision, memory_blocked, memory_context, memory_summary, memory_recent", file=sys.stderr)
    mcp.run()


if __name__ == "__main__":
    run_mcp()
