# Super Memory — Universal AI Memory

**Memory that works with ANY AI agent.**

```
Claude Code ✓    OpenClaw ✓    Codex ✓    Cursor ✓    Any CLI ✓
```

---

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_REPO/super-memory/main/install.sh | bash
```

Or manual:

```bash
git clone https://github.com/YOUR_REPO/super-memory.git ~/.super_memory
echo 'source ~/.super_memory/hook.sh' >> ~/.bashrc
source ~/.bashrc
mem agent
```

---

## What You Get

### 1. Memory Agent (Background Service)
REST API that stores memory and works with ANY AI agent.

```bash
mem agent  # Start the service
```

Endpoints:
- `GET /health` — Health check
- `GET /summary` — Memory stats
- `GET /recent` — Recent entries
- `GET /search?q=query` — Search
- `GET /context` — AI context for prompts
- `POST /add` — Add entry
- `POST /add_completed` — Mark task done
- `POST /add_decision` — Add decision
- `POST /add_blocker` — Add blocker

### 2. Shell Hook (Auto-Capture)
Automatically captures git commits, builds, etc.

Add to `.bashrc`:
```bash
source ~/.super_memory/hook.sh
```

### 3. Context Injector (For AI Prompts)
Inject memory context into ANY AI prompt.

```bash
# Pipe to Claude Code
cat file.py | context_inject.py --prefix "Review this code"

# Or with OpenClaw
openclaw "Explain $(cat code.py | context_inject.py --stdin)"

# With search
context_inject.py --prompt "Help me with auth"
```

---

## Usage

### Commands

```bash
mem add "Did something"       # Add entry
mem done "Task completed"      # Mark done
mem decision "Chose Postgres"   # Add decision
mem blocked "Waiting for API"  # Add blocker
mem search "auth"              # Search
mem recent                     # Recent entries
mem summary                    # Stats
mem context                    # AI context
mem agent                      # Start/stop agent
mem status                     # Check status
```

### API Usage

```bash
# Add to memory
curl -X POST http://127.0.0.1:8080/add \
  -H "Content-Type: application/json" \
  -d '{"text": "Task completed", "type": "completed"}'

# Get AI context
curl http://127.0.0.1:8080/context

# Search
curl "http://127.0.0.1:8080/search?q=auth"
```

### Integration Examples

#### Claude Code
```bash
# In .claude/commands/memory.js
const { execSync } = require('child_process');
const context = execSync('curl -s http://127.0.0.1:8080/context').toString();
console.log(context);
```

#### OpenClaw
```bash
# In system prompt or skill
curl -s http://127.0.0.1:8080/context
```

#### Any AI Agent
```bash
# Pre-prompt hook
export AI_PROMPT_PREFIX="$(curl -s http://127.0.0.1:8080/context)"
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                                                             │
│   AI Agent 1     AI Agent 2     AI Agent 3     AI Agent N  │
│        │              │              │              │       │
│        └──────────────┴──────────────┴──────────────┘       │
│                           │                                  │
│                    Memory Service                             │
│                    (localhost:8080)                           │
│                    SQLite + FTS5                            │
│                                                             │
└─────────────────────────────────────────────────────────┘
```

---

## Files

```
~/.super_memory/
├── memory_agent.py      # REST API daemon
├── hook.sh              # Shell hook for auto-capture
├── context_inject.py    # CLI tool for context injection
├── install.sh           # One-command installer
└── memory.db            # SQLite database
```

---

## Requirements

- Python 3.6+
- curl (for API)
- bash/zsh

---

## License

MIT

---

**One install. Works with everything.**
