"""
Super Memory CLI — Main entry point
Zero-config setup and unified command interface
"""
import sys
import os
import shutil
from pathlib import Path

import typer

app = typer.Typer(
    name="mem",
    help="Super Memory — Universal AI Memory",
    invoke_without_command=True,
)


def safe_print(msg):
    """Print without Rich formatting (Windows-safe)."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'replace').decode())


# Import subcommands
from mem.commands import (
    memory_group,
    daemon_group,
    ui_group,
    agent_group,
    file_group,
    project_group,
)

# Memory commands are top-level (mem add, mem done, etc.)
app.add_typer(memory_group, name="")
# Other groups keep their names
app.add_typer(daemon_group, name="daemon")
app.add_typer(ui_group, name="ui")
app.add_typer(agent_group, name="agent")
app.add_typer(file_group, name="file")
app.add_typer(project_group, name="project")

# Add comp_install AFTER groups
@app.command()
def comp_install(
    shell: str = typer.Option(..., help="Shell type: bash, zsh, fish, powershell"),
):
    """Install shell auto-completion for mem command"""
    if shell == "bash":
        script = """# Add to ~/.bashrc or ~/.bash_profile:
eval "$(_MEM_COMPLETE=bash_source mem)" """
        safe_print(script)
    elif shell == "zsh":
        script = """# Add to ~/.zshrc:
eval "$(_MEM_COMPLETE=zsh_source mem)" """
        safe_print(script)
    elif shell == "fish":
        script = """# Run:
_mem_complete fish | source"""
        safe_print(script)
    elif shell == "powershell":
        script = """# Add to $PROFILE:
Invoke-Expression "$(_MEM_COMPLETE=powershell_source mem)" """
        safe_print(script)
    else:
        safe_print(f"[X] Unsupported shell: {shell}")
        safe_print("Supported: bash, zsh, fish, powershell")
        raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Super Memory — Universal AI Memory CLI"""
    if ctx.invoked_subcommand is None:
        from mem.interactive import interactive_mode
        interactive_mode()


@app.command()
def init():
    """Zero-config setup — initialize Super Memory"""
    from mem import config
    from mem.commands.daemon import start_background, is_port_open, find_free_port, DEFAULT_PORT

    safe_print("=" * 40)
    safe_print("  Super Memory Init")
    safe_print("=" * 40)
    safe_print("")

    # 1. Create ~/.super_memory/
    safe_print("[*] Creating config directory...")
    config.ensure_dir()
    safe_print(f"   [OK] {config.SUPER_MEMORY_DIR}")

    # 2. Check if memory_agent.py exists in repo
    repo_agent = Path(__file__).parent.parent / "memory_agent.py"
    home_agent = config.SUPER_MEMORY_DIR / "memory_agent.py"

    if repo_agent.exists() and not home_agent.exists():
        safe_print("[*] Installing memory_agent.py...")
        shutil.copy(repo_agent, home_agent)
        safe_print(f"   [OK] {home_agent}")

    # 3. Find free port
    port = DEFAULT_PORT
    if is_port_open(port):
        free = find_free_port(8081)
        safe_print(f"   [!] Port {port} busy, using {free}")
        port = free

    # 4. Start daemon
    safe_print(f"[*] Starting daemon on port {port}...")
    os.environ['SUPER_MEMORY_API'] = f'http://127.0.0.1:{port}'

    if home_agent.exists():
        start_background(port, verbose=True)
    else:
        safe_print("[X] memory_agent.py not found!")
        safe_print("   Please install: copy memory_agent.py to ~/.super_memory/")
        raise typer.Exit(1)

    safe_print("")
    safe_print("[OK] Super Memory initialized!")
    safe_print("")
    safe_print("Next steps:")
    safe_print("  mem                     → Interactive menu")
    safe_print("  mem done \"task\"         → Mark task completed")
    safe_print("  mem decision \"choice\"   → Record decision")
    safe_print("  mem daemon status       → Check status")


@app.command()
def status():
    """Quick status check"""
    from mem.commands.daemon import status as daemon_status
    daemon_status()


@app.command()
def inject(
    file: str = typer.Option(None, "--file", "-f", help="Read prompt from file"),
    stdin: bool = typer.Option(False, "--stdin", help="Read from stdin"),
    prompt: str = typer.Option(None, "--prompt", "-p", help="Direct prompt"),
    prefix: str = typer.Option(None, "--prefix", help="Add prefix text"),
    suffix: str = typer.Option(None, "--suffix", help="Add suffix text"),
    summary: bool = typer.Option(False, "--summary", help="Include memory summary"),
):
    """Inject memory context into prompt"""
    from mem import api

    # Get context
    result = api.api_get("/context")
    if api.check_running_hint(result):
        raise typer.Exit(1)
    context = result.get("context", "")

    # Build prompt
    if file:
        try:
            prompt_text = open(file, encoding="utf-8").read()
        except OSError as e:
            safe_print(f"[X] Cannot read file: {e}")
            raise typer.Exit(1)
    elif stdin or not sys.stdin.isatty():
        prompt_text = sys.stdin.read()
    elif prompt:
        prompt_text = prompt
    else:
        safe_print(context or "No context available")
        return

    parts = []
    if prefix:
        parts.append(prefix)
    if context:
        parts.append(context)
    parts.append(prompt_text)
    if suffix:
        parts.append(suffix)
    if summary:
        s = api.api_get("/summary")
        if "error" not in s:
            parts.append(
                f"\n## Memory Summary\n"
                f"Total: {s.get('total', 0)} | "
                f"Completed: {s.get('completed', 0)} | "
                f"Decisions: {s.get('decisions', 0)} | "
                f"Blockers: {s.get('blockers', 0)}"
            )

    safe_print("\n".join(parts))


@app.command()
def mcp():
    """Start MCP server for AI agents (Claude Code, Cursor, etc.)"""
    from mcp_server import run_mcp
    run_mcp()


# Manually register comp_install (workaround for Typer decorator issue)
app.command(name="completion")(comp_install)


if __name__ == "__main__":
    app()
