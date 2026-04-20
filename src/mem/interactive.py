"""
Interactive menu for Super Memory CLI
Windows-compatible ASCII-only interface
"""
import sys
from urllib.parse import urlencode

from mem.print_utils import safe_print, print_safe
import mem.api as api
import mem.commands.daemon as daemon_module


# Menu options mapping: letter -> (index, description)
MENU_OPTIONS = [
    ("a", 0, "Add completed task"),
    ("d", 1, "Record decision"),
    ("b", 2, "Add blocker"),
    ("s", 3, "Search memories"),
    ("c", 4, "Show context"),
    ("m", 5, "Summary"),
    ("g", 6, "Agent management"),
    ("e", 7, "Settings"),
    ("x", 8, "Exit"),
]


def show_menu():
    """Show interactive menu and return choice index"""
    print_safe("\n" + "=" * 40)
    print_safe("     Super Memory CLI")
    print_safe("=" * 40)
    print_safe("")

    for letter, idx, desc in MENU_OPTIONS:
        print_safe(f"  {letter}. {desc}")

    print_safe("")
    print_safe("=" * 40)

    try:
        choice = input("Choice (letter or number): ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        return 8  # exit

    # Check letter shortcuts first
    for letter, idx, desc in MENU_OPTIONS:
        if choice == letter:
            return idx

    # Check number shortcuts (1-9)
    if choice.isdigit():
        num = int(choice)
        if 1 <= num <= 9:
            # Map 1->0, 2->1, ... 9->8
            return num - 1
        elif num == 0:
            return 8  # 0 also means exit

    return -1  # invalid


def interactive_mode():
    """Run interactive menu loop"""
    # Ensure daemon is running
    if not api.is_agent_running():
        safe_print("[*] Starting Super Memory daemon...")
        daemon_module.start_background(verbose=False)
        safe_print("[OK] Daemon started\n")

    while True:
        try:
            idx = show_menu()

            if idx == -1:
                safe_print("Invalid choice. Press a letter (a-e) or number (1-9)")
                continue

            # Add completed task
            if idx == 0:
                try:
                    task = input("Task completed: ").strip()
                except (KeyboardInterrupt, EOFError):
                    continue
                if task:
                    result = api.api_post("/add_completed", {"task": task, "source": "interactive"})
                    if "error" not in result:
                        safe_print(f"[OK] Completed: {task[:50]}...")
                    else:
                        safe_print(f"[X] {result.get('error')}")

            # Decision
            elif idx == 1:
                try:
                    topic = input("Decision topic: ").strip()
                except (KeyboardInterrupt, EOFError):
                    continue
                if topic:
                    result = api.api_post("/add_decision", {"topic": topic, "source": "interactive"})
                    if "error" not in result:
                        safe_print(f"[OK] Decision added: {topic[:50]}...")
                    else:
                        safe_print(f"[X] {result.get('error')}")

            # Blocker
            elif idx == 2:
                try:
                    task = input("Blocked task: ").strip()
                except (KeyboardInterrupt, EOFError):
                    continue
                if task:
                    result = api.api_post("/add_blocker", {"task": task, "source": "interactive"})
                    if "error" not in result:
                        safe_print(f"[OK] Blocker added: {task[:50]}...")
                    else:
                        safe_print(f"[X] {result.get('error')}")

            # Search
            elif idx == 3:
                try:
                    query = input("Search: ").strip()
                except (KeyboardInterrupt, EOFError):
                    continue
                if query:
                    result = api.api_get(f"/search?{urlencode({'q': query})}")
                    if "error" not in result:
                        results = result.get("results", [])
                        if results:
                            safe_print(f"\nFound {len(results)} results")
                            for r in results[:5]:
                                safe_print(f"  [{r.get('type', '?')}] {r.get('text', '')[:60]}")
                            if len(results) > 5:
                                safe_print(f"  ... and {len(results) - 5} more (use 'mem search \"{query}\"' for full list)")
                        else:
                            safe_print(f"No results for: {query}")
                    else:
                        safe_print(f"[X] {result.get('error')}")

            # Context
            elif idx == 4:
                result = api.api_get("/context")
                if "error" not in result:
                    ctx = result.get("context", "")
                    safe_print(ctx or "No context available")
                else:
                    safe_print(f"[X] {result.get('error')}")

            # Summary
            elif idx == 5:
                result = api.api_get("/summary")
                if "error" not in result:
                    safe_print("\n[S] Memory Summary")
                    safe_print("=" * 40)
                    safe_print(f"  Total:     {result.get('total', 0)}")
                    safe_print(f"  Completed: {result.get('completed', 0)}")
                    safe_print(f"  Decisions: {result.get('decisions', 0)}")
                    safe_print(f"  Blockers: {result.get('blockers', 0)}")
                else:
                    safe_print(f"[X] {result.get('error')}")

            # Agent management
            elif idx == 6:
                safe_print("\n[Agent Management]")
                result = api.api_get("/agents")
                if "error" not in result:
                    agents = result.get('agents', [])
                    active = result.get('active', 'default')
                    safe_print(f"Active: {active}")
                    for a in agents:
                        marker = " [active]" if a.get('name') == active else ""
                        safe_print(f"  * {a.get('name')}{marker}")
                try:
                    name = input("\nSwitch to agent (or Enter to go back): ").strip()
                    if name:
                        result = api.api_post("/agents/select", {"name": name})
                        if "error" not in result:
                            safe_print(f"[OK] Switched to: {name}")
                        else:
                            safe_print(f"[X] {result.get('error')}")
                except (KeyboardInterrupt, EOFError):
                    pass

            # Settings
            elif idx == 7:
                safe_print("\n[Settings]")
                safe_print("  1. Check daemon status")
                safe_print("  2. Restart daemon")
                safe_print("  3. Open dashboard")
                try:
                    choice = input("Choice (1-3): ").strip()
                except (KeyboardInterrupt, EOFError):
                    continue
                if choice == "1":
                    daemon_module.status()
                elif choice == "2":
                    daemon_module.restart()
                elif choice == "3":
                    import webbrowser
                    safe_print("[OK] Opening dashboard...")
                    webbrowser.open("http://127.0.0.1:5000")

            # Exit
            elif idx == 8:
                safe_print("[OK] Bye!")
                break

            safe_print("")

        except KeyboardInterrupt:
            safe_print("\n[OK] Bye!")
            break
        except Exception as e:
            safe_print(f"[X] Error: {e}")
