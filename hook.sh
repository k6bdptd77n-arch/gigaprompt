#!/bin/bash
# Super Memory Hook — Auto-capture for ANY AI agent
# =================================================
# Add to .bashrc: source ~/.super_memory/hook.sh
#
# Features:
# - Auto-captures git commits
# - Auto-captures command completions
# - Context injection for AI prompts
# - Works with ANY AI agent

# Configuration
MEMORY_API="${SUPER_MEMORY_API:-http://127.0.0.1:8080}"
ENABLE_HOOK="${SUPER_MEMORY_ENABLE:-1}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if memory agent is running
check_agent() {
    if curl -s --max-time 1 "$MEMORY_API/health" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Send to memory API
memory_add() {
    local text="$1"
    local type="${2:-general}"
    
    if [ "$ENABLE_HOOK" != "1" ]; then
        return
    fi
    
    if ! check_agent; then
        return
    fi
    
    curl -s -X POST "$MEMORY_API/add" \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"$text\", \"type\": \"$type\", \"source\": \"hook\"}" > /dev/null 2>&1
}

# Memory command shortcuts
mem() {
    local cmd="${1:-help}"
    
    case "$cmd" in
        help|--help)
            echo ""
            echo "Super Memory — Memory commands"
            echo ""
            echo "  mem                    — This help"
            echo "  mem add <text>        — Add entry"
            echo "  mem done <task>       — Mark task completed"
            echo "  mem decision <topic>  — Add decision"
            echo "  mem blocked <task>     — Add blocker"
            echo "  mem search <query>    — Search"
            echo "  mem recent            — Show recent"
            echo "  mem summary           — Summary"
            echo "  mem context           — Show context for AI"
            echo ""
            echo "  mem agent             — Start memory agent"
            echo "  mem status           — Check agent status"
            echo ""
            ;;
        add)
            shift
            memory_add "$*"
            echo -e "${GREEN}✅ Added to memory${NC}"
            ;;
        done|completed)
            shift
            curl -s -X POST "$MEMERY_API/add_completed" \
                -H "Content-Type: application/json" \
                -d "{\"task\": \"$*\"}" > /dev/null 2>&1
            echo -e "${GREEN}✅ Completed: $*${NC}"
            ;;
        decision)
            shift
            curl -s -X POST "$MEMORY_API/add_decision" \
                -H "Content-Type: application/json" \
                -d "{\"topic\": \"$*\"}" > /dev/null 2>&1
            echo -e "${GREEN}⚖️ Decision added: $*${NC}"
            ;;
        blocked)
            shift
            curl -s -X POST "$MEMORY_API/add_blocker" \
                -H "Content-Type: application/json" \
                -d "{\"task\": \"$*\", \"blocker\": \"unknown\", \"needed\": \"TBD\"}" > /dev/null 2>&1
            echo -e "${YELLOW}🚧 Blocker added: $*${NC}"
            ;;
        search)
            shift
            curl -s "$MEMORY_API/search?q=$*" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('results'):
    for r in data['results'][:5]:
        print(f\"  [{r['type']}] {r['text'][:80]}...\")
else:
    print('  No results found.')
"
            ;;
        recent)
            curl -s "$MEMORY_API/recent" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('memories'):
    for r in data['memories'][:10]:
        print(f\"  [{r['type']}] {r['text'][:80]}...\")
"
            ;;
        summary)
            curl -s "$MEMORY_API/summary" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('')
print('📊 Memory Summary:')
print(f\"  Total: {data.get('total', 0)}\")
print(f\"  ✅ Completed: {data.get('completed', 0)}\")
print(f\"  ⚖️ Decisions: {data.get('decisions', 0)}\")
print(f\"  🚧 Blockers: {data.get('blockers', 0)}\")
print('')
"
            ;;
        context)
            curl -s "$MEMORY_API/context" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('context', 'No context available'))
"
            ;;
        agent)
            if check_agent; then
                echo -e "${YELLOW}Memory agent already running${NC}"
            else
                echo "Starting memory agent..."
                python3 ~/.super_memory/memory_agent.py &
                sleep 1
                echo -e "${GREEN}Memory agent started on http://127.0.0.1:8080${NC}"
            fi
            ;;
        status)
            if check_agent; then
                echo -e "${GREEN}✅ Memory agent running${NC}"
                curl -s "$MEMORY_API/summary" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"   Total: {data.get('total', 0)} entries\")
"
            else
                echo -e "${RED}❌ Memory agent not running${NC}"
                echo "   Run: mem agent"
            fi
            ;;
        *)
            echo -e "${RED}Unknown command: $cmd${NC}"
            echo "   Run: mem help"
            ;;
    esac
}

# Auto-complete for mem command
_mem_completions() {
    local cur prev
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    
    case "$prev" in
        mem)
            COMPREPLY=($(compgen -W "add done decision blocked search recent summary context agent status" -- "$cur"))
            ;;
    esac
    
    return 0
}

complete -F _mem_completions mem

# Git auto-capture
git_complete_hook() {
    local exit_code=$?
    local last_cmd=$(history | tail -1 | sed 's/^[0-9]* *//')
    
    # Auto-save git commits
    if [[ "$last_cmd" =~ ^git\ (commit|push|pull|merge|checkout\ -b) ]]; then
        if [[ "$last_cmd" =~ "commit" ]]; then
            memory_add "Git: $last_cmd" "general"
        fi
    fi
    
    # Auto-save completed commands
    if [ $exit_code -eq 0 ] && [[ "$last_cmd" =~ ^(make|npm\ |pip\ |cargo\ ) ]]; then
        memory_add "Build: $last_cmd" "general"
    fi
    
    return $exit_code
}

# Only enable if PROMPT_COMMAND exists and hook is enabled
if [ "$ENABLE_HOOK" = "1" ]; then
    # Add to prompt
    PROMPT_COMMAND="${PROMPT_COMMAND:+$PROMPT_COMMAND; }git_complete_hook"
fi

echo -e "${BLUE}Super Memory hook loaded${NC} (mem agent to start, mem help for commands)"
