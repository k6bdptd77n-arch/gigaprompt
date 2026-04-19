"""
Daemon commands: start, stop, restart, status, install
"""
import os
import sys
import signal
import socket
import subprocess
import time
from pathlib import Path
import typer

daemon_group = typer.Typer(name="daemon", help="Daemon management")

AGENT_PATH = Path.home() / ".super_memory" / "memory_agent.py"
SERVICE_NAME = "super-memory"
DEFAULT_PORT = 8080


def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'replace').decode())


def is_port_open(port: int) -> bool:
    """Check if port is already listening."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex(('127.0.0.1', port))
        return result == 0
    finally:
        sock.close()


def is_agent_running(port: int = DEFAULT_PORT) -> bool:
    """Check if agent is already running."""
    if is_port_open(port):
        try:
            import urllib.request
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2) as resp:
                return resp.status == 200
        except:
            pass
    return False


def find_free_port(start: int = 8080) -> int:
    """Find a free port starting from start."""
    port = start
    while port < start + 100:
        if not is_port_open(port):
            return port
        port += 1
    return start


def start_background(port: int = DEFAULT_PORT, verbose: bool = False):
    """Start agent as background process."""
    if not AGENT_PATH.exists():
        safe_print(f"[X] Agent not found: {AGENT_PATH}")
        safe_print("    Run: mem init")
        return False

    if is_agent_running(port):
        safe_print(f"[OK] Already running on port {port}")
        return True

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    log_path = Path.home() / ".super_memory" / "agent.log"
    pid_file = Path.home() / ".super_memory" / "agent.pid"

    try:
        proc = subprocess.Popen(
            [sys.executable, str(AGENT_PATH), "--port", str(port)],
            env=env,
            stdout=open(log_path, "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        pid_file.write_text(str(proc.pid))

        # Wait for startup
        for i in range(10):
            time.sleep(0.5)
            if is_agent_running(port):
                if verbose:
                    safe_print(f"[OK] Started (PID: {proc.pid}) on port {port}")
                return True

        safe_print("[!] Started but not responding yet")
        return True
    except Exception as e:
        safe_print(f"[X] Failed to start: {e}")
        return False


@daemon_group.command()
def start(port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="Port to run on")):
    """Start the daemon"""
    if is_agent_running(port):
        safe_print(f"[OK] Already running on port {port}")
        return

    safe_print(f"[*] Starting Super Memory daemon on port {port}...")
    start_background(port, verbose=True)


@daemon_group.command()
def stop():
    """Stop the daemon"""
    from .. import config

    # Try PID file first
    pid_file = config.AGENT_PID
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            pid_file.unlink(missing_ok=True)
            safe_print("[OK] Stopped")
            return
        except (ProcessLookupError, ValueError, OSError):
            pid_file.unlink(missing_ok=True)

    # Try to find and kill by port
    for port in [DEFAULT_PORT, 8081, 8082]:
        if is_port_open(port):
            try:
                if sys.platform == "win32":
                    result = subprocess.run(
                        ["netstat", "-ano"],
                        capture_output=True, text=True
                    )
                    for line in result.stdout.splitlines():
                        if f":{port}" in line and "LISTENING" in line:
                            pid = line.strip().split()[-1]
                            subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
                            safe_print("[OK] Stopped")
                            return
                else:
                    result = subprocess.run(
                        ["lsof", "-ti", f":{port}"],
                        capture_output=True, text=True
                    )
                    if result.returncode == 0:
                        for pid in result.stdout.strip().split('\n'):
                            if pid:
                                os.kill(int(pid), signal.SIGTERM)
                        safe_print("[OK] Stopped")
                        return
            except:
                pass

    safe_print("[-] Not running")


@daemon_group.command()
def restart():
    """Restart the daemon"""
    safe_print("[*] Restarting...")
    stop()
    time.sleep(1)
    start()


@daemon_group.command()
def status():
    """Check daemon status"""
    from .. import api

    if api.is_agent_running():
        safe_print("[OK] Super Memory running")

        result = api.api_get("/summary")
        if "error" not in result:
            safe_print(f"   Entries: {result.get('total', '?')}")
            safe_print(f"   Agent: {result.get('active_agent', 'unknown')}")
    else:
        safe_print("[X] Super Memory not running")
        safe_print("   Run: mem daemon start")


@daemon_group.command()
def install():
    """Install as system service (Linux systemd)"""
    if sys.platform != "linux":
        safe_print("[!] systemd service only works on Linux")
        return

    from .. import config
    config.ensure_dir()

    systemd_dir = Path.home() / ".config" / "systemd" / "user"
    systemd_dir.mkdir(parents=True, exist_ok=True)

    service_content = f"""[Unit]
Description=Super Memory Agent - Universal AI Memory
After=network.target

[Service]
Type=simple
ExecStart={sys.executable} {AGENT_PATH} --port {DEFAULT_PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
"""

    service_file = systemd_dir / f"{SERVICE_NAME}.service"
    service_file.write_text(service_content)
    safe_print(f"[OK] Service installed to {service_file}")
    safe_print("   Run: mem daemon start")