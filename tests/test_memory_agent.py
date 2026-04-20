"""
Tests for memory_agent.py — uses in-memory SQLite via tmp_path fixture.
"""
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Patch DB_PATH before importing the module so tests never touch ~/.super_memory
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Redirect all path constants to tmp_path for each test."""
    import importlib
    db = tmp_path / "memory.db"
    cfg = tmp_path / "config.json"
    tok = tmp_path / "token_log.jsonl"

    import memory_agent as ma
    monkeypatch.setattr(ma, "DB_PATH", db)
    monkeypatch.setattr(ma, "CONFIG_PATH", cfg)
    monkeypatch.setattr(ma, "TOKEN_LOG_PATH", tok)
    ma._active_agent[0] = None
    ma.init_db()
    yield
    ma._active_agent[0] = None


# ---------------------------------------------------------------------------
# DB initialisation
# ---------------------------------------------------------------------------

def test_init_db_creates_tables(tmp_path):
    import memory_agent as ma
    conn = ma.get_db()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert "memories" in tables
    assert "files" in tables
    assert "folders" in tables
    assert "projects" in tables
    assert "schema_version" in tables


def test_schema_version_idempotent():
    import memory_agent as ma
    ma.init_db()  # second call must not raise
    conn = ma.get_db()
    rows = conn.execute("SELECT version FROM schema_version").fetchall()
    conn.close()
    versions = [r[0] for r in rows]
    assert versions.count(1) == 1  # migration 1 applied exactly once


# ---------------------------------------------------------------------------
# Active-agent cache
# ---------------------------------------------------------------------------

def test_active_agent_cache_invalidated_by_save_config():
    import memory_agent as ma
    _ = ma.get_active_agent()  # prime cache
    assert ma._active_agent[0] == "default"
    ma.save_config({"active_agent": "other"})
    assert ma._active_agent[0] is None
    assert ma.get_active_agent() == "other"


# ---------------------------------------------------------------------------
# Token logging
# ---------------------------------------------------------------------------

def test_log_token_usage_writes_jsonl():
    import memory_agent as ma
    entry = ma.log_token_usage("claude-sonnet-4-6", {"input_tokens": 100, "output_tokens": 50})
    assert ma.TOKEN_LOG_PATH.exists()
    line = json.loads(ma.TOKEN_LOG_PATH.read_text().strip())
    assert line["model"] == "claude-sonnet-4-6"
    assert line["input_tokens"] == 100
    assert line["estimated_cost_usd"] > 0


def test_get_token_summary_aggregates():
    import memory_agent as ma
    ma.log_token_usage("claude-sonnet-4-6", {"input_tokens": 1000, "output_tokens": 500})
    ma.log_token_usage("claude-haiku-4-5", {"input_tokens": 200, "output_tokens": 100})
    s = ma.get_token_summary()
    assert s["total_requests"] == 2
    assert s["total_input_tokens"] == 1200
    assert len(s["models_used"]) == 2


# ---------------------------------------------------------------------------
# HTTP handler via fake socket
# ---------------------------------------------------------------------------

class FakeSocket:
    """Minimal socket stub for BaseHTTPRequestHandler."""
    def __init__(self):
        self._data = b""

    def makefile(self, mode, *a, **kw):
        import io
        if "r" in mode:
            return io.BytesIO(self._data)
        return io.BytesIO()

    def sendall(self, data):
        self._sent = getattr(self, "_sent", b"") + data

    def getsockname(self):
        return ("127.0.0.1", 8080)


def make_handler(method: str, path: str, body: bytes = b""):
    """Build a MemoryHandler instance without a real socket."""
    import memory_agent as ma
    import io
    from http.client import parse_headers

    header_block = (
        f"Host: 127.0.0.1\r\n"
        f"Content-Length: {len(body)}\r\n\r\n"
    ).encode()

    handler = ma.MemoryHandler.__new__(ma.MemoryHandler)
    handler.command = method
    handler.path = path
    handler.request_version = "HTTP/1.1"
    handler.requestline = f"{method} {path} HTTP/1.1"
    handler.headers = parse_headers(io.BytesIO(header_block))
    handler.rfile = io.BytesIO(body)
    handler.wfile = io.BytesIO()
    handler.client_address = ("127.0.0.1", 1234)
    handler.server = types.SimpleNamespace(server_address=("127.0.0.1", 8080))
    return handler


def get_response_json(handler):
    handler.wfile.seek(0)
    raw = handler.wfile.read()
    # strip HTTP header
    body = raw.split(b"\r\n\r\n", 1)[1]
    return json.loads(body)


def test_get_health():
    import memory_agent as ma
    h = make_handler("GET", "/health")
    h.do_GET()
    resp = get_response_json(h)
    assert resp["status"] == "ok"


def test_post_add_memory():
    import memory_agent as ma
    body = json.dumps({"text": "test entry", "type": "general"}).encode()
    h = make_handler("POST", "/add", body)
    h.do_POST()
    resp = get_response_json(h)
    assert resp.get("success") is True
    assert "id" in resp


def test_post_add_requires_text():
    import memory_agent as ma
    body = json.dumps({}).encode()
    h = make_handler("POST", "/add", body)
    h.do_POST()
    resp = get_response_json(h)
    assert "error" in resp


def test_search_sanitises_fts_query():
    import memory_agent as ma
    # Insert a memory first
    conn = ma.get_db()
    conn.execute(
        "INSERT INTO memories (text, type, timestamp, source, metadata, search_text, agent_id) VALUES (?,?,?,?,?,?,?)",
        ("hello world", "general", "2025-01-01", "test", "{}", "hello world", "default")
    )
    conn.commit()
    conn.close()
    # Query with FTS-special chars — should not raise
    h = make_handler("GET", '/search?q=hello":(')
    h.do_GET()
    resp = get_response_json(h)
    assert "results" in resp


def test_max_body_cap(monkeypatch):
    import memory_agent as ma
    assert ma.MAX_BODY == 1_048_576


# ---------------------------------------------------------------------------
# prepare_search_text
# ---------------------------------------------------------------------------

def test_prepare_search_text_strips_emoji():
    import memory_agent as ma
    result = ma.prepare_search_text("hello 🌍 world")
    assert "🌍" not in result
    assert "hello" in result
