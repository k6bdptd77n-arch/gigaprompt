"""
API client for Super Memory REST API
"""
import os
import json
import urllib.request
import urllib.error
from typing import Optional

from mem.config import DEFAULT_PORT


def get_api_host() -> str:
    """Get API host from env or config."""
    env_host = os.environ.get('SUPER_MEMORY_API')
    if env_host:
        return env_host
    # Fallback to config-based host
    try:
        from mem.config import load_config
        config = load_config()
        port = config.get('port', DEFAULT_PORT)
        return f'http://127.0.0.1:{port}'
    except Exception:
        return f'http://127.0.0.1:{DEFAULT_PORT}'


API_HOST = get_api_host()


def api_get(endpoint: str, timeout: int = 5) -> dict:
    """GET request to memory API."""
    url = f"{API_HOST}{endpoint}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError:
        return {"error": "not_running"}
    except (json.JSONDecodeError, ValueError) as e:
        return {"error": f"invalid_response: {e}"}


def api_post(endpoint: str, data: dict, timeout: int = 5) -> dict:
    """POST request to memory API."""
    url = f"{API_HOST}{endpoint}"
    payload = json.dumps(data).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError:
        return {"error": "not_running"}
    except (json.JSONDecodeError, ValueError) as e:
        return {"error": f"invalid_response: {e}"}


def is_agent_running() -> bool:
    """Check if agent is running."""
    result = api_get("/health")
    return "error" not in result


def check_running_hint(result: dict) -> bool:
    """Print agent-not-running hint if needed. Returns True if error."""
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            print(msg.encode('ascii', 'replace').decode())

    if "error" in result:
        err = result["error"]
        if err == "not_running":
            safe_print("[X] Super Memory daemon is not running.")
            safe_print("   Start it with: mem daemon start")
            safe_print("   Or run: mem init")
        elif err.startswith("invalid_response"):
            safe_print("[X] Connection error. Is the daemon running?")
        else:
            safe_print(f"[X] {err}")
        return True
    return False