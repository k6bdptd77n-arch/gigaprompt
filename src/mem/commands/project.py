"""
Project commands: add, list
"""
import typer

from mem.print_utils import safe_print

project_group = typer.Typer(name="project", help="Project management")


@project_group.command()
def add(
    name: str = typer.Argument(..., help="Project name"),
    root_path: str = typer.Option("", "--root", "-r", help="Root path"),
    architecture: str = typer.Option("", "--architecture", "-a", help="Architecture description"),
):
    """Add or update project"""
    from .. import api
    result = api.api_post("/projects/add", {
        "name": name,
        "root_path": root_path,
        "architecture": architecture,
        "key_decisions": []
    })
    if api.check_running_hint(result):
        raise typer.Exit(1)
    print(f"[OK] Project added: {name}")


@project_group.command()
def list():
    """List tracked projects"""
    from .. import api
    result = api.api_get("/projects/list")
    if api.check_running_hint(result):
        raise typer.Exit(1)

    projects = result.get('projects', [])
    if not projects:
        safe_print("No projects tracked yet")
        safe_print("   Run: mem project add my-project --root /path/to/project")
        return

    safe_print(f"Projects: {len(projects)}")
    for p in projects:
        arch = p.get('architecture', '')[:50]
        safe_print(f"  {p.get('name', '')}")
        if arch:
            safe_print(f"    -> {arch}")