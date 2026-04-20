#!/usr/bin/env python3
"""
Super Memory Token Logger — wraps Claude API calls to auto-log token usage.
Works as a drop-in wrapper for `curl` or any API client.

Usage:
  # Wrap curl:
  SUPER_MEMORY_API=http://127.0.0.1:8080 python token_log.py curl https://api.anthropic.com/v1/messages ...

  # In Python (via subprocess):
  import subprocess, os, json
  env = os.environ.copy()
  env["SUPER_MEMORY_API"] = "http://127.0.0.1:8080"
  result = subprocess.run(
      ["python", "token_log.py", "curl", "https://api.anthropic.com/v1/messages", ...],
      env=env, capture_output=True
  )

  # Or use as a module:
  from token_log import log_tokens
  log_tokens("claude-opus-4-6", {"input_tokens": 1000, "output_tokens": 500})
"""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

_SRC = Path(__file__).parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from mem.tokens import TOKEN_PRICES, DEFAULT_PRICE, _locked_append

SUPER_MEMORY_API = os.environ.get("SUPER_MEMORY_API", "http://127.0.0.1:8080")
TOKEN_LOG_PATH = os.path.expanduser("~/.super_memory/token_log.jsonl")


def log_tokens(model: str, usage: dict, source: str = "curl"):
    """Log token usage to local file + Super Memory API."""
    prices = TOKEN_PRICES.get(model, DEFAULT_PRICE)
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)
    cache_creation = usage.get("cache_creation_input_tokens", 0)

    input_cost = (input_tokens / 1_000_000) * prices["input"]
    output_cost = (output_tokens / 1_000_000) * prices["output"]
    cache_savings = (cache_read / 1_000_000) * prices["input"] * 0.9

    entry = {
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "source": source,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_creation,
        "estimated_cost_usd": round(input_cost + output_cost, 4),
        "cache_savings_usd": round(cache_savings, 4),
    }

    # Save locally (flock guards against interleaved writes)
    os.makedirs(os.path.dirname(TOKEN_LOG_PATH), exist_ok=True)
    with _locked_append(TOKEN_LOG_PATH) as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Send to Super Memory API (optional - local log always saved)
    try:
        req = urllib.request.Request(
            f"{SUPER_MEMORY_API}/log_tokens",
            data=json.dumps({"model": model, "usage": usage, "source": source}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                return entry  # Successfully logged to API
    except urllib.error.URLError as e:
        # Silently ignore if agent not running - local log is sufficient
        pass
    except Exception:
        # Log errors to stderr for debugging but don't fail
        print(f"[Super Memory] Warning: Could not reach API at {SUPER_MEMORY_API}", file=sys.stderr)

    return entry


def main():
    if len(sys.argv) < 2:
        print("Usage: token_log.py <command> [args...]")
        print("   Wraps API calls and logs token usage to Super Memory.")
        print("   Example: token_log.py curl -X POST https://api.anthropic.com/v1/messages \\")
        print("              -H 'x-api-key: $ANTHROPIC_API_KEY' ...")
        sys.exit(1)

    # Check for model in env (set by wrapper scripts)
    model = os.environ.get("CLAUDE_MODEL", "claude-opus-4-6")
    source = os.environ.get("CLAUDE_API_SOURCE", "curl")

    # Build command
    cmd = sys.argv[1:]

    # Run the actual command, capturing output
    result = subprocess.run(cmd, capture_output=True)

    # Print stdout/stderr
    if result.stdout:
        sys.stdout.write(result.stdout.decode("utf-8", errors="replace"))
    if result.stderr:
        sys.stderr.write(result.stderr.decode("utf-8", errors="replace"))

    # Try to extract token usage from the response
    if result.stdout:
        # Try to detect JSON response
        try:
            data = json.loads(result.stdout.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
            data = None
        usage = {}
        if isinstance(data, dict) and "usage" in data:
            usage = data["usage"]
            if "model" in data:
                model = data["model"]

        if usage:
            entry = log_tokens(model, usage, source)
            print(f"\n[Super Memory] Logged: {entry['input_tokens']} in / {entry['output_tokens']} out — ~${entry['estimated_cost_usd']}", file=sys.stderr)

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
