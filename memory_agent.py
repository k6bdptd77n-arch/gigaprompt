#!/usr/bin/env python3
"""
Super Memory Agent — Universal Background Memory Service
=====================================================
REST API daemon that works with ANY AI agent.
Start with: super-memory-agent &
Access from: curl http://localhost:8080/memory/...
"""

import json
import os
import sys
import hashlib
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

# Database
DB_PATH = Path.home() / ".super_memory" / "memory.db"
TOKEN_LOG_PATH = Path.home() / ".super_memory" / "token_log.jsonl"

# Ensure directory
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Token pricing (Anthropic API — USD per 1M tokens)
TOKEN_PRICES = {
    "claude-opus-4-6": {"input": 5.00, "output": 25.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}
DEFAULT_PRICE = {"input": 5.00, "output": 25.00}


def init_db():
    """Initialize SQLite database."""
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            type TEXT DEFAULT 'general',
            timestamp TEXT NOT NULL,
            source TEXT DEFAULT 'unknown',
            metadata TEXT DEFAULT '{}',
            search_text TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp)")
    conn.commit()
    conn.close()


def get_db():
    """Get database connection."""
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def prepare_search_text(text: str) -> str:
    """Clean text for FTS."""
    import re
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.lower().strip()


def log_token_usage(model: str, usage: dict, source: str = "api"):
    """Log token usage to token_log.jsonl for tracking spend."""
    import urllib.request

    prices = TOKEN_PRICES.get(model, DEFAULT_PRICE)
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)
    cache_creation = usage.get("cache_creation_input_tokens", 0)

    input_cost = (input_tokens / 1_000_000) * prices["input"]
    output_cost = (output_tokens / 1_000_000) * prices["output"]
    cache_savings = (cache_read / 1_000_000) * prices["input"] * 0.9  # ~90% savings

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
        with open(TOKEN_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
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
                    except:
                        continue
                    total_input += e.get("input_tokens", 0)
                    total_output += e.get("output_tokens", 0)
                    total_cost += e.get("estimated_cost_usd", 0)
                    total_cache_savings += e.get("cache_savings_usd", 0)
                    models.add(e.get("model", "unknown"))
                    entries += 1
                    day = e.get("timestamp", "")[:10]
                    daily_costs[day] = daily_costs.get(day, 0) + e.get("estimated_cost_usd", 0)
        except Exception:
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
    """HTTP handler for memory operations."""
    
    def log_message(self, format, *args):
        """Suppress log messages."""
        pass
    
    def send_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        
        conn = get_db()
        
        if path == '/health':
            self.send_json({'status': 'ok', 'db': str(DB_PATH)})
        
        elif path == '/summary':
            cursor = conn.execute("""
                SELECT type, COUNT(*) as count FROM memories GROUP BY type
            """)
            counts = {row['type']: row['count'] for row in cursor.fetchall()}
            cursor = conn.execute("SELECT COUNT(*) as total FROM memories")
            total = cursor.fetchone()['total']
            self.send_json({
                'total': total,
                'completed': counts.get('completed', 0),
                'decisions': counts.get('decision', 0),
                'blockers': counts.get('blocker', 0),
                'learnings': counts.get('learning', 0)
            })
        
        elif path == '/recent':
            cursor = conn.execute(
                "SELECT * FROM memories ORDER BY id DESC LIMIT 10"
            )
            rows = [dict(row) for row in cursor.fetchall()]
            self.send_json({'memories': rows})
        
        elif path.startswith('/search'):
            query = parse_qs(parsed.query).get('q', [''])[0]
            if query:
                cursor = conn.execute("""
                    SELECT * FROM memories 
                    WHERE search_text LIKE ? OR text LIKE ?
                    ORDER BY id DESC LIMIT 20
                """, (f'%{query.lower()}%', f'%{query.lower()}%'))
                rows = [dict(row) for row in cursor.fetchall()]
                self.send_json({'results': rows, 'query': query})
            else:
                self.send_json({'results': [], 'query': ''})
        
        elif path == '/context':
            # Get context for AI agents
            cursor = conn.execute("""
                SELECT text, type, timestamp FROM memories
                ORDER BY id DESC LIMIT 20
            """)
            rows = cursor.fetchall()

            completed = [dict(r) for r in rows if r['type'] == 'completed'][:5]
            decisions = [dict(r) for r in rows if r['type'] == 'decision'][:3]
            blockers = [dict(r) for r in rows if r['type'] == 'blocker'][:2]

            context = "## Recent Memory Context\n\n"

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

            self.send_json({'context': context})

        elif path == '/tokens' or path == '/tokens/summary':
            summary = get_token_summary()
            self.send_json(summary)

        elif path == '/tokens/daily':
            summary = get_token_summary()
            daily = summary.get("daily_costs", {})
            total = summary.get("total_cost_usd", 0)
            self.send_json({"daily": daily, "total_usd": total})

        elif path == '/tokens/recent':
            entries = []
            if TOKEN_LOG_PATH.exists():
                try:
                    with open(TOKEN_LOG_PATH, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    for line in reversed(lines[-20:]):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entries.append(json.loads(line))
                        except:
                            continue
                except Exception:
                    pass
            self.send_json({"entries": entries})
        
        else:
            self.send_json({'error': 'Not found'}, 404)
        
        conn.close()
    
    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode() if length > 0 else '{}'
        
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        conn = get_db()
        
        if path == '/add':
            text = data.get('text', '')
            entry_type = data.get('type', 'general')
            source = data.get('source', 'api')
            metadata = data.get('metadata', {})
            
            if text:
                timestamp = datetime.now().isoformat()
                conn.execute("""
                    INSERT INTO memories (text, type, timestamp, source, metadata, search_text)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (text, entry_type, timestamp, source, 
                      json.dumps(metadata, ensure_ascii=False),
                      prepare_search_text(text)))
                conn.commit()
                
                cursor = conn.execute("SELECT last_insert_rowid() as id")
                row_id = cursor.fetchone()['id']
                self.send_json({'success': True, 'id': row_id})
            else:
                self.send_json({'error': 'text required'}, 400)
        
        elif path == '/add_completed':
            task = data.get('task', '')
            result = data.get('result', '')
            artifacts = data.get('artifacts', [])
            
            text = f"✅ {task}"
            if result:
                text += f"\nResult: {result}"
            if artifacts:
                text += f"\nArtifacts: {', '.join(artifacts)}"
            
            timestamp = datetime.now().isoformat()
            metadata = {'task': task, 'result': result, 'artifacts': artifacts}
            
            conn.execute("""
                INSERT INTO memories (text, type, timestamp, source, metadata, search_text)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (text, 'completed', timestamp, 'api',
                  json.dumps(metadata, ensure_ascii=False),
                  prepare_search_text(text)))
            conn.commit()
            
            self.send_json({'success': True})
        
        elif path == '/add_decision':
            topic = data.get('topic', '')
            decision = data.get('decision', '')
            reason = data.get('reason', '')
            
            text = f"⚖️ Decision: {topic}\n→ {decision}"
            if reason:
                text += f"\nWhy: {reason}"
            
            timestamp = datetime.now().isoformat()
            metadata = {'topic': topic, 'decision': decision, 'reason': reason}
            
            conn.execute("""
                INSERT INTO memories (text, type, timestamp, source, metadata, search_text)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (text, 'decision', timestamp, 'api',
                  json.dumps(metadata, ensure_ascii=False),
                  prepare_search_text(text)))
            conn.commit()
            
            self.send_json({'success': True})
        
        elif path == '/add_blocker':
            task = data.get('task', '')
            blocker = data.get('blocker', '')
            needed = data.get('needed', '')
            
            text = f"🚧 Blocked: {task}\nBlocker: {blocker}\nNeeded: {needed}"
            
            timestamp = datetime.now().isoformat()
            metadata = {'task': task, 'blocker': blocker, 'needed': needed}
            
            conn.execute("""
                INSERT INTO memories (text, type, timestamp, source, metadata, search_text)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (text, 'blocker', timestamp, 'api',
                  json.dumps(metadata, ensure_ascii=False),
                  prepare_search_text(text)))
            conn.commit()
            
            self.send_json({'success': True})

        elif path == '/log_tokens':
            model = data.get('model', 'claude-opus-4-6')
            usage = data.get('usage', {})
            source = data.get('source', 'api')
            entry = log_token_usage(model, usage, source)
            self.send_json({'success': True, 'logged': entry})

        else:
            self.send_json({'error': 'Not found'}, 404)

        conn.close()


def run_server(port=8080):
    """Run the HTTP server."""
    init_db()
    server = HTTPServer(('127.0.0.1', port), MemoryHandler)
    print(f"Super Memory Agent running on http://127.0.0.1:{port}")
    print(f"DB: {DB_PATH}")
    print("\nEndpoints:")
    print("  GET  /health             — Health check")
    print("  GET  /summary           — Memory summary")
    print("  GET  /recent            — Recent entries")
    print("  GET  /search?q=query    — Search")
    print("  GET  /context           — AI context (for prompts)")
    print("  GET  /tokens/summary    — Token usage summary")
    print("  GET  /tokens/daily      — Daily cost breakdown")
    print("  GET  /tokens/recent     — Recent token log entries")
    print("  POST /add               — Add entry")
    print("  POST /add_completed     — Add completed task")
    print("  POST /add_decision      — Add decision")
    print("  POST /add_blocker       — Add blocker")
    print("  POST /log_tokens        — Log token usage")
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
