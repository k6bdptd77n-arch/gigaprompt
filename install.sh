#!/bin/bash
# Super Memory — Universal AI Memory
# =====================================
# One-command install for universal memory that works with ANY AI agent
#
# Usage:
#   curl -fsSL https://.../install.sh | bash
#
# After install, works with:
#   - Claude Code
#   - OpenAI Codex
#   - OpenClaw
#   - Cursor
#   - Any CLI agent

set -e

# Configuration
INSTALL_DIR="${HOME}/.super_memory"
REPO_URL="${REPO_URL:-https://github.com/YOUR_REPO/super-memory}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Super Memory — Universal AI Memory Agent    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""

# Check prerequisites
check_prereqs() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"
    
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python3 is required${NC}"
        exit 1
    fi
    echo "  ✅ Python3: $(python3 --version | cut -d' ' -f2)"
    
    if ! command -v curl &> /dev/null; then
        echo -e "${RED}❌ curl is required${NC}"
        exit 1
    fi
    echo "  ✅ curl"
}

# Create installation directory
create_dir() {
    echo -e "${YELLOW}Creating installation directory...${NC}"
    mkdir -p "$INSTALL_DIR"
    echo "  ✅ $INSTALL_DIR"
}

# Install Python dependencies
install_deps() {
    echo -e "${YELLOW}Installing dependencies...${NC}"
    
    # requests is usually built-in, but just in case
    python3 -c "import requests" 2>/dev/null || \
        pip3 install requests --quiet 2>/dev/null || \
        python3 -m pip install requests --quiet 2>/dev/null
    
    echo "  ✅ requests (Python)"
}

# Install files
install_files() {
    echo -e "${YELLOW}Installing files...${NC}"
    
    # Copy files
    if [ -f "$(dirname $0)/memory_agent.py" ]; then
        cp "$(dirname $0)/memory_agent.py" "$INSTALL_DIR/"
        echo "  ✅ memory_agent.py"
    fi
    
    if [ -f "$(dirname $0)/hook.sh" ]; then
        cp "$(dirname $0)/hook.sh" "$INSTALL_DIR/"
        echo "  ✅ hook.sh"
    fi
    
    if [ -f "$(dirname $0)/context_inject.py" ]; then
        cp "$(dirname $0)/context_inject.py" "$INSTALL_DIR/"
        echo "  ✅ context_inject.py"
    fi
    
    # Make executable
    chmod +x "$INSTALL_DIR/memory_agent.py"
    chmod +x "$INSTALL_DIR/context_inject.py"
}

# Configure bashrc
configure_bashrc() {
    echo -e "${YELLOW}Configuring shell...${NC}"
    
    HOOK_LINE="[ -f ${INSTALL_DIR}/hook.sh ] && source ${INSTALL_DIR}/hook.sh"
    
    # Check if already configured
    if grep -q "super_memory/hook.sh" ~/.bashrc 2>/dev/null; then
        echo "  ✅ Already configured in ~/.bashrc"
    else
        echo "" >> ~/.bashrc
        echo "# Super Memory — Universal AI Memory" >> ~/.bashrc
        echo "$HOOK_LINE" >> ~/.bashrc
        echo "  ✅ Added to ~/.bashrc"
    fi
    
    # Add alias for quick access
    ALIAS_LINE="alias mem='source ${INSTALL_DIR}/hook.sh && mem'"
    
    if grep -q "alias mem=" ~/.bashrc 2>/dev/null; then
        echo "  ✅ Alias already configured"
    else
        echo "$ALIAS_LINE" >> ~/.bashrc
        echo "  ✅ Added alias: mem"
    fi
}

# Start memory agent
start_agent() {
    echo -e "${YELLOW}Starting memory agent...${NC}"
    
    # Check if already running
    if curl -s --max-time 1 http://127.0.0.1:8080/health > /dev/null 2>&1; then
        echo "  ⚠️  Memory agent already running"
    else
        # Start in background
        nohup python3 "$INSTALL_DIR/memory_agent.py" > "$INSTALL_DIR/agent.log" 2>&1 &
        sleep 2
        
        # Verify
        if curl -s --max-time 2 http://127.0.0.1:8080/health > /dev/null 2>&1; then
            echo "  ✅ Memory agent started on http://127.0.0.1:8080"
        else
            echo "  ⚠️  Could not verify agent (check: cat $INSTALL_DIR/agent.log)"
        fi
    fi
}

# Verify installation
verify() {
    echo ""
    echo -e "${YELLOW}Verifying installation...${NC}"
    
    # Check files
    echo "  📁 Files:"
    ls -la "$INSTALL_DIR/"*.py "$INSTALL_DIR/"*.sh 2>/dev/null | wc -l | xargs -I{} echo "     {} files installed"
    
    # Check API
    echo "  🌐 API:"
    if curl -s --max-time 2 http://127.0.0.1:8080/health > /dev/null 2>&1; then
        echo "     ✅ Agent responding"
        
        # Get stats
        STATS=$(curl -s http://127.0.0.1:8080/summary 2>/dev/null)
        TOTAL=$(echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total','?'))" 2>/dev/null || echo "?")
        echo "     📊 Total entries: $TOTAL"
    else
        echo "     ⚠️  Agent not responding (run: mem agent)"
    fi
    
    # Check hook
    echo "  🔗 Hook:"
    if grep -q "super_memory/hook.sh" ~/.bashrc 2>/dev/null; then
        echo "     ✅ Shell hook configured"
    else
        echo "     ⚠️  Shell hook not configured"
    fi
}

# Main
main() {
    check_prereqs
    create_dir
    install_deps
    install_files
    configure_bashrc
    start_agent
    verify
    
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   ✅ Super Memory installed successfully!       ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Quick start:"
    echo "  1. Restart terminal or run: source ~/.bashrc"
    echo ""
    echo "  2. Start using:"
    echo "     mem add \"Сделал что-то\"       — Add to memory"
    echo "     mem done \"Task name\"         — Mark completed"
    echo "     mem search \"query\"           — Search"
    echo "     mem summary                  — Show summary"
    echo ""
    echo "  3. For AI context:"
    echo "     cat file.py | context_inject.py --prefix 'Review'"
    echo ""
    echo "  4. Check status:"
    echo "     mem status"
    echo "     mem agent     — Start agent if not running"
    echo ""
}

main "$@"
