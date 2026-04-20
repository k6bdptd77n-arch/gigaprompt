#!/bin/bash
# Super Memory Hook — Auto-capture for ANY AI agent
# =================================================
# Add to .bashrc: source ~/.super_memory/hook.sh

# Configuration
MEMORY_API="${SUPER_MEMORY_API:-http://127.0.0.1:8080}"
ENABLE_HOOK="${SUPER_MEMORY_ENABLE:-1}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Thin passthrough — delegates all subcommands to the Python CLI
mem() {
    python3 -m mem "$@"
}

# Check if memory agent is running (used by auto-capture hooks below)
check_agent() {
    curl -s --max-time 1 "$MEMORY_API/health" > /dev/null 2>&1
}

# Send one entry to the REST API (used by git_complete_hook)
memory_add() {
    local text="$1"
    local type="${2:-general}"
    [ "$ENABLE_HOOK" = "1" ] || return
    check_agent || return
    curl -s -X POST "$MEMORY_API/add" \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"$text\", \"type\": \"$type\", \"source\": \"hook\"}" > /dev/null 2>&1
}

# Auto-capture git commits and successful build commands
git_complete_hook() {
    local exit_code=$?
    local last_cmd
    last_cmd=$(history | tail -1 | sed 's/^[0-9]* *//')

    if [[ "$last_cmd" =~ ^git\ commit ]]; then
        memory_add "Git: $last_cmd" "general"
    fi

    if [ $exit_code -eq 0 ] && [[ "$last_cmd" =~ ^(make|npm\ |pip\ |cargo\ ) ]]; then
        memory_add "Build: $last_cmd" "general"
    fi

    return $exit_code
}

# Bash completion for mem subcommands
_mem_completions() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local prev="${COMP_WORDS[COMP_CWORD-1]}"
    if [[ "$prev" == "mem" ]]; then
        COMPREPLY=($(compgen -W "add done decision blocked search recent summary context daemon agent file project" -- "$cur"))
    fi
}
complete -F _mem_completions mem

if [ "$ENABLE_HOOK" = "1" ]; then
    PROMPT_COMMAND="${PROMPT_COMMAND:+$PROMPT_COMMAND; }git_complete_hook"
fi

echo -e "${BLUE}Super Memory hook loaded${NC} — run 'mem help' for commands"
