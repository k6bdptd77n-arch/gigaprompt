"""
Interactive menu for Super Memory CLI
Windows-compatible ASCII-only interface
"""
import sys
from urllib.parse import urlencode

# Import from parent package
import mem.api as api
import mem.commands.daemon as daemon_module


def print_safe(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'replace').decode())


def show_menu():
    """Show interactive menu and return choice"""
    print_safe("\n" + "=" * 40)
    print_safe("     Super Memory CLI")
    print_safe("=" * 40)
    print_safe("")
    print_safe("  1. Add completed task")
    print_safe("  2. Record decision")
    print_safe("  3. Add blocker")
    print_safe("  4. Search memories")
    print_safe("  5. Show context")
    print_safe("  6. Summary")
    print_safe("  7. Agent management")
    print_safe("  8. Settings")
    print_safe("  9. Exit")
    print_safe("")
    print_safe("=" * 40)

    try:
        choice = input("Choice (1-9): ").strip()
    except (KeyboardInterrupt, EOFError):
        return 8  # exit

    if choice == "1":
        return 0
    elif choice == "2":
        return 1
    elif choice == "3":
        return 2
    elif choice == "4":
        return 3
    elif choice == "5":
        return 4
    elif choice == "6":
        return 5
    elif choice == "7":
        return 6
    elif choice == "8":
        return 7
    elif choice == "9":
        return 8
    else:
        return -1


def interactive_mode():
    """Run interactive menu loop"""
    # Ensure daemon is running
    if not api.is_agent_running():
        print_safe("[*] Starting Super Memory daemon...")
        daemon_module.start_background(verbose=False)
        print_safe("[OK] Daemon started\n")

    while True:
        try:
            idx = show_menu()

            if idx == -1:
                print_safe("Invalid choice")
                continue

            if idx == 0:  # Add completed task
                try:
                    task = input("Task completed: ").strip()
                except (KeyboardInterrupt, EOFError):
                    continue
                if task:
                    result = api.api_post("/add_completed", {"task": task, "source": "interactive"})
                    if "error" not in result:
                        print_safe(f"[OK] Completed: {task[:50]}...")
                    else:
                        print_safe(f"[X] {result.get('error')}")

            elif idx == 1:  # Decision
                try:
                    topic = input("Decision topic: ").strip()
                except (KeyboardInterrupt, EOFError):
                    continue
                if topic:
                    result = api.api_post("/add_decision", {"topic": topic, "source": "interactive"})
                    if "error" not in result:
                        print_safe(f"[OK] Decision added: {topic[:50]}...")
                    else:
                        print_safe(f"[X] {result.get('error')}")

            elif idx == 2:  # Blocker
                try:
                    task = input("Blocked task: ").strip()
                except (KeyboardInterrupt, EOFError):
                    continue
                if task:
                    result = api.api_post("/add_blocker", {"task": task, "source": "interactive"})
                    if "error" not in result:
                        print_safe(f"[OK] Blocker added: {task[:50]}...")
                    else:
                        print_safe(f"[X] {result.get('error')}")

            elif idx == 3:  # Search
                try:
                    query = input("Search: ").strip()
                except (KeyboardInterrupt, EOFError):
                    continue
                if query:
                    result = api.api_get(f"/search?{urlencode({'q': query})}")
                    if "error" not in result:
                        results = result.get("results", [])
                        if results:
                            print_safe(f"\nFound {len(results)} results")
                            for r in results[:5]:
                                print_safe(f"  [{r.get('type', '?')}] {r.get('text', '')[:60]}")
                        else:
                            print_safe(f"No results for: {query}")
                    else:
                        print_safe(f"[X] {result.get('error')}")

            elif idx == 4:  # Context
                result = api.api_get("/context")
                if "error" not in result:
                    ctx = result.get("context", "")
                    print_safe(ctx or "No context available")
                else:
                    print_safe(f"[X] {result.get('error')}")

            elif idx == 5:  # Summary
                result = api.api_get("/summary")
                if "error" not in result:
                    print_safe("\n[S] Memory Summary")
                    print_safe("=" * 40)
                    print_safe(f"  Total:     {result.get('total', 0)}")
                    print_safe(f"  Completed: {result.get('completed', 0)}")
                    print_safe(f"  Decisions: {result.get('decisions', 0)}")
                    print_safe(f"  Blockers:  {result.get('blockers', 0)}")
                else:
                    print_safe(f"[X] {result.get('error')}")

            elif idx == 6:  # Agent management
                print_safe("\n[Agent Management]")
                result = api.api_get("/agents")
                if "error" not in result:
                    agents = result.get('agents', [])
                    active = result.get('active', 'default')
                    print_safe(f"Active: {active}")
                    for a in agents:
                        marker = " [active]" if a.get('name') == active else ""
                        print_safe(f"  * {a.get('name')}{marker}")
                try:
                    name = input("\nSwitch to agent (or Enter to go back): ").strip()
                    if name:
                        result = api.api_post("/agents/select", {"name": name})
                        if "error" not in result:
                            print_safe(f"[OK] Switched to: {name}")
                        else:
                            print_safe(f"[X] {result.get('error')}")
                except (KeyboardInterrupt, EOFError):
                    pass

            elif idx == 7:  # Settings
                print_safe("\n[Settings]")
                print_safe("  1. Check daemon status")
                print_safe("  2. Restart daemon")
                print_safe("  3. Open dashboard")
                try:
                    choice = input("Choice (1-3): ").strip()
                except (KeyboardInterrupt, EOFError):
                    continue
                if choice == "1":
                    daemon_module.status()
                elif choice == "2":
                    daemon_module.restart()
                elif choice == "3":
                    print_safe("[OK] Opening dashboard...")

            elif idx == 8:  # Exit
                print_safe("[OK] Bye!")
                break

            print_safe("")

        except KeyboardInterrupt:
            print_safe("\n[OK] Bye!")
            break
        except Exception as e:
            print_safe(f"[X] Error: {e}")


def print_safe(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'replace').decode())


def show_menu():
    """Show interactive menu and return choice"""
    print_safe("\n" + "=" * 40)
    print_safe("     Super Memory CLI")
    print_safe("=" * 40)
    print_safe("")
    print_safe("  1. Add completed task")
    print_safe("  2. Record decision")
    print_safe("  3. Add blocker")
    print_safe("  4. Search memories")
    print_safe("  5. Show context")
    print_safe("  6. Summary")
    print_safe("  7. Agent management")
    print_safe("  8. Settings")
    print_safe("  9. Exit")
    print_safe("")
    print_safe("=" * 40)

    try:
        choice = input("Choice (1-9): ").strip()
    except (KeyboardInterrupt, EOFError):
        return 8  # exit

    if choice == "1":
        return 0
    elif choice == "2":
        return 1
    elif choice == "3":
        return 2
    elif choice == "4":
        return 3
    elif choice == "5":
        return 4
    elif choice == "6":
        return 5
    elif choice == "7":
        return 6
    elif choice == "8":
        return 7
    elif choice == "9":
        return 8
    else:
        return -1


def interactive_mode():
    """Run interactive menu loop"""
    # Ensure daemon is running
    if not api.is_agent_running():
        print_safe("[*] Starting Super Memory daemon...")
        start_background(verbose=False)
        print_safe("[OK] Daemon started\n")

    while True:
        try:
            idx = show_menu()

            if idx == -1:
                print_safe("Invalid choice")
                continue

            if idx == 0:  # Add completed task
                try:
                    task = input("Task completed: ").strip()
                except (KeyboardInterrupt, EOFError):
                    continue
                if task:
                    result = api.api_post("/add_completed", {"task": task, "source": "interactive"})
                    if "error" not in result:
                        print_safe(f"[OK] Completed: {task[:50]}...")
                    else:
                        print_safe(f"[X] {result.get('error')}")

            elif idx == 1:  # Decision
                try:
                    topic = input("Decision topic: ").strip()
                except (KeyboardInterrupt, EOFError):
                    continue
                if topic:
                    result = api.api_post("/add_decision", {"topic": topic, "source": "interactive"})
                    if "error" not in result:
                        print_safe(f"[OK] Decision added: {topic[:50]}...")
                    else:
                        print_safe(f"[X] {result.get('error')}")

            elif idx == 2:  # Blocker
                try:
                    task = input("Blocked task: ").strip()
                except (KeyboardInterrupt, EOFError):
                    continue
                if task:
                    result = api.api_post("/add_blocker", {"task": task, "source": "interactive"})
                    if "error" not in result:
                        print_safe(f"[OK] Blocker added: {task[:50]}...")
                    else:
                        print_safe(f"[X] {result.get('error')}")

            elif idx == 3:  # Search
                try:
                    query = input("Search: ").strip()
                except (KeyboardInterrupt, EOFError):
                    continue
                if query:
                    from urllib.parse import urlencode
                    result = api.api_get(f"/search?{urlencode({'q': query})}")
                    if "error" not in result:
                        results = result.get("results", [])
                        if results:
                            print_safe(f"\nFound {len(results)} results")
                            for r in results[:5]:
                                print_safe(f"  [{r.get('type', '?')}] {r.get('text', '')[:60]}")
                        else:
                            print_safe(f"No results for: {query}")
                    else:
                        print_safe(f"[X] {result.get('error')}")

            elif idx == 4:  # Context
                result = api.api_get("/context")
                if "error" not in result:
                    ctx = result.get("context", "")
                    print_safe(ctx or "No context available")
                else:
                    print_safe(f"[X] {result.get('error')}")

            elif idx == 5:  # Summary
                result = api.api_get("/summary")
                if "error" not in result:
                    print_safe("\n[S] Memory Summary")
                    print_safe("=" * 40)
                    print_safe(f"  Total:     {result.get('total', 0)}")
                    print_safe(f"  Completed: {result.get('completed', 0)}")
                    print_safe(f"  Decisions: {result.get('decisions', 0)}")
                    print_safe(f"  Blockers:  {result.get('blockers', 0)}")
                else:
                    print_safe(f"[X] {result.get('error')}")

            elif idx == 6:  # Agent management
                print_safe("\n[Agent Management]")
                result = api.api_get("/agents")
                if "error" not in result:
                    agents = result.get('agents', [])
                    active = result.get('active', 'default')
                    print_safe(f"Active: {active}")
                    for a in agents:
                        marker = " [active]" if a.get('name') == active else ""
                        print_safe(f"  * {a.get('name')}{marker}")
                try:
                    name = input("\nSwitch to agent (or Enter to go back): ").strip()
                    if name:
                        result = api.api_post("/agents/select", {"name": name})
                        if "error" not in result:
                            print_safe(f"[OK] Switched to: {name}")
                        else:
                            print_safe(f"[X] {result.get('error')}")
                except (KeyboardInterrupt, EOFError):
                    pass

            elif idx == 7:  # Settings
                print_safe("\n[Settings]")
                print_safe("  1. Check daemon status")
                print_safe("  2. Restart daemon")
                print_safe("  3. Open dashboard")
                try:
                    choice = input("Choice (1-3): ").strip()
                except (KeyboardInterrupt, EOFError):
                    continue
                if choice == "1":
                    from .daemon import status
                    status()
                elif choice == "2":
                    from .daemon import restart
                    restart()
                elif choice == "3":
                    print_safe("[OK] Opening dashboard...")

            elif idx == 8:  # Exit
                print_safe("[OK] Bye!")
                break

            print_safe("")

        except KeyboardInterrupt:
            print_safe("\n[OK] Bye!")
            break
        except Exception as e:
            print_safe(f"[X] Error: {e}")