#!/usr/bin/env python3
"""
Super Memory Launcher
====================
Auto-starts the memory agent using the best available method:
1. systemd (Linux with user services)
2. launchd (macOS)
3. Manual background process (fallback)
"""

import os
import sys
import subprocess
import signal
import time
import socket
from pathlib import Path

AGENT_PATH = Path.home() / ".super_memory" / "memory_agent.py"
SERVICE_NAME = "super-memory"
PORT = 8080


def is_port_open(port: int) -> bool:
    """Check if port is already listening."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex(('127.0.0.1', port))
        return result == 0
    finally:
        sock.close()


def is_agent_running() -> bool:
    """Check if agent is already running."""
    if is_port_open(PORT):
        # Try to get health
        import requests
        try:
            resp = requests.get(f'http://127.0.0.1:{PORT}/health', timeout=2)
            return resp.status_code == 200
        except:
            pass
    return False


def start_systemd():
    """Start using systemd user service."""
    service_file = Path.home() / ".config" / "systemd" / "user" / f"{SERVICE_NAME}.service"
    
    if not service_file.exists():
        print(f"❌ Service file not found: {service_file}")
        print("   Run: super-memory install")
        return False
    
    try:
        # Enable and start
        subprocess.run(["systemctl", "--user", "enable", SERVICE_NAME], check=True)
        subprocess.run(["systemctl", "--user", "start", SERVICE_NAME], check=True)
        print("✅ Started via systemd")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ systemd failed: {e}")
        return False


def start_launchd():
    """Start using launchd (macOS)."""
    # macOS implementation would go here
    print("⚠️  launchd not implemented yet")
    return False


def start_background():
    """Start as background process (fallback)."""
    if is_agent_running():
        print("✅ Agent already running on port", PORT)
        return True
    
    # Check if agent exists
    if not AGENT_PATH.exists():
        print(f"❌ Agent not found: {AGENT_PATH}")
        return False
    
    # Start process
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    try:
        # Start in background
        proc = subprocess.Popen(
            [sys.executable, str(AGENT_PATH), "--port", str(PORT)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        
        # Wait for startup
        for i in range(10):
            if is_agent_running():
                print(f"✅ Agent started (PID: {proc.pid})")
                return True
            time.sleep(0.5)
        
        print("⚠️  Agent started but not responding yet")
        return True
        
    except Exception as e:
        print(f"❌ Failed to start: {e}")
        return False


def start():
    """Auto-detect best method and start."""
    if is_agent_running():
        print(f"✅ Super Memory already running on port {PORT}")
        return True
    
    print("🚀 Starting Super Memory Agent...")
    
    # Try systemd first
    if sys.platform == "linux":
        try:
            subprocess.run(["systemctl", "--user", "version"], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            if start_systemd():
                return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    
    # Try launchd on macOS
    if sys.platform == "darwin":
        if start_launchd():
            return True
    
    # Fallback to background process
    return start_background()


def stop():
    """Stop the agent."""
    if not is_agent_running():
        print("Agent not running")
        return True
    
    # Try systemd first
    if sys.platform == "linux":
        try:
            subprocess.run(["systemctl", "--user", "stop", SERVICE_NAME], check=True)
            print("✅ Stopped via systemd")
            return True
        except:
            pass
    
    # Kill by port
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{PORT}"],
            capture_output=True, text=True, check=True
        )
        pids = result.stdout.strip().split('\n')
        for pid in pids:
            if pid:
                os.kill(int(pid), signal.SIGTERM)
        print("✅ Stopped via lsof")
        return True
    except:
        pass
    
    print("⚠️  Could not stop agent (you may need to kill manually)")
    return False


def restart():
    """Restart the agent."""
    stop()
    time.sleep(1)
    return start()


def status():
    """Check agent status."""
    if is_agent_running():
        print(f"✅ Super Memory running on port {PORT}")
        
        # Get stats
        try:
            import requests
            resp = requests.get(f'http://127.0.0.1:{PORT}/summary', timeout=2)
            data = resp.json()
            print(f"   Entries: {data.get('total', '?')}")
            print(f"   Completed: {data.get('completed', '?')}")
            print(f"   Decisions: {data.get('decisions', '?')}")
        except:
            pass
    else:
        print(f"❌ Super Memory not running on port {PORT}")
        print("   Run: super-memory start")


def install_service():
    """Install systemd service file."""
    if sys.platform != "linux":
        print("⚠️  systemd service only works on Linux")
        return False
    
    # Create directories
    systemd_dir = Path.home() / ".config" / "systemd" / "user"
    systemd_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy service file
    source_service = Path(__file__).parent / f"{SERVICE_NAME}.service"
    if not source_service.exists():
        # Try relative to this script
        source_service = Path.home() / ".super_memory" / "daemon" / f"{SERVICE_NAME}.service"
    
    dest_service = systemd_dir / f"{SERVICE_NAME}.service"
    
    if source_service.exists():
        import shutil
        shutil.copy(source_service, dest_service)
        print(f"✅ Installed service to {dest_service}")
        print("   Run: super-memory start")
    else:
        print(f"❌ Service file not found")
        return False
    
    # Reload systemd
    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        print("✅ Reloaded systemd")
    except:
        pass
    
    return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Super Memory Launcher')
    parser.add_argument('command', nargs='?', default='status',
                        choices=['start', 'stop', 'restart', 'status', 'install'])
    args = parser.parse_args()
    
    if args.command == 'start':
        start()
    elif args.command == 'stop':
        stop()
    elif args.command == 'restart':
        restart()
    elif args.command == 'status':
        status()
    elif args.command == 'install':
        install_service()
        start()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
