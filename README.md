# Super Memory — Universal AI Memory

**Memory that works with ANY AI agent. Installs in 30 seconds.**

```
Claude Code ✓    OpenClaw ✓    Codex ✓    Cursor ✓    Any AI Agent ✓
```

---

## ⚡ Quick Start

```bash
# One command install:
curl -fsSL https://raw.githubusercontent.com/YOUR_REPO/super-memory/main/install.sh | bash

# Or manual:
git clone https://github.com/YOUR_REPO/super-memory.git ~/.super_memory
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
GET  /health       — Check status
GET  /summary      — Memory stats
GET  /recent       — Recent entries
GET  /search?q=    — Search
GET  /context      — AI context (for prompts)
POST /add          — Add entry
POST /add_completed — Mark task done
POST /add_decision  — Add decision
POST /add_blocker  — Add blocker
```

### CLI Commands
```bash
mem add "text"           # Add entry
mem done "task"          # Mark completed
mem decision "topic"     # Add decision
mem blocked "task"       # Add blocker
mem search "query"       # Search
mem recent               # Recent entries
mem summary              # Stats
mem context              # AI context
mem status               # Check agent
mem start                # Start agent
mem stop                 # Stop agent
mem install              # Install + auto-start
```

### Auto-Start
- **systemd** service (Linux)
- **Background process** (fallback)
- Starts automatically on boot

### Works With Everything
```bash
# Claude Code
cat file.py | mem context

# OpenClaw
mem context | openai -p "review this"

# Any AI
curl http://localhost:8080/context
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
```

### AI Integration
```bash
# Get context for Claude Code
mem context > /tmp/memory.txt
cat /tmp/memory.txt code.py | claude

# Or in prompt
claude "Review $(mem context) code.py"
```

### In Scripts
```bash
#!/bin/bash
# Post-deploy hook
mem done "Deployed v1.2.3"

#!/bin/bash
# Git commit hook
mem add "Git: $(git log -1 --oneline)"
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
├── memory_agent.py    # REST API daemon
├── mem                # CLI tool
├── launcher.py        # Auto-start manager
├── hook.sh           # Bash hook (optional)
├── context_inject.py # Prompt injector
├── daemon/
│   └── super-memory.service  # systemd unit
└── memory.db          # SQLite database
```

---

## 🔧 Configuration

### Environment Variables
```bash
SUPER_MEMORY_API=http://127.0.0.1:8080  # API URL
SUPER_MEMORY_ENABLE=1                      # Enable hook
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
