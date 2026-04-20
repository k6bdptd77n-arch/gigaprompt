"""
UI commands: dashboard
"""
import subprocess
import time
import sys
from pathlib import Path
import typer

from mem.print_utils import safe_print

ui_group = typer.Typer(name="ui", help="Web dashboard")


@ui_group.command()
def open(port: int = typer.Option(5000, "--port", "-p", help="Dashboard port")):
    """Open web dashboard"""
    monitor_path = Path(__file__).parent.parent.parent / "desktop_monitor" / "app.py"

    if not monitor_path.exists():
        monitor_path = Path.home() / ".super_memory" / "desktop_monitor" / "app.py"

    if not monitor_path.exists():
        safe_print("[X] desktop_monitor not found.")
        safe_print("   Clone the full repo to use this feature.")
        raise typer.Exit(1)

    safe_print(f"[OK] Starting dashboard on http://127.0.0.1:{port}")

    try:
        import webbrowser
        proc = subprocess.Popen(
            [sys.executable, str(monitor_path), "--port", str(port)],
        )
        time.sleep(2)
        webbrowser.open(f"http://127.0.0.1:{port}")
        proc.wait()
    except KeyboardInterrupt:
        safe_print("\n[OK] Dashboard stopped.")


@ui_group.command()
def dashboard(port: int = typer.Option(5000, "--port", "-p", help="Dashboard port")):
    """Open web dashboard (alias for open)"""
    open(port)