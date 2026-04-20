"""
Shared token pricing, logging, and aggregation for Super Memory.
Single source of truth — imported by memory_agent.py, desktop_monitor, token_log.py.
"""
import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

TOKEN_PRICES: dict = {
    "claude-opus-4-7": {"input": 15.00, "output": 75.00},
    "claude-opus-4-6": {"input": 5.00, "output": 25.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}
DEFAULT_PRICE: dict = {"input": 5.00, "output": 25.00}


@contextmanager
def _locked_append(path):
    """Append-open a file with an exclusive advisory lock (no-op on Windows)."""
    f = open(path, "a", encoding="utf-8")
    try:
        try:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass
        yield f
    finally:
        try:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (ImportError, OSError):
            pass
        f.close()


def log_token_usage(token_log_path: Path, model: str, usage: dict, source: str = "api") -> dict:
    """Write one JSONL entry to token_log_path and return the entry."""
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

    try:
        token_log_path.parent.mkdir(parents=True, exist_ok=True)
        with _locked_append(str(token_log_path)) as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass

    return entry


def get_token_summary(token_log_path: Path) -> dict:
    """Aggregate all JSONL entries in token_log_path into a summary dict."""
    total_input = 0
    total_output = 0
    total_cost = 0.0
    total_cache_savings = 0.0
    entries = 0
    models: set = set()
    daily_costs: dict = {}

    if token_log_path.exists():
        try:
            with open(token_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    total_input += e.get("input_tokens", 0)
                    total_output += e.get("output_tokens", 0)
                    total_cost += e.get("estimated_cost_usd", 0)
                    total_cache_savings += e.get("cache_savings_usd", 0)
                    models.add(e.get("model", "unknown"))
                    entries += 1
                    day = e.get("timestamp", "")[:10]
                    daily_costs[day] = daily_costs.get(day, 0) + e.get("estimated_cost_usd", 0)
        except OSError:
            pass

    return {
        "total_requests": entries,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cost_usd": round(total_cost, 4),
        "total_cache_savings_usd": round(total_cache_savings, 0),
        "models_used": sorted(models),
        "daily_costs": {k: round(v, 4) for k, v in sorted(daily_costs.items())},
    }
