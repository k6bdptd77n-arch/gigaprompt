#!/usr/bin/env python3
"""
Super Memory Agent — Universal Background Memory Service
======================================================
REST API daemon with File Memory System (MVP 8)
Stores MD documentation attached to files and folders
"""

import collections
import functools
import json
import os
import re
import sqlite3
import sys
import hashlib
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
import threading


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


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle each request in a new daemon thread."""
    daemon_threads = True
    allow_reuse_address = True

# Database
DB_PATH = Path.home() / ".super_memory" / "memory.db"
TOKEN_LOG_PATH = Path.home() / ".super_memory" / "token_log.jsonl"
CONFIG_PATH = Path.home() / ".super_memory" / "config.json"

MAX_BODY = 1_048_576  # 1 MiB POST body cap

_active_agent: list = [None]  # mutable cache; invalidated by save_config


def load_config() -> dict:
    """Load config from JSON file."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_config(config: dict):
    """Save config to JSON file."""
    _active_agent[0] = None  # invalidate cache
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


# Token pricing (Anthropic API — USD per 1M tokens)
TOKEN_PRICES = {
    "claude-opus-4-6": {"input": 5.00, "output": 25.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}
DEFAULT_PRICE = {"input": 5.00, "output": 25.00}


def init_db():
    """Initialize SQLite database with all tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")

    # Agents table (multi-agent support)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            agent_type TEXT DEFAULT 'claude',
            api_key TEXT,
            api_url TEXT,
            model TEXT,
            config TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Memories table (with agent_id for multi-agent)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            type TEXT DEFAULT 'general',
            timestamp TEXT NOT NULL,
            source TEXT DEFAULT 'unknown',
            metadata TEXT DEFAULT '{}',
            search_text TEXT,
            agent_id TEXT DEFAULT 'default'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp)")

    # FTS5 virtual table for fast full-text search
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            text,
            content='memories',
            content_rowid='id'
        )
    """)

    # Triggers to keep FTS in sync
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, text) VALUES (new.id, new.text);
        END
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, text) VALUES('delete', old.id, old.text);
        END
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, text) VALUES('delete', old.id, old.text);
            INSERT INTO memories_fts(rowid, text) VALUES (new.id, new.text);
        END
    """)

    # Files table (with agent_id)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,
            extension TEXT,
            purpose TEXT,
            description TEXT,
            decisions TEXT DEFAULT '[]',
            patterns TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            search_text TEXT,
            agent_id TEXT DEFAULT 'default'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_filepath ON files(filepath)")

    # Folders table (with agent_id)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            purpose TEXT,
            description TEXT,
            blockers TEXT DEFAULT '[]',
            child_files TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            search_text TEXT,
            agent_id TEXT DEFAULT 'default'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_folder_path ON folders(path)")

    # Projects table (global - shared across agents)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            root_path TEXT,
            architecture TEXT,
            key_decisions TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """)
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_version").fetchall()}
    now_iso = datetime.now().isoformat()
    if 1 not in applied:
        try:
            conn.execute("ALTER TABLE memories ADD COLUMN agent_id TEXT DEFAULT 'default'")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_id ON memories(agent_id)")
            conn.execute("ALTER TABLE files ADD COLUMN agent_id TEXT DEFAULT 'default'")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_files_agent_id ON files(agent_id)")
            conn.execute("ALTER TABLE folders ADD COLUMN agent_id TEXT DEFAULT 'default'")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_folders_agent_id ON folders(agent_id)")
        except sqlite3.OperationalError:
            pass
        conn.execute("INSERT OR IGNORE INTO schema_version VALUES (1, ?)", (now_iso,))

    conn.commit()
    conn.close()


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_registry_db():
    """Get registry database connection (alias for get_db in single-DB architecture)."""
    return get_db()


def get_active_agent() -> str:
    """Get the currently active agent name from config."""
    if _active_agent[0] is None:
        config = load_config()
        _active_agent[0] = config.get("active_agent", "default")
    return _active_agent[0]


def get_agent_by_name(name: str) -> dict:
    """Get agent configuration by name."""
    conn = get_db()
    cursor = conn.execute("SELECT * FROM agents WHERE name = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def prepare_search_text(text: str) -> str:
    """Clean text for FTS."""
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.lower().strip()


def log_token_usage(model: str, usage: dict, source: str = "api"):
    """Log token usage to token_log.jsonl for tracking spend."""
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
        TOKEN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _locked_append(str(TOKEN_LOG_PATH)) as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass

    return entry


def get_token_summary() -> dict:
    """Aggregate token usage from token_log.jsonl."""
    total_input = 0
    total_output = 0
    total_cost = 0.0
    total_cache_savings = 0.0
    entries = 0
    models = set()
    daily_costs = {}

    if TOKEN_LOG_PATH.exists():
        try:
            with open(TOKEN_LOG_PATH, "r", encoding="utf-8") as f:
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
        "models_used": list(models),
        "daily_costs": {k: round(v, 4) for k, v in sorted(daily_costs.items())},
    }


class MemoryHandler(BaseHTTPRequestHandler):
    """HTTP handler for memory + file operations."""
    
    def log_message(self, format, *args):
        """Suppress log messages."""
        pass
    
    def send_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', 'http://127.0.0.1:5000')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    # ============================================================
    # MEMORY ENDPOINTS (existing)
    # ============================================================
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        conn = get_db()
        try:
            if path == '/health':
                self.send_json({'status': 'ok', 'db': str(DB_PATH)})

            elif path == '/summary':
                active = get_active_agent()
                cursor = conn.execute("""
                    SELECT type, COUNT(*) as count FROM memories
                    WHERE agent_id = ? GROUP BY type
                """, (active,))
                counts = {row['type']: row['count'] for row in cursor.fetchall()}
                cursor = conn.execute(
                    "SELECT COUNT(*) as total FROM memories WHERE agent_id = ?", (active,)
                )
                total = cursor.fetchone()['total']
                self.send_json({
                    'total': total,
                    'completed': counts.get('completed', 0),
                    'decisions': counts.get('decision', 0),
                    'blockers': counts.get('blocker', 0),
                    'learnings': counts.get('learning', 0),
                    'active_agent': active,
                })

            elif path == '/recent':
                active = get_active_agent()
                qs = parse_qs(parsed.query)
                limit = min(int(qs.get('limit', ['10'])[0]), 100)
                offset = int(qs.get('offset', ['0'])[0])
                cursor = conn.execute(
                    "SELECT * FROM memories WHERE agent_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                    (active, limit, offset)
                )
                rows = [dict(row) for row in cursor.fetchall()]
                self.send_json({'memories': rows, 'agent': active})

            elif path.startswith('/search'):
                active = get_active_agent()
                query = parse_qs(parsed.query).get('q', [''])[0]
                if query:
                    # Use FTS5 for fast full-text search
                    try:
                        safe_query = re.sub(r'[^\w\s]', '', query.lower())
                        cursor = conn.execute("""
                            SELECT memories.* FROM memories
                            JOIN memories_fts ON memories.id = memories_fts.rowid
                            WHERE memories_fts MATCH ? AND memories.agent_id = ?
                            ORDER BY memories.id DESC LIMIT 20
                        """, (f'{safe_query}*', active))
                        rows = [dict(row) for row in cursor.fetchall()]
                    except Exception:
                        # Fallback to LIKE if FTS fails
                        cursor = conn.execute("""
                            SELECT * FROM memories
                            WHERE agent_id = ?
                              AND (search_text LIKE ? OR text LIKE ?)
                            ORDER BY id DESC LIMIT 20
                        """, (active, f'%{query.lower()}%', f'%{query.lower()}%'))
                        rows = [dict(row) for row in cursor.fetchall()]
                    self.send_json({'results': rows, 'query': query, 'agent': active})
                else:
                    self.send_json({'results': [], 'query': ''})

            elif path == '/context':
                active = get_active_agent()
                cursor = conn.execute("""
                    SELECT text, type, timestamp FROM memories
                    WHERE agent_id = ?
                    ORDER BY id DESC LIMIT 20
                """, (active,))
                rows = cursor.fetchall()

                completed = [dict(r) for r in rows if r['type'] == 'completed'][:5]
                decisions = [dict(r) for r in rows if r['type'] == 'decision'][:3]
                blockers = [dict(r) for r in rows if r['type'] == 'blocker'][:2]

                context = f"## Recent Memory Context (agent: {active})\n\n"

                if completed:
                    context += "### Completed Tasks:\n"
                    for m in completed:
                        context += f"- {m['text'][:100]}\n"
                    context += "\n"

                if decisions:
                    context += "### Decisions:\n"
                    for m in decisions:
                        context += f"- {m['text'][:100]}\n"
                    context += "\n"

                if blockers:
                    context += "### Blockers:\n"
                    for m in blockers:
                        context += f"- {m['text'][:100]}\n"

                self.send_json({'context': context, 'agent': active})

            elif path == '/tokens' or path == '/tokens/summary':
                summary = get_token_summary()
                self.send_json(summary)

            elif path == '/tokens/daily':
                summary = get_token_summary()
                self.send_json({"daily": summary.get("daily_costs", {}), "total_usd": summary.get("total_cost_usd", 0)})

            elif path == '/tokens/recent':
                entries = []
                if TOKEN_LOG_PATH.exists():
                    try:
                        with open(TOKEN_LOG_PATH, "r", encoding="utf-8") as f:
                            tail = collections.deque(f, maxlen=20)
                        for line in reversed(list(tail)):
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                entries.append(json.loads(line))
                            except (json.JSONDecodeError, ValueError):
                                continue
                    except OSError:
                        pass
                self.send_json({"entries": entries})

            elif path == '/files' or path == '/files/list':
                cursor = conn.execute("SELECT * FROM files ORDER BY updated_at DESC LIMIT 50")
                rows = [dict(row) for row in cursor.fetchall()]
                self.send_json({'files': rows})

            elif path.startswith('/files/') and path.endswith('/info'):
                filepath = path[7:-5]
                cursor = conn.execute("SELECT * FROM files WHERE filepath = ?", (filepath,))
                row = cursor.fetchone()
                if row:
                    self.send_json({'file': dict(row)})
                else:
                    self.send_json({'error': 'File not found', 'filepath': filepath}, 404)

            elif path.startswith('/files/search'):
                query = parse_qs(parsed.query).get('q', [''])[0]
                if query:
                    cursor = conn.execute("""
                        SELECT * FROM files
                        WHERE search_text LIKE ? OR filepath LIKE ? OR purpose LIKE ?
                        ORDER BY updated_at DESC LIMIT 20
                    """, (f'%{query.lower()}%', f'%{query.lower()}%', f'%{query.lower()}%'))
                    rows = [dict(row) for row in cursor.fetchall()]
                    self.send_json({'results': rows, 'query': query})
                else:
                    self.send_json({'results': []})

            elif path == '/folders' or path == '/folders/list':
                cursor = conn.execute("SELECT * FROM folders ORDER BY updated_at DESC LIMIT 50")
                rows = [dict(row) for row in cursor.fetchall()]
                self.send_json({'folders': rows})

            elif path.startswith('/folders/') and path.endswith('/info'):
                folder_path = path[9:-5]
                cursor = conn.execute("SELECT * FROM folders WHERE path = ?", (folder_path,))
                row = cursor.fetchone()
                if row:
                    self.send_json({'folder': dict(row)})
                else:
                    self.send_json({'error': 'Folder not found', 'path': folder_path}, 404)

            elif path == '/projects' or path == '/projects/list':
                reg_conn = get_registry_db()
                try:
                    cursor = reg_conn.execute("SELECT * FROM projects ORDER BY updated_at DESC")
                    rows = [dict(row) for row in cursor.fetchall()]
                finally:
                    reg_conn.close()
                self.send_json({'projects': rows})

            elif path.startswith('/projects/') and path.endswith('/files'):
                project_name = path[10:-6]
                reg_conn = get_registry_db()
                try:
                    cursor = reg_conn.execute("SELECT * FROM projects WHERE name = ?", (project_name,))
                    project = cursor.fetchone()
                finally:
                    reg_conn.close()
                if project:
                    root = project['root_path'] or ''
                    cursor = conn.execute("""
                        SELECT * FROM files WHERE filepath LIKE ? ORDER BY filepath
                    """, (f'{root}%',))
                    rows = [dict(row) for row in cursor.fetchall()]
                    self.send_json({'project': project_name, 'files': rows})
                else:
                    self.send_json({'error': 'Project not found'}, 404)

            elif path == '/file_context':
                query = parse_qs(parsed.query).get('path', [''])[0]
                if not query:
                    self.send_json({'error': 'path parameter required'}, 400)
                    return

                cursor = conn.execute("SELECT * FROM files WHERE filepath = ?", (query,))
                file_row = cursor.fetchone()

                folder_path = str(Path(query).parent)
                cursor = conn.execute("SELECT * FROM folders WHERE path = ?", (folder_path,))
                folder_row = cursor.fetchone()

                file_name = Path(query).name
                cursor = conn.execute("""
                    SELECT * FROM memories
                    WHERE text LIKE ? OR text LIKE ?
                    ORDER BY id DESC LIMIT 5
                """, (f'%{file_name}%', f'%{query}%'))
                related_memories = [dict(row) for row in cursor.fetchall()]

                context = {
                    'file': dict(file_row) if file_row else None,
                    'folder': dict(folder_row) if folder_row else None,
                    'related_memories': related_memories,
                    'query_path': query
                }

                self.send_json(context)

            elif path == '/agents':
                cursor = conn.execute("SELECT * FROM agents ORDER BY name")
                rows = [dict(row) for row in cursor.fetchall()]
                for row in rows:
                    row.pop('api_key', None)
                active_agent = get_active_agent()
                self.send_json({'agents': rows, 'active': active_agent})

            elif path.startswith('/agents/') and path != '/agents/':
                parts = path.split('/')
                if len(parts) >= 3:
                    agent_name = parts[2]
                    cursor = conn.execute("SELECT * FROM agents WHERE name = ?", (agent_name,))
                    row = cursor.fetchone()
                    if row:
                        d = dict(row)
                        d.pop('api_key', None)
                        self.send_json({'agent': d})
                    else:
                        self.send_json({'error': 'Agent not found'}, 404)
                else:
                    self.send_json({'error': 'Invalid path'}, 400)

            elif path == '/active_agent':
                self.send_json({'active': get_active_agent()})

            else:
                self.send_json({'error': 'Not found'}, 404)
        finally:
            conn.close()
    
    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        length = min(int(self.headers.get('Content-Length', 0)), MAX_BODY)
        body = self.rfile.read(length).decode() if length > 0 else '{}'
        try:
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            data = {}
        conn = get_db()
        try:
            self._do_post_impl(conn, path, data)
        finally:
            conn.close()

    def _do_post_impl(self, conn, path, data):

        # ============================================================
        # AGENT MANAGEMENT ENDPOINTS (POST)
        # ============================================================

        if path == '/agents/add' or path == '/agents/update':
            name = data.get('name', '')
            agent_type = data.get('type', 'claude')
            api_key = data.get('api_key', '')
            api_url = data.get('api_url', '')
            model = data.get('model', '')
            config = data.get('config', {})

            if not name:
                self.send_json({'error': 'name required'}, 400)
                return

            now = datetime.now().isoformat()

            cursor = conn.execute("SELECT id FROM agents WHERE name = ?", (name,))
            existing = cursor.fetchone()

            if existing:
                conn.execute("""
                    UPDATE agents SET
                        agent_type = ?,
                        api_key = ?,
                        api_url = ?,
                        model = ?,
                        config = ?,
                        updated_at = ?
                    WHERE name = ?
                """, (agent_type, api_key, api_url, model, json.dumps(config), now, name))
            else:
                conn.execute("""
                    INSERT INTO agents (name, agent_type, api_key, api_url, model, config, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, agent_type, api_key, api_url, model, json.dumps(config), now, now))

            conn.commit()
            self.send_json({'success': True, 'name': name})
            return

        elif path == '/agents/delete':
            name = data.get('name', '')
            if not name:
                self.send_json({'error': 'name required'}, 400)
                return

            if name == 'default':
                self.send_json({'error': 'Cannot delete default agent'}, 400)
                return

            conn.execute("DELETE FROM agents WHERE name = ?", (name,))
            conn.commit()

            # If deleted agent was active, switch to default
            config = load_config()
            if config.get('active_agent') == name:
                config['active_agent'] = 'default'
                save_config(config)

            self.send_json({'success': True, 'deleted': name})
            return

        elif path == '/agents/select':
            name = data.get('name', '')
            if not name:
                self.send_json({'error': 'name required'}, 400)
                return

            # Verify agent exists
            cursor = conn.execute("SELECT id FROM agents WHERE name = ?", (name,))
            if not cursor.fetchone():
                self.send_json({'error': f'Agent {name} not found'}, 404)
                return

            config = load_config()
            config['active_agent'] = name
            save_config(config)

            self.send_json({'success': True, 'active': name})
            return

        # Existing memory endpoints
        if path == '/add':
            text = data.get('text', '')
            entry_type = data.get('type', 'general')
            source = data.get('source', 'api')
            metadata = data.get('metadata', {})
            agent_id = data.get('agent_id') or get_active_agent()

            if text:
                timestamp = datetime.now().isoformat()
                conn.execute("""
                    INSERT INTO memories (text, type, timestamp, source, metadata, search_text, agent_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (text, entry_type, timestamp, source,
                      json.dumps(metadata, ensure_ascii=False),
                      prepare_search_text(text), agent_id))
                conn.commit()

                cursor = conn.execute("SELECT last_insert_rowid() as id")
                row_id = cursor.fetchone()['id']
                self.send_json({'success': True, 'id': row_id, 'agent': agent_id})
            else:
                self.send_json({'error': 'text required'}, 400)

        elif path == '/add_completed':
            task = data.get('task', '')
            result = data.get('result', '')
            artifacts = data.get('artifacts', [])
            agent_id = data.get('agent_id') or get_active_agent()

            text = f"✅ {task}"
            if result:
                text += f"\nResult: {result}"
            if artifacts:
                text += f"\nArtifacts: {', '.join(artifacts)}"

            timestamp = datetime.now().isoformat()
            metadata = {'task': task, 'result': result, 'artifacts': artifacts}

            conn.execute("""
                INSERT INTO memories (text, type, timestamp, source, metadata, search_text, agent_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (text, 'completed', timestamp, data.get('source', 'api'),
                  json.dumps(metadata, ensure_ascii=False),
                  prepare_search_text(text), agent_id))
            conn.commit()

            self.send_json({'success': True, 'agent': agent_id})

        elif path == '/add_decision':
            topic = data.get('topic', '')
            decision = data.get('decision', '')
            reason = data.get('reason', '')
            agent_id = data.get('agent_id') or get_active_agent()

            text = f"⚖️ Decision: {topic}\n→ {decision}"
            if reason:
                text += f"\nWhy: {reason}"

            timestamp = datetime.now().isoformat()
            metadata = {'topic': topic, 'decision': decision, 'reason': reason}

            conn.execute("""
                INSERT INTO memories (text, type, timestamp, source, metadata, search_text, agent_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (text, 'decision', timestamp, data.get('source', 'api'),
                  json.dumps(metadata, ensure_ascii=False),
                  prepare_search_text(text), agent_id))
            conn.commit()

            self.send_json({'success': True, 'agent': agent_id})

        elif path == '/add_blocker':
            task = data.get('task', '')
            blocker = data.get('blocker', '')
            needed = data.get('needed', '')
            agent_id = data.get('agent_id') or get_active_agent()

            text = f"🚧 Blocked: {task}\nBlocker: {blocker}\nNeeded: {needed}"

            timestamp = datetime.now().isoformat()
            metadata = {'task': task, 'blocker': blocker, 'needed': needed}

            conn.execute("""
                INSERT INTO memories (text, type, timestamp, source, metadata, search_text, agent_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (text, 'blocker', timestamp, data.get('source', 'api'),
                  json.dumps(metadata, ensure_ascii=False),
                  prepare_search_text(text), agent_id))
            conn.commit()

            self.send_json({'success': True, 'agent': agent_id})

        elif path == '/log_tokens':
            model = data.get('model', 'claude-opus-4-6')
            usage = data.get('usage', {})
            source = data.get('source', 'api')
            entry = log_token_usage(model, usage, source)
            self.send_json({'success': True, 'logged': entry})
        
        # ============================================================
        # FILE ENDPOINTS (NEW - MVP 8)
        # ============================================================
        
        elif path == '/files/add' or path == '/files/update':
            filepath = data.get('filepath', '')
            purpose = data.get('purpose', '')
            description = data.get('description', '')
            decisions = data.get('decisions', [])
            patterns = data.get('patterns', [])
            agent_id = data.get('agent_id') or get_active_agent()

            if not filepath:
                self.send_json({'error': 'filepath required'}, 400)
                return

            now = datetime.now().isoformat()
            filename = Path(filepath).name
            extension = Path(filepath).suffix
            search_text = prepare_search_text(
                f"{filepath} {purpose} {description} {' '.join(patterns)}"
            )

            cursor = conn.execute("SELECT id FROM files WHERE filepath = ?", (filepath,))
            existing = cursor.fetchone()

            if existing:
                conn.execute("""
                    UPDATE files SET
                        purpose = ?, description = ?, decisions = ?,
                        patterns = ?, updated_at = ?, search_text = ?, agent_id = ?
                    WHERE filepath = ?
                """, (purpose, description, json.dumps(decisions), json.dumps(patterns),
                      now, search_text, agent_id, filepath))
            else:
                conn.execute("""
                    INSERT INTO files
                        (filepath, filename, extension, purpose, description,
                         decisions, patterns, created_at, updated_at, search_text, agent_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (filepath, filename, extension, purpose, description,
                      json.dumps(decisions), json.dumps(patterns),
                      now, now, search_text, agent_id))

            conn.commit()
            self.send_json({'success': True, 'filepath': filepath, 'agent': agent_id})
        
        elif path == '/folders/add' or path == '/folders/update':
            folder_path = data.get('path', '')
            purpose = data.get('purpose', '')
            description = data.get('description', '')
            blockers = data.get('blockers', [])
            agent_id = data.get('agent_id') or get_active_agent()

            if not folder_path:
                self.send_json({'error': 'path required'}, 400)
                return

            now = datetime.now().isoformat()
            name = Path(folder_path).name
            search_text = prepare_search_text(f"{folder_path} {purpose} {description}")

            cursor = conn.execute("SELECT id FROM folders WHERE path = ?", (folder_path,))
            existing = cursor.fetchone()

            if existing:
                conn.execute("""
                    UPDATE folders SET
                        purpose = ?, description = ?, blockers = ?,
                        updated_at = ?, search_text = ?, agent_id = ?
                    WHERE path = ?
                """, (purpose, description, json.dumps(blockers),
                      now, search_text, agent_id, folder_path))
            else:
                conn.execute("""
                    INSERT INTO folders
                        (path, name, purpose, description, blockers, created_at, updated_at, search_text, agent_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (folder_path, name, purpose, description, json.dumps(blockers),
                      now, now, search_text, agent_id))

            conn.commit()
            self.send_json({'success': True, 'path': folder_path, 'agent': agent_id})
        
        elif path == '/projects/add' or path == '/projects/update':
            name = data.get('name', '')
            root_path = data.get('root_path', '')
            architecture = data.get('architecture', '')
            key_decisions = data.get('key_decisions', [])

            if not name:
                self.send_json({'error': 'name required'}, 400)
                return

            now = datetime.now().isoformat()

            reg_conn = get_registry_db()
            try:
                cursor = reg_conn.execute("SELECT id FROM projects WHERE name = ?", (name,))
                existing = cursor.fetchone()

                if existing:
                    reg_conn.execute("""
                        UPDATE projects SET
                            root_path = ?,
                            architecture = ?,
                            key_decisions = ?,
                            updated_at = ?
                        WHERE name = ?
                    """, (root_path, architecture, json.dumps(key_decisions), now, name))
                else:
                    reg_conn.execute("""
                        INSERT INTO projects (name, root_path, architecture, key_decisions, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (name, root_path, architecture, json.dumps(key_decisions), now, now))

                reg_conn.commit()
            finally:
                reg_conn.close()
            self.send_json({'success': True, 'name': name})
        
        elif path == '/files/delete':
            filepath = data.get('filepath', '')
            if filepath:
                conn.execute("DELETE FROM files WHERE filepath = ?", (filepath,))
                conn.commit()
                self.send_json({'success': True, 'deleted': filepath})
            else:
                self.send_json({'error': 'filepath required'}, 400)
        
        elif path == '/folders/delete':
            folder_path = data.get('path', '')
            if folder_path:
                conn.execute("DELETE FROM folders WHERE path = ?", (folder_path,))
                conn.commit()
                self.send_json({'success': True, 'deleted': folder_path})
            else:
                self.send_json({'error': 'path required'}, 400)
        
        elif path == '/projects/delete':
            name = data.get('name', '')
            if name:
                reg_conn = get_registry_db()
                try:
                    reg_conn.execute("DELETE FROM projects WHERE name = ?", (name,))
                    reg_conn.commit()
                finally:
                    reg_conn.close()
                self.send_json({'success': True, 'deleted': name})
            else:
                self.send_json({'error': 'name required'}, 400)

        # ============================================================
        # MEMORY CRUD — delete and edit individual entries
        # ============================================================

        elif path == '/memories/delete':
            mem_id = data.get('id')
            if not mem_id:
                self.send_json({'error': 'id required'}, 400)
                return
            cursor = conn.execute("SELECT id FROM memories WHERE id = ?", (mem_id,))
            if not cursor.fetchone():
                self.send_json({'error': 'Memory not found'}, 404)
                return
            conn.execute("DELETE FROM memories WHERE id = ?", (mem_id,))
            conn.commit()
            self.send_json({'success': True, 'deleted': mem_id})

        elif path == '/memories/edit':
            mem_id = data.get('id')
            new_text = data.get('text', '').strip()
            if not mem_id or not new_text:
                self.send_json({'error': 'id and text required'}, 400)
                return
            cursor = conn.execute("SELECT id FROM memories WHERE id = ?", (mem_id,))
            if not cursor.fetchone():
                self.send_json({'error': 'Memory not found'}, 404)
                return
            conn.execute("""
                UPDATE memories SET text = ?, search_text = ? WHERE id = ?
            """, (new_text, prepare_search_text(new_text), mem_id))
            conn.commit()
            self.send_json({'success': True, 'id': mem_id})

        else:
            self.send_json({'error': 'Not found'}, 404)


def run_server(port=8080):
    """Run the HTTP server."""
    init_db()
    server = ThreadingHTTPServer(('127.0.0.1', port), MemoryHandler)
    print(f"Super Memory Agent running on http://127.0.0.1:{port}")
    print(f"DB: {DB_PATH}")
    print("\nEndpoints:")
    print("  GET  /health              — Health check")
    print("  GET  /summary             — Memory summary")
    print("  GET  /recent              — Recent entries")
    print("  GET  /search?q=           — Search memories")
    print("  GET  /context             — AI context")
    print("  GET  /tokens/summary      — Token usage")
    print("  POST /add                 — Add entry")
    print("  POST /add_completed       — Add completed task")
    print("  POST /add_decision        — Add decision")
    print("  POST /add_blocker         — Add blocker")
    print("  POST /log_tokens         — Log token usage")
    print()
    print("  FILE MEMORY (MVP 8):")
    print("  GET  /files/list          — List all files")
    print("  GET  /files/<path>/info   — File details")
    print("  GET  /files/search?q=     — Search files")
    print("  POST /files/add           — Add/update file")
    print("  DELETE /files/delete      — Delete file")
    print()
    print("  FOLDER MEMORY:")
    print("  GET  /folders/list        — List folders")
    print("  GET  /folders/<path>/info — Folder details")
    print("  POST /folders/add         — Add/update folder")
    print()
    print("  PROJECT MEMORY:")
    print("  GET  /projects/list       — List projects")
    print("  POST /projects/add        — Add/update project")
    print()
    print("  CONTEXT:")
    print("  GET  /file_context?path=  — Full context for file")
    print("\nCtrl+C to stop")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Super Memory Agent')
    parser.add_argument('--port', '-p', type=int, default=8080, help='Port to run on')
    args = parser.parse_args()
    
    run_server(args.port)