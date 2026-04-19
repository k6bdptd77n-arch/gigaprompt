"""
Memory commands: add, done, decision, blocked, search, recent, summary, context, tokens, delete, edit
"""
import sys
import typer
from typing import Optional

memory_group = typer.Typer(name="memory", help="Memory operations")


def print_ok(msg):
    print(f"[OK] {msg}")


def print_err(msg):
    print(f"[X] {msg}")


def safe_print(msg):
    """Print without Unicode errors (Windows-safe)."""
    try:
        print(msg)
    except UnicodeEncodeError:
        # Encode to ASCII with replacements before printing
        ascii_msg = msg.encode('ascii', 'replace').decode('ascii')
        print(ascii_msg)


def input_prompt(prompt_text: str) -> str:
    """Safe input prompt."""
    try:
        return input(prompt_text)
    except (KeyboardInterrupt, EOFError):
        return ""


@memory_group.command()
def add(
    text: str = typer.Argument(None, help="Entry text"),
    type: str = typer.Option("general", "--type", "-t", help="Entry type"),
):
    """Add entry to memory"""
    if not text:
        text = input_prompt("Enter text: ")
    if not text:
        print_err("Text required")
        raise typer.Exit(1)
    from .. import api
    result = api.api_post("/add", {"text": text, "type": type, "source": "cli"})
    if api.check_running_hint(result):
        raise typer.Exit(1)
    print_ok(f"Added: {text[:50]}...")


@memory_group.command()
def done(task: Optional[str] = typer.Argument(None, help="Task description")):
    """Mark task completed"""
    if not task:
        task = input_prompt("Task completed: ")
    if not task:
        print_err("Task required")
        raise typer.Exit(1)
    from .. import api
    result = api.api_post("/add_completed", {"task": task, "source": "cli"})
    if api.check_running_hint(result):
        raise typer.Exit(1)
    print_ok(f"Completed: {task[:50]}...")


@memory_group.command()
def decision(
    topic: str = typer.Argument(None, help="Decision topic"),
    choice: Optional[str] = typer.Option(None, "--decision", "-d", help="Decision made"),
    reason: Optional[str] = typer.Option(None, "--reason", "-r", help="Reason"),
):
    """Record a decision"""
    if not topic:
        topic = input_prompt("Decision topic: ")
    if not topic:
        print_err("Topic required")
        raise typer.Exit(1)
    from .. import api
    result = api.api_post("/add_decision", {
        "topic": topic,
        "decision": choice or topic,
        "reason": reason or "",
        "source": "cli"
    })
    if api.check_running_hint(result):
        raise typer.Exit(1)
    print_ok(f"Decision added: {topic[:50]}...")


@memory_group.command()
def blocked(
    task: str = typer.Argument(None, help="Blocked task"),
    blocker: str = typer.Option("unknown", "--blocker", "-b", help="What's blocking"),
    needed: str = typer.Option("TBD", "--needed", "-n", help="What's needed"),
):
    """Add a blocker"""
    if not task:
        task = input_prompt("Blocked task: ")
    if not task:
        print_err("Task required")
        raise typer.Exit(1)
    from .. import api
    result = api.api_post("/add_blocker", {
        "task": task,
        "blocker": blocker,
        "needed": needed,
        "source": "cli"
    })
    if api.check_running_hint(result):
        raise typer.Exit(1)
    print(f"[!] Blocker added: {task[:50]}...")


@memory_group.command()
def search(query: str = typer.Argument(None, help="Search query")):
    """Search memories"""
    if not query:
        query = input_prompt("Search: ")
    if not query:
        print_err("Query required")
        raise typer.Exit(1)
    from urllib.parse import urlencode
    from .. import api
    result = api.api_get(f"/search?{urlencode({'q': query})}")
    if api.check_running_hint(result):
        raise typer.Exit(1)
    results = result.get("results", [])
    if not results:
        safe_print(f"No results for: {query}")
        return
    safe_print(f"Found {len(results)} results:\n")
    for r in results[:10]:
        safe_print(f"[{r.get('type', '?')}] {r.get('text', '')[:80]}")


@memory_group.command()
def recent(limit: int = typer.Option(10, "--limit", "-n", help="Number of entries")):
    """Show recent entries"""
    from .. import api
    result = api.api_get(f"/recent?limit={limit}")
    if api.check_running_hint(result):
        raise typer.Exit(1)
    memories = result.get("memories", [])
    if not memories:
        safe_print("No entries yet")
        return
    for m in memories[:limit]:
        safe_print(f"[{m.get('type', '?')}] {m.get('text', '')[:80]}")


@memory_group.command()
def summary():
    """Show memory summary"""
    from .. import api
    result = api.api_get("/summary")
    if api.check_running_hint(result):
        raise typer.Exit(1)
    safe_print("[S] Memory Summary")
    safe_print("=" * 40)
    safe_print(f"  Total:     {result.get('total', 0)}")
    safe_print(f"  Completed: {result.get('completed', 0)}")
    safe_print(f"  Decisions: {result.get('decisions', 0)}")
    safe_print(f"  Blockers:  {result.get('blockers', 0)}")
    safe_print(f"  Learnings: {result.get('learnings', 0)}")
    if result.get('active_agent'):
        safe_print(f"  Agent:     {result.get('active_agent')}")


@memory_group.command()
def context():
    """Show AI context"""
    from .. import api
    result = api.api_get("/context")
    if api.check_running_hint(result):
        raise typer.Exit(1)
    ctx = result.get("context", "")
    safe_print(ctx or "No context available")


@memory_group.command()
def tokens():
    """Show token usage summary"""
    from .. import api
    result = api.api_get("/tokens/summary")
    if api.check_running_hint(result):
        raise typer.Exit(1)
    safe_print("[S] Token Usage Summary")
    safe_print("=" * 40)
    safe_print(f"  Total Requests:  {result.get('total_requests', 0)}")
    safe_print(f"  Input Tokens:    {result.get('total_input_tokens', 0):,}")
    safe_print(f"  Output Tokens:   {result.get('total_output_tokens', 0):,}")
    safe_print(f"  Estimated Cost:  ${result.get('total_cost_usd', 0):.4f}")
    safe_print(f"  Cache Savings:   ${result.get('total_cache_savings_usd', 0):.2f}")
    models = result.get("models_used", [])
    if models:
        safe_print(f"  Models:          {', '.join(models)}")


@memory_group.command()
def delete(mem_id: int = typer.Argument(..., help="Memory ID")):
    """Delete a memory entry"""
    from .. import api
    result = api.api_post("/memories/delete", {"id": mem_id})
    if api.check_running_hint(result):
        raise typer.Exit(1)
    print_ok(f"Deleted memory #{mem_id}")


@memory_group.command()
def edit(mem_id: int = typer.Argument(..., help="Memory ID"), text: str = typer.Argument(None, help="New text")):
    """Edit a memory entry"""
    if not text:
        text = input_prompt("New text: ")
    if not text:
        print_err("Text required")
        raise typer.Exit(1)
    from .. import api
    result = api.api_post("/memories/edit", {"id": mem_id, "text": text})
    if api.check_running_hint(result):
        raise typer.Exit(1)
    print_ok(f"Updated memory #{mem_id}")