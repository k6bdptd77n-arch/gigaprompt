"""
Agent commands: list, add, use, remove, info
"""
import typer

from mem.print_utils import safe_print

agent_group = typer.Typer(name="agent", help="Multi-agent management")


@agent_group.command()
def list():
    """List all agents"""
    from .. import api
    result = api.api_get("/agents")
    if api.check_running_hint(result):
        raise typer.Exit(1)

    agents = result.get('agents', [])
    active = result.get('active', 'default')

    if not agents:
        safe_print("No agents configured")
        safe_print("   Run: mem agent add <name> --type claude")
        return

    safe_print(f"[Agents: {len(agents)}]")
    for a in agents:
        name = a.get('name', '')
        marker = " [active]" if name == active else ""
        agent_type = a.get('agent_type', 'unknown')
        model = a.get('model', '')
        safe_print(f"  * {name}{marker}")
        safe_print(f"    Type: {agent_type}")
        if model:
            safe_print(f"    Model: {model}")


@agent_group.command()
def add(
    name: str = typer.Argument(..., help="Agent name"),
    agent_type: str = typer.Option("claude", "--type", "-t", help="Agent type"),
    model: str = typer.Option("", "--model", "-m", help="Model"),
    api_key: str = typer.Option("", "--api-key", help="API key"),
    api_url: str = typer.Option("", "--api-url", help="API URL"),
):
    """Add a new agent"""
    from .. import api
    result = api.api_post("/agents/add", {
        "name": name,
        "type": agent_type,
        "api_key": api_key,
        "api_url": api_url,
        "model": model,
        "config": {}
    })
    if api.check_running_hint(result):
        raise typer.Exit(1)
    print(f"[OK] Agent added: {name}")


@agent_group.command()
def use(name: str = typer.Argument(..., help="Agent name")):
    """Switch active agent"""
    from .. import api
    result = api.api_post("/agents/select", {"name": name})
    if api.check_running_hint(result):
        raise typer.Exit(1)
    print(f"[OK] Active agent: {name}")


@agent_group.command()
def remove(name: str = typer.Argument(..., help="Agent name")):
    """Remove an agent"""
    if name == 'default':
        print("[X] Cannot delete 'default' agent")
        raise typer.Exit(1)
    from .. import api
    result = api.api_post("/agents/delete", {"name": name})
    if api.check_running_hint(result):
        raise typer.Exit(1)
    print(f"[OK] Agent deleted: {name}")


@agent_group.command()
def info(name: str = typer.Argument("default", help="Agent name")):
    """Get agent info"""
    from .. import api
    result = api.api_get(f"/agents/{name}")
    if api.check_running_hint(result):
        raise typer.Exit(1)
    a = result.get('agent', {})
    safe_print(f"\nAgent: {a.get('name', '')}")
    safe_print(f"  Type: {a.get('agent_type', 'N/A')}")
    safe_print(f"  Model: {a.get('model', 'N/A')}")
    safe_print(f"  API URL: {a.get('api_url', 'N/A')}")
    safe_print(f"  Created: {a.get('created_at', 'N/A')}")