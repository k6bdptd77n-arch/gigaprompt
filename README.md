# Super Memory — Universal AI Memory

**Memory that works with ANY AI agent. Installs in 30 seconds.**

```
Claude Code ✓    OpenClaw ✓    Codex ✓    Cursor ✓    Any AI Agent ✓
```

---

## ⚡ Quick Start

```bash
# One command install:
curl -fsSL https://raw.githubusercontent.com/k6bdptd77n-arch/gigaprompt/main/install.sh | bash

# Or manual:
git clone https://github.com/k6bdptd77n-arch/gigaprompt.git ~/.super_memory
cd ~/.super_memory && python3 mem install

# Start using:
mem add "First entry"
mem status
```

---

## 🚀 Features

### Universal Memory API
REST API that any AI agent can query:
```
GET  /health              — Check status
GET  /summary             — Memory stats
GET  /recent              — Recent entries
GET  /search?q=           — Search
GET  /context             — AI context (for prompts)
GET  /tokens/summary     — Token usage summary
GET  /tokens/daily        — Daily cost breakdown
GET  /tokens/recent       — Recent token log entries
POST /add                 — Add entry
POST /add_completed       — Mark task done
POST /add_decision        — Add decision
POST /add_blocker         — Add blocker
POST /log_tokens          — Log token usage
```

### CLI Commands
```bash
# Memory operations (top-level, intuitive)
mem add "text"           # Add entry
mem done "task"          # Mark completed
mem decision "topic"     # Add decision
mem blocked "task"       # Add blocker
mem search "query"       # Search
mem recent               # Recent entries
mem summary              # Stats
mem context              # AI context
mem tokens               # Token usage summary

# Daemon management
mem daemon start         # Start daemon
mem daemon stop          # Stop daemon
mem daemon status        # Check status
mem init                 # Initialize (first time)

# Shell completion
mem completion bash      # Install bash completion
```

### Auto-Start
- **systemd** service (Linux)
- **Background process** (fallback)
- Starts automatically on boot

### Desktop Monitor (Optional)
Web-based dashboard with PTY terminal:
```bash
cd desktop_monitor
pip install -r requirements.txt
python app.py
# Opens http://127.0.0.1:5000
```

### Token Tracking
Track Claude API usage and costs:
```bash
# Log tokens manually
curl -X POST http://localhost:8080/log_tokens \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-opus-4-6","usage":{"input_tokens":1000,"output_tokens":500}}'

# Or use the wrapper
SUPER_MEMORY_API=http://127.0.0.1:8080 python token_log.py curl ...
```

---

## 📦 Installation

### Option 1: One Command
```bash
curl -fsSL https://.../install.sh | bash
```

### Option 2: Manual
```bash
git clone https://... ~/.super_memory
cd ~/.super_memory
python3 mem install
```

### Option 3: CLI Only (no agent)
```bash
# Just the CLI, use existing agent
cp mem ~/bin/  # or ~/.local/bin/
```

---

## 🎯 Usage Examples

### Daily Workflow
```bash
# Start of day
mem context          # What was I working on?

# After completing task
mem done "Added auth endpoint"

# Decision made
mem decision "Use JWT" --reason "Stateless, scalable"

# Blocked
mem blocked "Deploy" --blocker "Waiting for CI"

# End of day
mem summary          # What did I accomplish?
mem tokens           # How much did I spend?
```

### AI Integration
```bash
# Get context for Claude Code
mem context > /tmp/memory.txt
cat /tmp/memory.txt code.py | claude

# Or in prompt
claude "Review $(mem context) code.py"
```

### Token Tracking in Scripts
```bash
#!/bin/bash
# Post-api-call hook
python token_log.py curl -X POST https://api.anthropic.com/... \
  -H "x-api-key: $ANTHROPIC_API_KEY" ...
```

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                                                             │
│   Claude Code     OpenClaw      Codex        Any Agent    │
│        │              │           │              │          │
│        └──────────────┴───────────┴──────────────┘        │
│                           │                               │
│                    Memory Service                          │
│                    (localhost:8080)                       │
│                    SQLite + FTS5                          │
│                                                             │
└─────────────────────────────────────────────────────────┘
```

### Files
```
~/.super_memory/
├── memory_agent.py     # REST API daemon
├── mem                 # CLI tool
├── token_log.py        # Token usage logger
├── hook.sh            # Bash hook (optional)
├── context_inject.py  # Prompt injector
├── launcher.py        # Auto-start manager
├── desktop_monitor/   # Web dashboard (optional)
│   ├── app.py         # Flask + WebSocket PTY
│   └── templates/     # HTML templates
├── daemon/
│   └── super-memory.service  # systemd unit
└── memory.db          # SQLite database
```

---

## 🔧 Configuration

### Environment Variables
```bash
SUPER_MEMORY_API=http://127.0.0.1:8080  # API URL
```

### Port
Default: `8080`

To change:
```bash
python3 memory_agent.py --port 9090
```

---

## 🐛 Troubleshooting

### Agent not running?
```bash
mem start
```

### Check status:
```bash
mem status
```

### View logs:
```bash
cat ~/.super_memory/agent.log
```

### Restart:
```bash
mem stop && mem start
```

---

## 📊 Stats

| Metric | Value |
|--------|-------|
| Install time | ~30 seconds |
| Memory per entry | ~1KB |
| Search speed | <10ms (FTS5) |
| Agents supported | Unlimited |

---

## 🤝 Contributing

1. Fork
2. Add feature
3. Test: `python3 mem status && python3 mem add "test"`
4. PR

---

## 📝 License

MIT

---

**One install. Works with everything. Remembers everything.**