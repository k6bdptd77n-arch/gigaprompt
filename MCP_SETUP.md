# Super Memory — MCP Integration Guide

## Quick Start

### 1. Install Dependencies

```bash
# Install Super Memory if not already installed
curl -fsSL https://raw.githubusercontent.com/k6bdptd77n-arch/gigaprompt/main/install.sh | bash

# Install MCP
pip install mcp
```

### 2. Configure Claude Code MCP

Add to your Claude Code settings (`~/.claude/settings.json` or project `.claude/settings.json`):

```json
{
  "mcpServers": {
    "super-memory": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "env": {
        "PYTHONPATH": "~/.super_memory/src"
      }
    }
  }
}
```

Or if using the CLI wrapper:

```json
{
  "mcpServers": {
    "super-memory": {
      "command": "/path/to/mem",
      "args": ["mcp"]
    }
  }
}
```

### 3. Start the Memory Daemon

```bash
# In a separate terminal
python memory_agent.py &
```

### 4. Restart Claude Code

After configuring MCP, restart Claude Code. The memory tools will be available automatically.

---

## Available Tools

When connected, you can use these tools in conversations:

| Tool | Description | Example |
|------|-------------|---------|
| `memory_search` | Search memories | "Search for: authentication" |
| `memory_add` | Add general entry | "Mem: learned about Python decorators" |
| `memory_done` | Mark task completed | "Done: implemented login" |
| `memory_decision` | Record decision | "Decision: use JWT for auth" |
| `memory_blocked` | Add blocker | "Blocked: waiting for API keys" |
| `memory_context` | Get AI context | Returns recent tasks/decisions |
| `memory_summary` | Get stats | Returns total/completed/decisions |
| `memory_recent` | Recent entries | Get last 10 entries |

---

## Usage Examples

### In Claude Code Conversation

```
You: I need to add authentication to the API
Claude: [calls memory_blocked] Blocked: authentication - waiting for API keys

You: What was I working on?
Claude: [calls memory_context] Returns recent tasks and decisions

You: I finished the user model
Claude: [calls memory_done] Task completed: user model
```

### Manual Commands

```bash
# Check memory status
mem summary

# Add entry
mem add "Note: Python 3.11 has faster dict iteration"

# Mark task done
mem done "Implemented user authentication"

# Record decision
mem decision "Use bcrypt for passwords" --reason "Industry standard, secure"

# Search
mem search "authentication"
```

---

## Troubleshooting

### MCP not connecting?

1. Ensure daemon is running: `curl http://localhost:8080/health`
2. Start daemon: `python memory_agent.py &`
3. Check Python path for MCP server

### Tools not appearing?

Restart Claude Code after adding MCP configuration.

### Daemon not running?

```bash
python memory_agent.py --port 8080 &
```

---

## Architecture

```
┌─────────────────┐     MCP      ┌──────────────────┐
│ Claude Code     │ ◄──────────► │ memory-mcp       │
│ Cursor          │  tools:      │ (src/mcp_server) │
└─────────────────┘  - search    └────────┬─────────┘
                 - add                      │
                 - context                  ▼
                                          ┌──────────────────┐
                                          │ localhost:8080    │
                                          │ memory_agent.py   │
                                          │ SQLite DB         │
                                          └──────────────────┘
```
