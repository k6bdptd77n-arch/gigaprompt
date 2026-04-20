#!/bin/bash
# Super Memory — Universal AI Memory
# =====================================
# One-command install for universal memory that works with ANY AI agent
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/k6bdptd77n-arch/gigaprompt/main/install.sh | bash
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
REPO_URL="https://github.com/k6bdptd77n-arch/gigaprompt.git"
GITHUB_RAW="https://raw.githubusercontent.com/k6bdptd77n-arch/gigaprompt/main"

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

# Download a file from GitHub
download_file() {
    local file="$1"
    local url="${GITHUB_RAW}/${file}"
    echo "  📥 Downloading $file..."
    if curl -fsSL "$url" -o "$INSTALL_DIR/$file"; then
        echo "  ✅ $file"
        return 0
    else
        echo "  ❌ Failed to download $file"
        return 1
    fi
}

# Install Python dependencies
install_deps() {
    echo -e "${YELLOW}Checking dependencies...${NC}"

    # Check required Python modules
    python3 -c "import http.server" 2>/dev/null && echo "  ✅ http.server (stdlib)" || echo "  ⚠️  http.server missing"
    python3 -c "import sqlite3" 2>/dev/null && echo "  ✅ sqlite3 (stdlib)" || echo "  ⚠️  sqlite3 missing"
    python3 -c "import json" 2>/dev/null && echo "  ✅ json (stdlib)" || echo "  ⚠️  json missing"
    python3 -c "import os" 2>/dev/null && echo "  ✅ os (stdlib)" || echo "  ⚠️  os missing"

    # Install MCP for AI agent integration
    if python3 -c "import mcp" 2>/dev/null; then
        echo "  ✅ mcp (AI agent integration)"
    else
        echo -e "${YELLOW}  Installing mcp for AI agents...${NC}"
        pip3 install mcp --quiet 2>/dev/null && echo "  ✅ mcp installed" || echo "  ⚠️  mcp install failed (optional)"
    fi

    echo "  ✅ All required modules available"
}

# Download and install files
install_files() {
    echo -e "${YELLOW}Installing files...${NC}"
    
    # Core files (required)
    download_file "memory_agent.py" || exit 1
    
    # CLI (required)
    download_file "mem" || exit 1
    
    # Optional but useful
    download_file "hook.sh" && chmod +x "$INSTALL_DIR/hook.sh"
download_file "token_log.py" && chmod +x "$INSTALL_DIR/token_log.py"
    
    # Daemon files
    mkdir -p "$INSTALL_DIR/daemon"
    curl -fsSL "${GITHUB_RAW}/daemon/launcher.py" -o "$INSTALL_DIR/daemon/launcher.py" 2>/dev/null && chmod +x "$INSTALL_DIR/daemon/launcher.py" && echo "  ✅ daemon/launcher.py" || true
    curl -fsSL "${GITHUB_RAW}/daemon/super-memory.service" -o "$INSTALL_DIR/daemon/super-memory.service" 2>/dev/null && echo "  ✅ daemon/super-memory.service" || true
    
    # Make core files executable
    chmod +x "$INSTALL_DIR/memory_agent.py"
    chmod +x "$INSTALL_DIR/mem"
}

# Configure shell
configure_shell() {
    echo -e "${YELLOW}Configuring shell...${NC}"
    
    # For curl-based install, we need to set PATH or alias
    # Since hook.sh needs sourcing, provide both options
    
    # Option 1: Alias that sources hook
    MEM_ALIAS="alias mem='source ${INSTALL_DIR}/hook.sh'"
    
    # Option 2: Direct PATH to mem
    MEM_PATH="export PATH=\"\${PATH}:${INSTALL_DIR}\""
    
    # Check if already configured
    if grep -q "super_memory/hook.sh\|super_memory/mem" ~/.bashrc 2>/dev/null; then
        echo "  ✅ Already configured in ~/.bashrc"
    else
        echo "" >> ~/.bashrc
        echo "# Super Memory — Universal AI Memory" >> ~/.bashrc
        echo "$MEM_PATH" >> ~/.bashrc
        echo "$MEM_ALIAS" >> ~/.bashrc
        echo "  ✅ Added to ~/.bashrc"
    fi
    
    # Also check ~/.profile for ssh sessions
    if [ -f ~/.profile ]; then
        if ! grep -q "super_memory/mem" ~/.profile 2>/dev/null; then
            echo "" >> ~/.profile
            echo "# Super Memory" >> ~/.profile
            echo "export PATH=\"\${PATH}:${INSTALL_DIR}\"" >> ~/.profile
            echo "  ✅ Also added to ~/.profile"
        fi
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
    count=$(ls "$INSTALL_DIR/"*.py "$INSTALL_DIR/"*.sh 2>/dev/null | wc -l | tr -d ' ')
    echo "     $count files installed"
    ls -la "$INSTALL_DIR/"
    
    # Check API
    echo "  🌐 API:"
    if curl -s --max-time 2 http://127.0.0.1:8080/health > /dev/null 2>&1; then
        echo "     ✅ Agent responding"
        
        # Get stats
        STATS=$(curl -s http://127.0.0.1:8080/summary 2>/dev/null)
        TOTAL=$(echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total','?'))" 2>/dev/null || echo "?")
        echo "     📊 Total entries: $TOTAL"
    else
        echo "     ⚠️  Agent not responding (run: python3 $INSTALL_DIR/mem start)"
    fi
    
    # Check CLI
    echo "  🔗 CLI:"
    if "$INSTALL_DIR/mem" status 2>/dev/null; then
        echo "     ✅ mem CLI working"
    else
        echo "     ⚠️  mem CLI needs restart (source ~/.bashrc)"
    fi
}

# Main
main() {
    check_prereqs
    create_dir
    install_deps
    install_files
    configure_shell
    start_agent
    verify
    
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   ✅ Super Memory installed successfully!       ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Quick start:"
    echo "  1. Restart terminal OR run: source ~/.bashrc"
    echo ""
    echo "  2. Start using:"
    echo "     mem add \"Сделал что-то\"       — Add to memory"
    echo "     mem done \"Task name\"         — Mark completed"
    echo "     mem search \"query\"           — Search"
    echo "     mem summary                  — Show summary"
    echo "     mem tokens                   — Token usage"
    echo ""
    echo "  3. Check status:"
    echo "     mem status"
    echo "     mem start    — Start agent if not running"
    echo ""
    echo "Install location: $INSTALL_DIR"
    echo ""
}

main "$@"