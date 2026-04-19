#!/usr/bin/env python3
"""
Super Memory Desktop Monitor
============================
Flask + WebSocket PTY terminal for Super Memory project.
"""

import os
import sys
import threading
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, jsonify, request
import requests

app = Flask(__name__, template_folder='templates')

SUPER_MEMORY_API = os.environ.get('SUPER_MEMORY_API', 'http://127.0.0.1:8080')
TOKEN_LOG_PATH = os.path.expanduser('~/.super_memory/token_log.jsonl')
MEMORY_DB_PATH = os.path.expanduser('~/.super_memory/memory.db')


# ============================================================
# Helpers
# ============================================================

def get_memory_summary():
    try:
        r = requests.get(f'{SUPER_MEMORY_API}/summary', timeout=2)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}


def get_token_summary():
    total_input = total_output = total_cost = 0.0
    total_cache_savings = 0.0
    entries = 0
    models = set()
    daily_costs = {}

    if os.path.exists(TOKEN_LOG_PATH):
        try:
            with open(TOKEN_LOG_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        import json
                        e = json.loads(line)
                        total_input += e.get('input_tokens', 0)
                        total_output += e.get('output_tokens', 0)
                        total_cost += e.get('estimated_cost_usd', 0)
                        total_cache_savings += e.get('cache_savings_usd', 0)
                        models.add(e.get('model', 'unknown'))
                        entries += 1
                        day = e.get('timestamp', '')[:10]
                        daily_costs[day] = daily_costs.get(day, 0) + e.get('estimated_cost_usd', 0)
                    except Exception:
                        continue
        except Exception:
            pass

    return {
        'total_requests': entries,
        'total_input_tokens': int(total_input),
        'total_output_tokens': int(total_output),
        'total_cost_usd': round(total_cost, 4),
        'total_cache_savings_usd': round(total_cache_savings, 0),
        'models_used': list(models),
        'daily_costs': {k: round(v, 4) for k, v in sorted(daily_costs.items())},
    }


def get_agent_status():
    try:
        r = requests.get(f'{SUPER_MEMORY_API}/health', timeout=2)
        return r.status_code == 200
    except Exception:
        return False


# ============================================================
# Flask Routes
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/setup')
def setup():
    return render_template('setup.html')


@app.route('/api/ui/data')
def ui_data():
    summary = get_memory_summary()
    tokens = get_token_summary()
    recent = []
    try:
        r = requests.get(f'{SUPER_MEMORY_API}/recent', timeout=2)
        recent = r.json().get('memories', []) if r.status_code == 200 else []
    except Exception:
        pass

    return jsonify({
        'memory': summary,
        'tokens': tokens,
        'recent': recent[-10:],
        'agent_ok': get_agent_status(),
        'db_path': str(MEMORY_DB_PATH),
        'token_log_path': str(TOKEN_LOG_PATH),
    })


@app.route('/api/project/summary')
def project_summary():
    import sqlite3

    try:
        conn = sqlite3.connect(str(MEMORY_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT id, text, type, timestamp, metadata, search_text FROM memories ORDER BY id DESC LIMIT 50"
        )
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        blockers = [r for r in rows if r['type'] == 'blocker']
        completed = [r for r in rows if r['type'] == 'completed']
        decisions = [r for r in rows if r['type'] == 'decision']
        learnings = [r for r in rows if r['type'] == 'learning']
        general = [r for r in rows if r['type'] == 'general']

        context_text = ''
        try:
            ctx_r = requests.get(f'{SUPER_MEMORY_API}/context', timeout=2)
            if ctx_r.status_code == 200:
                context_text = ctx_r.json().get('context', '')
        except Exception:
            pass

        tokens = get_token_summary()

        return jsonify({
            'blockers': blockers,
            'completed': completed,
            'decisions': decisions,
            'learnings': learnings,
            'general': general,
            'context': context_text,
            'totals': {
                'blockers': len(blockers),
                'completed': len(completed),
                'decisions': len(decisions),
                'learnings': len(learnings),
                'general': len(general),
            },
            'daily_cost': tokens.get('daily_costs', {}),
            'total_cost': tokens.get('total_cost_usd', 0),
            'agent_ok': get_agent_status(),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tokens/recent')
def tokens_recent():
    entries = []
    if os.path.exists(TOKEN_LOG_PATH):
        try:
            with open(TOKEN_LOG_PATH, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for line in reversed(lines[-50:]):
                line = line.strip()
                if not line:
                    continue
                try:
                    import json
                    entries.append(json.loads(line))
                except Exception:
                    continue
        except Exception:
            pass
    return jsonify({'entries': entries})


@app.route('/api/sql/query', methods=['POST'])
def sql_query():
    import sqlite3

    data = request.get_json() or {}
    query = data.get('query', '').strip()

    if not query:
        return jsonify({'error': 'Query is required'}), 400

    if not query.upper().startswith('SELECT'):
        return jsonify({'error': 'Only SELECT queries are allowed'}), 400

    try:
        conn = sqlite3.connect(str(MEMORY_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(query)
        rows = [dict(row) for row in cursor.fetchall()]
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        conn.close()
        return jsonify({'columns': columns, 'rows': rows, 'count': len(rows)})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/sql/schema')
def sql_schema():
    import sqlite3
    try:
        conn = sqlite3.connect(str(MEMORY_DB_PATH))
        cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table'")
        schemas = [row[0] for row in cursor.fetchall() if row[0]]
        conn.close()
        return jsonify({'schemas': schemas})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/cli/run', methods=['POST'])
def cli_run():
    import subprocess

    data = request.get_json() or {}
    cmd = data.get('command', '').strip()

    if not cmd:
        return jsonify({'error': 'Command is required'}), 400

    if cmd.startswith('mem '):
        args = cmd[4:].strip()
    else:
        args = cmd

    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['SUPER_MEMORY_API'] = SUPER_MEMORY_API

        python_exe = r'C:\Program Files\Python311\python'
        mem_script = os.path.expanduser(r'~/.super_memory/mem')

        import shlex
        result = subprocess.run(
            [python_exe, mem_script] + shlex.split(args),
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        return jsonify({
            'stdout': result.stdout,
            'stderr': result.stderr,
            'exit_code': result.returncode,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


# ============================================================
# WebSocket PTY Terminal
# ============================================================

async def pty_terminal_handler(websocket):
    import queue, threading, os, platform

    cols, rows = 120, 30
    out_queue = queue.Queue()
    stop_event = threading.Event()

    env = {
        'TERM': 'xterm-256color',
        'PYTHONIOENCODING': 'utf-8',
        'SUPER_MEMORY_API': SUPER_MEMORY_API,
        'PATH': os.environ.get('PATH', ''),
    }

    proc = None
    is_windows = platform.system() == 'Windows'

    try:
        if is_windows:
            try:
                import winpty
                proc = winpty.PtyProcess.spawn(
                    [r'C:\Program Files\Git\usr\bin\bash.exe', '-l'],
                    dimensions=(rows, cols),
                    env=env,
                )
            except Exception:
                import subprocess
                proc = subprocess.Popen(
                    ['cmd.exe', '/q'],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                )
                proc.is_subprocess = True
        else:
            import pty
            pid, fd = pty.fork()
            if pid == 0:
                os.execvp('/bin/bash', ['/bin/bash', '-l'])
            else:
                class PtyProcess:
                    def __init__(self, pid, fd):
                        self.pid = pid
                        self.fd = fd
                    def read(self, size):
                        return os.read(self.fd, size)
                    def write(self, data):
                        return os.write(self.fd, data)
                    def kill(self):
                        os.kill(self.pid, 9)
                        os.close(self.fd)
                    def wait(self):
                        os.waitpid(self.pid, 0)
                proc = PtyProcess(pid, fd)
    except Exception as e:
        await websocket.send(f'\r\n\x1b[31mFailed to start shell: {e}\x1b[0m\r\n')
        return

    def reader_thread():
        """Read from PTY and put in queue"""
        try:
            while not stop_event.is_set():
                try:
                    if is_windows and hasattr(proc, 'is_subprocess'):
                        data = proc.stdout.read(4096)
                        if data:
                            out_queue.put(data)
                        else:
                            break
                    elif is_windows:
                        data = proc.read(4096)
                        if data:
                            out_queue.put(data)
                        else:
                            break
                    else:
                        import select
                        r, _, _ = select.select([proc.fd], [], [], 0.1)
                        if r:
                            data = os.read(proc.fd, 4096)
                            if data:
                                out_queue.put(data)
                            else:
                                break
                except Exception:
                    break
        except Exception:
            pass
        finally:
            stop_event.set()

    reader = threading.Thread(target=reader_thread, daemon=True)
    reader.start()

    async def pump_input():
        try:
            async for msg in websocket:
                if is_windows and hasattr(proc, 'is_subprocess'):
                    proc.stdin.write(msg.encode())
                    proc.stdin.flush()
                else:
                    proc.write(msg)
        except Exception:
            pass
        finally:
            stop_event.set()
            try:
                proc.kill()
            except Exception:
                pass

    async def pump_output():
        try:
            while not stop_event.is_set():
                try:
                    data = out_queue.get(timeout=0.05)
                    if data:
                        await websocket.send(data)
                except queue.Empty:
                    await asyncio.sleep(0.02)
                    continue
                except Exception:
                    break
        except Exception:
            pass
        finally:
            stop_event.set()
            try:
                proc.kill()
            except Exception:
                pass

    try:
        await asyncio.gather(pump_output(), pump_input())
    except Exception:
        stop_event.set()
        try:
            proc.kill()
            if not is_windows and hasattr(proc, 'wait'):
                proc.wait()
        except Exception:
            pass


def start_websocket_server():
    import websockets, threading

    async def run():
        async with websockets.serve(pty_terminal_handler, '127.0.0.1', 5001):
            await asyncio.Future()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def run_loop():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run())

    t = threading.Thread(target=run_loop, daemon=True)
    t.start()
    # Keep thread alive
    while t.is_alive():
        t.join(timeout=1)


def start_flask():
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)


def main():
    import time
    import webbrowser

    print('Starting Super Memory Desktop Monitor...')

    # Start WebSocket server in background thread
    ws_thread = threading.Thread(target=start_websocket_server, daemon=True)
    ws_thread.start()
    print('WebSocket terminal server on ws://127.0.0.1:5001')

    # Start Flask
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()

    time.sleep(1.5)

    url = 'http://127.0.0.1:5000'
    print(f'Opening browser at {url}')
    webbrowser.open(url)

    print('Flask running. Press Ctrl+C to stop.')
    while True:
        time.sleep(3600)


if __name__ == '__main__':
    main()
