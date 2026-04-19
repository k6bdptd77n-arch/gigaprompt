"""
Configuration management for Super Memory
"""
import os
import json
from pathlib import Path
from typing import Optional

SUPER_MEMORY_DIR = Path.home() / ".super_memory"
CONFIG_FILE = SUPER_MEMORY_DIR / "config.json"
DB_FILE = SUPER_MEMORY_DIR / "memory.db"
TOKEN_LOG = SUPER_MEMORY_DIR / "token_log.jsonl"
AGENT_PID = SUPER_MEMORY_DIR / "agent.pid"
AGENT_LOG = SUPER_MEMORY_DIR / "agent.log"
UI_TOKEN_FILE = SUPER_MEMORY_DIR / "ui_token"

DEFAULT_PORT = 8080


def ensure_dir():
    """Ensure ~/.super_memory/ exists."""
    SUPER_MEMORY_DIR.mkdir(exist_ok=True)


def load_config() -> dict:
    """Load config.json"""
    ensure_dir()
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"active_agent": "default"}


def save_config(config: dict):
    """Save config.json"""
    ensure_dir()
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def get_active_agent() -> str:
    """Get active agent name."""
    return load_config().get("active_agent", "default")


def set_active_agent(name: str):
    """Set active agent."""
    config = load_config()
    config["active_agent"] = name
    save_config(config)


def get_installed_path() -> Optional[Path]:
    """Check if memory_agent.py is installed in ~/.super_memory/"""
    path = SUPER_MEMORY_DIR / "memory_agent.py"
    return path if path.exists() else None