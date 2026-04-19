"""
File memory commands: add, list, info, context, search
"""
import typer

file_group = typer.Typer(name="file", help="File memory (MVP 8)")


def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'replace').decode())


def input_prompt(prompt_text: str) -> str:
    try:
        return input(prompt_text)
    except (KeyboardInterrupt, EOFError):
        return ""


@file_group.command()
def add(
    filepath: str = typer.Argument(..., help="File path"),
    purpose: str = typer.Option("", "--purpose", "-p", help="File purpose"),
    description: str = typer.Option("", "--description", "-d", help="Description"),
    patterns: str = typer.Option("", "--patterns", help="Comma-separated patterns"),
):
    """Add file to memory tracking"""
    from .. import api

    patterns_list = [p.strip() for p in patterns.split(',')] if patterns else []

    result = api.api_post("/files/add", {
        "filepath": filepath,
        "purpose": purpose,
        "description": description,
        "patterns": patterns_list,
        "decisions": []
    })
    if api.check_running_hint(result):
        raise typer.Exit(1)
    print(f"[OK] File added: {filepath}")


@file_group.command()
def list():
    """List tracked files"""
    from .. import api
    result = api.api_get("/files/list")
    if api.check_running_hint(result):
        raise typer.Exit(1)

    files = result.get('files', [])
    if not files:
        safe_print("No files tracked yet")
        safe_print("   Run: mem file add /path/to/file.py --purpose \"What this does\"")
        return

    safe_print(f"[F] Tracked files: {len(files)}")
    for f in files[:20]:
        ext = f.get('extension', '')
        purpose = f.get('purpose', '')[:50]
        safe_print(f"  [{ext}] {f.get('filepath', '')}")
        if purpose:
            safe_print(f"         -> {purpose}")

    if len(files) > 20:
        safe_print(f"  ... and {len(files) - 20} more")


@file_group.command()
def info(filepath: str = typer.Argument(..., help="File path")):
    """Get file info"""
    from .. import api
    import json
    result = api.api_get(f"/files/{filepath}/info")
    if api.check_running_hint(result):
        raise typer.Exit(1)

    f = result.get('file', {})
    safe_print(f"\n[F] File: {f.get('filepath', '')}")
    safe_print(f"   Purpose: {f.get('purpose', 'N/A')}")
    safe_print(f"   Description: {f.get('description', 'N/A')}")
    patterns = json.loads(f.get('patterns', '[]'))
    safe_print(f"   Patterns: {', '.join(patterns) if patterns else 'None'}")
    decisions = json.loads(f.get('decisions', '[]'))
    safe_print(f"   Decisions: {', '.join(decisions) if decisions else 'None'}")


@file_group.command()
def context(filepath: str = typer.Argument(..., help="File path")):
    """Get full context for file (file + folder + related memories)"""
    from .. import api
    import json
    result = api.api_get(f"/file_context?path={filepath}")
    if api.check_running_hint(result):
        raise typer.Exit(1)

    file_info = result.get('file')
    folder_info = result.get('folder')
    memories = result.get('related_memories', [])

    safe_print(f"\nContext for: {filepath}")
    safe_print("=" * 50)

    if file_info:
        safe_print(f"\n[F] FILE:")
        safe_print(f"   Purpose: {file_info.get('purpose', 'N/A')}")
        safe_print(f"   Description: {file_info.get('description', 'N/A')}")
        patterns = json.loads(file_info.get('patterns', '[]'))
        safe_print(f"   Patterns: {', '.join(patterns) if patterns else 'None'}")

    if folder_info:
        safe_print(f"\n[F] FOLDER: {folder_info.get('path', '')}")
        safe_print(f"   Purpose: {folder_info.get('purpose', 'N/A')}")
        blockers = json.loads(folder_info.get('blockers', '[]'))
        if blockers:
            safe_print(f"   Blockers: {', '.join(blockers)}")

    if memories:
        safe_print(f"\n[MEMORIES]")
        for m in memories[:3]:
            safe_print(f"   - {m.get('text', '')[:80]}")


@file_group.command()
def search(query: str = typer.Argument(None, help="Search query")):
    """Search tracked files"""
    if not query:
        query = input_prompt("Search files: ")
    if not query:
        print("[X] Query required")
        raise typer.Exit(1)
    from .. import api
    result = api.api_get(f"/files/search?q={query}")
    if api.check_running_hint(result):
        raise typer.Exit(1)

    files = result.get('results', [])
    if not files:
        safe_print(f"No files found for: {query}")
        return

    safe_print(f"Found {len(files)} files for '{query}':")
    for f in files:
        safe_print(f"  {f.get('filepath', '')}")
        if f.get('purpose'):
            safe_print(f"    -> {f.get('purpose', '')[:60]}")