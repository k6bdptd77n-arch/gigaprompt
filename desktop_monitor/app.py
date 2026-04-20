#!/usr/bin/env python3
"""
Super Memory Desktop Monitor
============================
Flask + WebSocket (JSON-protocol) multi-session PTY terminal.
"""

import os
import sys
import json
import secrets
import shutil
import sqlite3
import subprocess
import threading
import asyncio
import platform
import time
import uuid
from functools import wraps
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from flask import Flask, render_template, jsonify, request, send_from_directory, redirect, url_for
import requests
from mem.config import SUPER_MEMORY_DIR, DB_FILE as MEMORY_DB_PATH, TOKEN_LOG as _TOKEN_LOG_DEFAULT, UI_TOKEN_FILE as API_TOKEN_PATH
from mem.tokens import get_token_summary as _get_token_summary

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / 'static'

app = Flask(__name__, template_folder=str(BASE_DIR / 'templates'), static_folder=None)
app.secret_key = secrets.token_bytes(32)

SUPER_MEMORY_API = os.environ.get('SUPER_MEMORY_API', 'http://127.0.0.1:8080')
SUPER_MEMORY_HOME = Path(os.environ.get('SUPER_MEMORY_HOME', SUPER_MEMORY_DIR))
TOKEN_LOG_PATH = SUPER_MEMORY_HOME / 'token_log.jsonl'

IS_WINDOWS = platform.system() == 'Windows'


# ============================================================
# UI auth token (shared between REST + WS)
# ============================================================

def _load_or_create_token() -> str:
    SUPER_MEMORY_HOME.mkdir(parents=True, exist_ok=True)
    if API_TOKEN_PATH.exists():
        token = API_TOKEN_PATH.read_text(encoding='utf-8').strip()
        if token:
            return token
    token = secrets.token_urlsafe(32)
    API_TOKEN_PATH.write_text(token, encoding='utf-8')
    try:
        os.chmod(API_TOKEN_PATH, 0o600)
    except OSError:
        pass
    return token


UI_TOKEN = _load_or_create_token()


def _token_from_request() -> str:
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:].strip()
    return request.args.get('token', '') or request.headers.get('X-UI-Token', '')


def require_token(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        token = _token_from_request()
        if token and secrets.compare_digest(token, UI_TOKEN):
            return view(*args, **kwargs)
        cookie = request.cookies.get('ui_auth', '')
        if cookie and secrets.compare_digest(cookie, UI_TOKEN):
            return view(*args, **kwargs)
        return jsonify({'error': 'unauthorized'}), 401
    return wrapper


# ============================================================
# Helpers
# ============================================================

def _get(path: str, timeout: float = 2.0):
    try:
        r = requests.get(f'{SUPER_MEMORY_API}{path}', timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except (requests.RequestException, ValueError):
        return None
    return None


def get_memory_summary() -> dict:
    return _get('/summary') or {}


def get_token_summary() -> dict:
    return _get_token_summary(TOKEN_LOG_PATH)


def get_agent_status() -> bool:
    return _get('/health') is not None


# ============================================================
# Page + static routes
# ============================================================

@app.route('/')
def index():
    token = request.args.get('token', '')
    if token:
        if secrets.compare_digest(token, UI_TOKEN):
            resp = redirect(url_for('index'))
            resp.set_cookie('ui_auth', UI_TOKEN, httponly=True, samesite='Strict', max_age=86400)
            return resp
        return jsonify({'error': 'unauthorized'}), 401
    cookie = request.cookies.get('ui_auth', '')
    if not (cookie and secrets.compare_digest(cookie, UI_TOKEN)):
        return jsonify({'error': 'unauthorized — open via the URL printed at startup'}), 401
    return render_template('index.html', ui_token='')


@app.route('/setup')
def setup():
    return render_template('setup.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(str(STATIC_DIR), filename)


# ============================================================
# Dashboard API
# ============================================================

@app.route('/api/ui/data')
@require_token
def ui_data():
    recent = _get('/recent') or {}
    return jsonify({
        'memory': get_memory_summary(),
        'tokens': get_token_summary(),
        'recent': (recent.get('memories') or [])[-10:],
        'agent_ok': get_agent_status(),
        'db_path': str(MEMORY_DB_PATH),
        'token_log_path': str(TOKEN_LOG_PATH),
    })


@app.route('/api/project/summary')
@require_token
def project_summary():
    try:
        conn = sqlite3.connect(f'file:{MEMORY_DB_PATH}?mode=ro', uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT id, text, type, timestamp, metadata, search_text FROM memories ORDER BY id DESC LIMIT 50"
        )
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500

    by_type = {'blocker': [], 'completed': [], 'decision': [], 'learning': [], 'general': []}
    for r in rows:
        by_type.setdefault(r['type'], []).append(r)

    ctx = _get('/context') or {}
    tokens = get_token_summary()

    return jsonify({
        'blockers': by_type['blocker'],
        'completed': by_type['completed'],
        'decisions': by_type['decision'],
        'learnings': by_type['learning'],
        'general': by_type['general'],
        'context': ctx.get('context', ''),
        'totals': {k: len(v) for k, v in by_type.items()},
        'daily_cost': tokens.get('daily_costs', {}),
        'total_cost': tokens.get('total_cost_usd', 0),
        'agent_ok': get_agent_status(),
    })


@app.route('/api/tokens/recent')
@require_token
def tokens_recent():
    import collections as _col
    entries = []
    if TOKEN_LOG_PATH.exists():
        try:
            with open(TOKEN_LOG_PATH, 'r', encoding='utf-8') as f:
                tail = _col.deque(f, maxlen=50)
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
    return jsonify({'entries': entries})


@app.route('/api/tokens/summary')
@require_token
def tokens_summary_route():
    return jsonify(get_token_summary())


# ============================================================
# Memory proxies (so UI shares the UI token, not the raw API)
# ============================================================

_PROXY_GET = {
    'summary': '/summary',
    'recent': '/recent',
    'search': '/search',
    'context': '/context',
    'files_list': '/files/list',
    'files_search': '/files/search',
    'folders_list': '/folders/list',
    'projects_list': '/projects/list',
    'tokens_daily': '/tokens/daily',
    'tokens_api_summary': '/tokens/summary',
    'file_context': '/file_context',
    'health': '/health',
}

_PROXY_POST = {
    'add': '/add',
    'add_completed': '/add_completed',
    'add_decision': '/add_decision',
    'add_blocker': '/add_blocker',
    'files_add': '/files/add',
    'files_delete': '/files/delete',
    'folders_add': '/folders/add',
    'folders_delete': '/folders/delete',
    'projects_add': '/projects/add',
    'projects_delete': '/projects/delete',
}


@app.route('/api/proxy/<name>', methods=['GET'])
@require_token
def proxy_get(name):
    upstream = _PROXY_GET.get(name)
    if not upstream:
        return jsonify({'error': 'unknown proxy'}), 404
    try:
        r = requests.get(f'{SUPER_MEMORY_API}{upstream}', params=request.args, timeout=5)
        return (r.text, r.status_code, {'Content-Type': r.headers.get('Content-Type', 'application/json')})
    except requests.RequestException as e:
        return jsonify({'error': str(e)}), 502


@app.route('/api/proxy/<name>', methods=['POST'])
@require_token
def proxy_post(name):
    upstream = _PROXY_POST.get(name)
    if not upstream:
        return jsonify({'error': 'unknown proxy'}), 404
    try:
        r = requests.post(f'{SUPER_MEMORY_API}{upstream}', json=request.get_json(silent=True) or {}, timeout=5)
        return (r.text, r.status_code, {'Content-Type': r.headers.get('Content-Type', 'application/json')})
    except requests.RequestException as e:
        return jsonify({'error': str(e)}), 502


# ============================================================
# Read-only SQL playground (authorizer + URI ro mode)
# ============================================================

_ALLOWED_SQL_OPS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}


def _sql_authorizer(action, *_args):
    return sqlite3.SQLITE_OK if action in _ALLOWED_SQL_OPS else sqlite3.SQLITE_DENY


@app.route('/api/sql/query', methods=['POST'])
@require_token
def sql_query():
    data = request.get_json(silent=True) or {}
    query = (data.get('query') or '').strip().rstrip(';')
    if not query:
        return jsonify({'error': 'Query is required'}), 400

    try:
        conn = sqlite3.connect(f'file:{MEMORY_DB_PATH}?mode=ro', uri=True)
        conn.row_factory = sqlite3.Row
        conn.set_authorizer(_sql_authorizer)
        cursor = conn.execute(query)
        rows = [dict(row) for row in cursor.fetchmany(500)]
        columns = [d[0] for d in cursor.description] if cursor.description else []
        conn.close()
        return jsonify({'columns': columns, 'rows': rows, 'count': len(rows)})
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/sql/schema')
@require_token
def sql_schema():
    try:
        conn = sqlite3.connect(f'file:{MEMORY_DB_PATH}?mode=ro', uri=True)
        cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table'")
        schemas = [row[0] for row in cursor.fetchall() if row[0]]
        conn.close()
        return jsonify({'schemas': schemas})
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 400


# ============================================================
# One-shot mem CLI runner (kept for quick inline commands)
# ============================================================

def _resolve_mem_script() -> Path:
    candidates = [
        SUPER_MEMORY_HOME / 'mem',
        Path(__file__).resolve().parent.parent / 'mem',
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


_ALLOWED_CLI_SUBCMDS = {'add', 'done', 'decision', 'blocked', 'search', 'recent', 'summary'}


@app.route('/api/cli/run', methods=['POST'])
@require_token
def cli_run():
    data = request.get_json(silent=True) or {}
    cmd = (data.get('command') or '').strip()
    if not cmd:
        return jsonify({'error': 'Command is required'}), 400
    if cmd.startswith('mem '):
        cmd = cmd[4:].strip()

    import shlex
    try:
        args = shlex.split(cmd)
    except ValueError as e:
        return jsonify({'error': f'Bad command: {e}'}), 400

    if not args or args[0] not in _ALLOWED_CLI_SUBCMDS:
        allowed = ', '.join(sorted(_ALLOWED_CLI_SUBCMDS))
        return jsonify({'error': f'Subcommand not allowed. Allowed: {allowed}'}), 400

    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['SUPER_MEMORY_API'] = SUPER_MEMORY_API

    mem_script = str(_resolve_mem_script())
    try:
        result = subprocess.run(
            [sys.executable, mem_script, *args],
            capture_output=True, text=True, env=env, timeout=15,
        )
        return jsonify({
            'stdout': result.stdout,
            'stderr': result.stderr,
            'exit_code': result.returncode,
        })
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Command timed out'}), 504
    except OSError as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# Agent lifecycle proxies
# ============================================================

def _launcher_call(action: str):
    try:
        from daemon import launcher
    except ImportError as e:
        return {'error': f'launcher unavailable: {e}'}, 500
    fn = getattr(launcher, action, None)
    if not callable(fn):
        return {'error': f'unknown action: {action}'}, 404
    try:
        result = fn()
    except Exception as e:  # launcher swallows most errors already
        return {'error': str(e)}, 500
    return {'ok': True, 'result': result}, 200


@app.route('/api/agent/status')
@require_token
def agent_status_route():
    return jsonify({'running': get_agent_status()})


@app.route('/api/agent/<action>', methods=['POST'])
@require_token
def agent_action(action):
    if action not in {'start', 'stop', 'restart', 'install_service'}:
        return jsonify({'error': 'unknown action'}), 404
    body, status = _launcher_call(action)
    return jsonify(body), status


# ============================================================
# Multi-session PTY over a single WebSocket (JSON protocol)
# ============================================================

class PtySession:
    """One pseudo-terminal owned by a single websocket client."""

    def __init__(self, sid: str, shell: str, cols: int, rows: int, loop, send_coro):
        self.id = sid
        self.shell = shell
        self.cols = cols
        self.rows = rows
        self.started_at = time.time()
        self.stop_event = threading.Event()
        self._loop = loop
        self._send_coro = send_coro
        self.proc = None
        self.pid = None
        self.fd = None
        self._reader = None
        self._spawn()

    # ---- platform spawn ----
    def _spawn(self):
        env = os.environ.copy()
        env.update({
            'TERM': 'xterm-256color',
            'PYTHONIOENCODING': 'utf-8',
            'COLUMNS': str(self.cols),
            'LINES': str(self.rows),
            'SUPER_MEMORY_API': SUPER_MEMORY_API,
        })
        argv = self._argv()

        if IS_WINDOWS:
            try:
                import winpty  # type: ignore
                self.proc = winpty.PtyProcess.spawn(argv, dimensions=(self.rows, self.cols), env=env)
                self._kind = 'winpty'
            except ImportError:
                self.proc = subprocess.Popen(
                    argv, env=env,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                )
                self._kind = 'subprocess'
            self._reader = threading.Thread(target=self._pump_windows, daemon=True)
        else:
            import pty
            pid, fd = pty.fork()
            if pid == 0:
                try:
                    os.execvpe(argv[0], argv, env)
                finally:
                    os._exit(127)
            self.pid = pid
            self.fd = fd
            self._kind = 'posix'
            self._apply_winsize()
            self._reader = threading.Thread(target=self._pump_posix, daemon=True)

        self._reader.start()

    def _argv(self):
        if self.shell == 'mem':
            mem_script = str(_resolve_mem_script())
            return [sys.executable, '-u', mem_script, 'help'] if not Path(mem_script).exists() else \
                   [sys.executable, '-i', '-c',
                    f"import sys,subprocess; print('Super Memory CLI. Type a mem subcommand, e.g. `help`.'); "
                    f"\nwhile True:\n  try: line=input('mem> ')\n  except EOFError: break\n"
                    f"  if not line.strip(): continue\n  if line.strip() in ('exit','quit'): break\n"
                    f"  subprocess.call([sys.executable, {mem_script!r}] + line.split())"]
        # default: login shell
        shell_path = None
        if IS_WINDOWS:
            shell_path = shutil.which('bash') or shutil.which('cmd')
            if not shell_path:
                shell_path = 'cmd.exe'
            return [shell_path]
        shell_path = os.environ.get('SHELL') or shutil.which('bash') or shutil.which('sh') or '/bin/sh'
        return [shell_path, '-l']

    def _apply_winsize(self):
        if self.fd is None:
            return
        try:
            import fcntl, termios, struct
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ,
                        struct.pack('HHHH', self.rows, self.cols, 0, 0))
        except (ImportError, OSError):
            pass

    # ---- reader threads ----
    def _deliver(self, data: bytes):
        try:
            text = data.decode('utf-8', errors='replace')
        except UnicodeDecodeError:
            text = data.decode('latin-1', errors='replace')
        msg = json.dumps({'type': 'output', 'id': self.id, 'data': text}, ensure_ascii=False)
        asyncio.run_coroutine_threadsafe(self._send_coro(msg), self._loop)

    def _emit_exit(self, code: int):
        msg = json.dumps({'type': 'exit', 'id': self.id, 'code': code})
        try:
            asyncio.run_coroutine_threadsafe(self._send_coro(msg), self._loop)
        except RuntimeError:
            pass

    def _pump_posix(self):
        import select
        code = 0
        try:
            while not self.stop_event.is_set():
                r, _, _ = select.select([self.fd], [], [], 0.2)
                if not r:
                    continue
                try:
                    data = os.read(self.fd, 4096)
                except OSError:
                    break
                if not data:
                    break
                self._deliver(data)
        finally:
            try:
                _, status = os.waitpid(self.pid, os.WNOHANG)
                if os.WIFEXITED(status):
                    code = os.WEXITSTATUS(status)
            except OSError:
                pass
            self.stop_event.set()
            self._emit_exit(code)

    def _pump_windows(self):
        code = 0
        try:
            while not self.stop_event.is_set():
                if self._kind == 'winpty':
                    try:
                        data = self.proc.read(4096)
                    except Exception:
                        break
                    if not data:
                        break
                    self._deliver(data.encode('utf-8') if isinstance(data, str) else data)
                else:
                    data = self.proc.stdout.read(4096)
                    if not data:
                        break
                    self._deliver(data)
        finally:
            try:
                if self._kind == 'winpty':
                    code = self.proc.exitstatus or 0
                else:
                    code = self.proc.wait(timeout=1) or 0
            except Exception:
                pass
            self.stop_event.set()
            self._emit_exit(code)

    # ---- input / resize / close ----
    def write(self, text: str):
        data = text.encode('utf-8')
        if IS_WINDOWS:
            if self._kind == 'winpty':
                self.proc.write(text)
            else:
                self.proc.stdin.write(data)
                self.proc.stdin.flush()
        else:
            try:
                os.write(self.fd, data)
            except OSError:
                self.stop_event.set()

    def resize(self, cols: int, rows: int):
        self.cols, self.rows = cols, rows
        if IS_WINDOWS and self._kind == 'winpty':
            try:
                self.proc.setwinsize(rows, cols)
            except Exception:
                pass
        else:
            self._apply_winsize()

    def close(self):
        self.stop_event.set()
        try:
            if IS_WINDOWS:
                if self._kind == 'winpty':
                    self.proc.terminate(force=True)
                else:
                    self.proc.kill()
            else:
                import signal as _signal
                try:
                    os.kill(self.pid, _signal.SIGTERM)
                    import select as _select
                    _select.select([], [], [], 2.0)
                except (OSError, ProcessLookupError):
                    pass
                try:
                    os.kill(self.pid, 9)
                except (OSError, ProcessLookupError):
                    pass
                try:
                    os.close(self.fd)
                except OSError:
                    pass
        except (OSError, ProcessLookupError):
            pass

    def info(self):
        return {
            'id': self.id,
            'shell': self.shell,
            'cols': self.cols,
            'rows': self.rows,
            'started_at': self.started_at,
            'alive': not self.stop_event.is_set(),
        }


async def pty_handler(websocket):
    # Token handshake via query string: ws://host/?token=...
    import urllib.parse as _up
    req = getattr(websocket, 'request', None)
    path = getattr(req, 'path', '') if req is not None else getattr(websocket, 'path', '') or ''
    qs = _up.urlparse(path).query
    token = _up.parse_qs(qs).get('token', [''])[0]
    # Accept permanent UI_TOKEN or a short-lived single-use ws-token
    now = time.time()
    _ws_tokens_clean = {t: exp for t, exp in list(_ws_tokens.items()) if exp > now}
    _ws_tokens.clear()
    _ws_tokens.update(_ws_tokens_clean)
    is_ui_token = token and secrets.compare_digest(token, UI_TOKEN)
    is_ws_token = not is_ui_token and token in _ws_tokens
    if not (is_ui_token or is_ws_token):
        try:
            await websocket.send(json.dumps({'type': 'error', 'code': 'unauthorized'}))
        finally:
            await websocket.close(code=4401)
        return
    _ws_tokens.pop(token, None)  # single-use

    loop = asyncio.get_running_loop()
    sessions: dict = {}
    lock = threading.Lock()

    async def send(payload):
        try:
            await websocket.send(payload)
        except Exception:
            pass

    async def send_list():
        with lock:
            items = [s.info() for s in sessions.values()]
        await send(json.dumps({'type': 'sessions', 'items': items}))

    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode('utf-8'))
            except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
                await send(json.dumps({'type': 'error', 'code': 'bad_json'}))
                continue

            mtype = msg.get('type')
            sid = msg.get('id') or ''

            if mtype == 'open':
                sid = sid or uuid.uuid4().hex[:8]
                shell = msg.get('shell', 'bash')
                cols = int(msg.get('cols') or 120)
                rows = int(msg.get('rows') or 30)
                try:
                    sess = PtySession(sid, shell, cols, rows, loop, send)
                except OSError as e:
                    await send(json.dumps({'type': 'error', 'id': sid, 'code': 'spawn_failed', 'message': str(e)}))
                    continue
                with lock:
                    sessions[sid] = sess
                await send(json.dumps({'type': 'opened', 'id': sid, 'shell': shell, 'cols': cols, 'rows': rows}))
                await send_list()

            elif mtype == 'input':
                sess = sessions.get(sid)
                if sess:
                    sess.write(msg.get('data', ''))

            elif mtype == 'resize':
                sess = sessions.get(sid)
                if sess:
                    sess.resize(int(msg.get('cols') or sess.cols), int(msg.get('rows') or sess.rows))

            elif mtype == 'close':
                sess = sessions.pop(sid, None)
                if sess:
                    sess.close()
                await send_list()

            elif mtype == 'list':
                await send_list()

            elif mtype == 'ping':
                await send(json.dumps({'type': 'pong', 't': time.time()}))

            else:
                await send(json.dumps({'type': 'error', 'code': 'unknown_type', 'received': mtype}))
    except Exception as e:
        print(f"pty_handler error: {e}", file=sys.stderr)
    finally:
        with lock:
            items = list(sessions.values())
            sessions.clear()
        for s in items:
            s.close()


@app.route('/api/terminals')
@require_token
def terminals_list():
    return jsonify({'multiplexed': True, 'protocol': 'json'})


_ws_tokens: dict = {}  # short-lived single-use tokens for WS auth


@app.route('/api/ws-token')
@require_token
def ws_token_route():
    tok = secrets.token_urlsafe(16)
    _ws_tokens[tok] = time.time() + 30  # valid for 30 s
    return jsonify({'token': tok})


# ============================================================
# Servers
# ============================================================

def start_websocket_server():
    import websockets

    async def run():
        async with websockets.serve(pty_handler, '127.0.0.1', 5001):
            await asyncio.Future()

    asyncio.run(run())


def start_flask():
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False, threaded=True)


def main():
    import webbrowser

    print('Starting Super Memory Desktop Monitor...')
    print(f'UI token: {UI_TOKEN[:6]}… (stored at {API_TOKEN_PATH})')

    ws_thread = threading.Thread(target=start_websocket_server, daemon=True)
    ws_thread.start()
    print('WebSocket terminal server on ws://127.0.0.1:5001')

    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    time.sleep(1.5)

    url = f'http://127.0.0.1:5000/?token={UI_TOKEN}'
    print(f'Opening browser (token used once for cookie auth, then URL cleans up)')
    webbrowser.open(url)

    print('Flask running. Press Ctrl+C to stop.')
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
