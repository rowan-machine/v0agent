#!/usr/bin/env python3
# scripts/dev_cli.py
"""
SignalFlow Developer CLI

Quick access to common development operations while coding.
Run: python scripts/dev_cli.py [command]

Commands:
    status          - Show system status
    tickets         - View ticket checklist
    tests           - View test plan status
    release         - View release checklist
    mode [name]     - Get/set current mode
    timer [on|off]  - Toggle mode timer
    meetings        - List recent meetings
    signals         - View signal counts
    errors          - Check for errors
    push            - Push changes to staging
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Try to import rich for better formatting
try:
    from rich.console import Console
    from rich.table import Table
    from rich import box
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    console = None


def print_header(title: str):
    """Print a header."""
    if HAS_RICH:
        console.print(f"\n[bold blue]═══ {title} ═══[/bold blue]\n")
    else:
        print(f"\n═══ {title} ═══\n")


def print_item(key: str, value: str, status: str = ""):
    """Print a key-value item."""
    status_icons = {
        "done": "✅",
        "pending": "⏳",
        "failed": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
    }
    icon = status_icons.get(status, "")
    
    if HAS_RICH:
        console.print(f"  {icon} [cyan]{key}:[/cyan] {value}")
    else:
        print(f"  {icon} {key}: {value}")


def cmd_status():
    """Show system status."""
    print_header("System Status")
    
    # Check local server
    import socket
    def check_port(port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        return result == 0
    
    local_running = check_port(8001)
    print_item("Local Server (8001)", "Running" if local_running else "Stopped", 
               "done" if local_running else "warning")
    
    # Check environment
    env = os.environ.get("ENVIRONMENT", "development")
    print_item("Environment", env, "info")
    
    # Check Supabase
    supabase_url = os.environ.get("SUPABASE_URL", "")
    print_item("Supabase", "Connected" if supabase_url else "Not configured",
               "done" if supabase_url else "warning")
    
    # Git status
    import subprocess
    try:
        branch = subprocess.check_output(["git", "branch", "--show-current"], 
                                         cwd=project_root, text=True).strip()
        print_item("Git Branch", branch, "info")
        
        # Check for uncommitted changes
        status = subprocess.check_output(["git", "status", "--porcelain"],
                                        cwd=project_root, text=True)
        if status:
            changes = len(status.strip().split('\n'))
            print_item("Uncommitted Changes", f"{changes} files", "warning")
        else:
            print_item("Working Directory", "Clean", "done")
    except Exception as e:
        print_item("Git", f"Error: {e}", "failed")
    
    print()


def cmd_tickets():
    """View ticket checklist from the app database."""
    print_header("Sprint Tickets")
    
    try:
        from src.app.infrastructure.supabase_client import get_client
        client = get_client()
        
        if not client:
            print("  ⚠️ Supabase not configured")
            return
        
        result = client.table("tickets").select(
            "ticket_id, title, status, sprint_points, task_decomposition"
        ).eq("in_sprint", True).order("created_at", desc=True).execute()
        
        tickets = result.data
        
        if not tickets:
            print("  No tickets in current sprint")
            return
        
        if HAS_RICH:
            for ticket in tickets:
                status_icons = {
                    'done': '✅', 'in_progress': '🔄', 'in_review': '👁️',
                    'todo': '⬜', 'backlog': '📝', 'blocked': '🚫'
                }
                icon = status_icons.get(ticket['status'], '❓')
                
                console.print(f"\n{icon} [cyan][{ticket['ticket_id']}][/cyan] {ticket['title']}")
                console.print(f"   Status: {ticket['status']} | Points: {ticket.get('sprint_points', 0)}")
                
                # Show checklist
                tasks = ticket.get('task_decomposition')
                if tasks:
                    import json
                    if isinstance(tasks, str):
                        tasks = json.loads(tasks)
                    
                    console.print("   [bold]Checklist:[/bold]")
                    if isinstance(tasks, list):
                        for task in tasks:
                            if isinstance(task, dict):
                                done = task.get('done', task.get('completed', False))
                                name = task.get('name', task.get('task', str(task)))
                            else:
                                done = False
                                name = str(task)
                            check = '✅' if done else '⬜'
                            console.print(f"      {check} {name}")
        else:
            for ticket in tickets:
                icon = "✅" if ticket['status'] == 'done' else "⏳"
                print(f"\n  {icon} [{ticket['ticket_id']}] {ticket['title']}")
                print(f"     Status: {ticket['status']}")
                
    except Exception as e:
        print(f"  Error: {e}")
    
    print()


def cmd_tests():
    """View test cases from ticket task decompositions."""
    print_header("Test Cases (from Tickets)")
    
    try:
        from src.app.infrastructure.supabase_client import get_client
        client = get_client()
        
        if not client:
            print("  ⚠️ Supabase not configured")
            _show_pytest_tests()
            return
        
        result = client.table("tickets").select(
            "ticket_id, title, task_decomposition, tags"
        ).eq("in_sprint", True).execute()
        
        import json
        found_tests = False
        
        for ticket in result.data:
            tasks = ticket.get('task_decomposition', [])
            if isinstance(tasks, str):
                try:
                    tasks = json.loads(tasks)
                except json.JSONDecodeError:
                    tasks = []
            
            # Look for test-related tasks
            test_tasks = []
            if isinstance(tasks, list):
                for task in tasks:
                    task_name = task.get('name', str(task)) if isinstance(task, dict) else str(task)
                    if any(kw in task_name.lower() for kw in ['test', 'verify', 'validate', 'check', 'acceptance', 'qa']):
                        test_tasks.append(task)
            
            if test_tasks:
                found_tests = True
                print(f"\n  📋 [{ticket['ticket_id']}] {ticket['title']}")
                
                for task in test_tasks:
                    if isinstance(task, dict):
                        done = task.get('done', False)
                        name = task.get('name', str(task))
                    else:
                        done = False
                        name = str(task)
                    check = '✅' if done else '⬜'
                    print(f"     {check} {name}")
        
        if not found_tests:
            print("  No test cases found in ticket checklists")
            print("\n  💡 Add tasks with 'test', 'verify', or 'acceptance' in the name")
        
    except Exception as e:
        print(f"  Error: {e}")
        _show_pytest_tests()
    
    print()


def _show_pytest_tests():
    """Fall back to showing pytest test files."""
    print("\n  Falling back to pytest file scan...\n")
    
    import subprocess
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "--collect-only", "-q"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        lines = result.stdout.strip().split('\n')
        if lines:
            last_line = lines[-1]
            print_item("Tests Found", last_line, "info")
    except Exception as e:
        print_item("Test Collection", f"Error: {e}", "failed")
    
    # Show test categories
    import glob
    test_categories = [
        ("Unit Tests", "tests/test_*.py"),
        ("API Tests", "tests/test_api_*.py"),
    ]
    
    for name, pattern in test_categories:
        files = glob.glob(str(project_root / pattern))
        print_item(name, f"{len(files)} files", "info")


def cmd_release():
    """View release checklist from app workflow modes."""
    print_header("Release Checklist")
    
    try:
        from src.app.infrastructure.supabase_client import get_client
        client = get_client()
        
        if not client:
            print("  ⚠️ Supabase not configured")
            # Fall back to defaults
            _show_default_release_checklist()
            return
        
        # Get workflow modes from database
        result = client.table("workflow_modes").select(
            "mode_key, name, icon, steps"
        ).eq("is_active", True).order("sort_order").execute()
        
        modes = result.data
        
        # Look for release/deployment related modes
        release_mode = None
        for mode in modes:
            if any(kw in (mode.get('mode_key') or '').lower() for kw in ['release', 'deploy', 'ship', 'production']):
                release_mode = mode
                break
        
        if release_mode:
            import json
            print(f"\n{release_mode.get('icon', '🚀')} {release_mode['name']}\n")
            steps = release_mode.get('steps', [])
            if isinstance(steps, str):
                steps = json.loads(steps)
            
            done = 0
            for step in steps:
                if isinstance(step, dict):
                    name = step.get('label', step.get('name', str(step)))
                    completed = step.get('completed', step.get('done', False))
                else:
                    name = str(step)
                    completed = False
                
                if completed:
                    done += 1
                check = '✅' if completed else '⬜'
                print(f"  {check} {name}")
            
            print(f"\n  Progress: {done}/{len(steps)}")
        else:
            print("  ⚠️ No release workflow mode found in app")
            _show_default_release_checklist()
            
    except Exception as e:
        print(f"  Error: {e}")
        _show_default_release_checklist()
    
    print()


def _show_default_release_checklist():
    """Show default release checklist when no mode is configured."""
    checklist = [
        ("All tests passing", "pending"),
        ("Version bumped", "pending"),
        ("CHANGELOG updated", "pending"),
        ("Documentation updated", "pending"),
        ("Staging verified", "pending"),
        ("Security scan complete", "pending"),
        ("Performance check", "pending"),
        ("Rollback plan ready", "pending"),
    ]
    
    print("\n  Default checklist (add 'release' workflow mode to customize):\n")
    for task, status in checklist:
        icon = "✅" if status == "done" else "⬜"
        print(f"  {icon} {task}")


def cmd_mode(mode_name: str = None):
    """Get or set current mode."""
    print_header("Mode Control")
    
    # Mode definitions
    modes = {
        "focus": {"duration": 90, "description": "Deep work, no interruptions"},
        "meeting": {"duration": 60, "description": "Meeting mode, capture signals"},
        "review": {"duration": 30, "description": "Code review mode"},
        "break": {"duration": 15, "description": "Break time"},
    }
    
    current_mode = os.environ.get("SIGNALFLOW_MODE", "focus")
    timer_on = os.environ.get("SIGNALFLOW_TIMER", "off") == "on"
    
    if mode_name:
        if mode_name in modes:
            print_item("Mode Set", mode_name, "done")
            print(f"\n  To persist: export SIGNALFLOW_MODE={mode_name}")
        else:
            print_item("Unknown Mode", mode_name, "failed")
            print(f"\n  Available: {', '.join(modes.keys())}")
    else:
        print_item("Current Mode", current_mode, "info")
        print_item("Timer", "On" if timer_on else "Off", "info")
        
        print("\nAvailable Modes:")
        for name, config in modes.items():
            marker = "→" if name == current_mode else " "
            print(f"  {marker} {name}: {config['description']} ({config['duration']}min)")
    
    print()


def cmd_timer(action: str = None):
    """Toggle mode timer."""
    print_header("Mode Timer")
    
    current = os.environ.get("SIGNALFLOW_TIMER", "off")
    
    if action:
        if action.lower() in ("on", "off"):
            print_item("Timer", action.upper(), "done")
            print(f"\n  To persist: export SIGNALFLOW_TIMER={action.lower()}")
        else:
            print_item("Invalid Action", action, "failed")
            print("  Use: timer on | timer off")
    else:
        print_item("Timer Status", current.upper(), "info")
        print("\n  Usage: dev_cli.py timer on | dev_cli.py timer off")
    
    print()


def cmd_meetings():
    """List recent meetings."""
    print_header("Recent Meetings")
    
    try:
        from src.app.infrastructure.supabase_client import get_client
        client = get_client()
        
        if client:
            result = client.table("meetings").select("id, meeting_name, meeting_date, created_at").order("created_at", desc=True).limit(10).execute()
            
            if result.data:
                if HAS_RICH:
                    table = Table(title="Last 10 Meetings", box=box.ROUNDED)
                    table.add_column("Name", style="cyan")
                    table.add_column("Date", style="green")
                    
                    for m in result.data:
                        date = m.get("meeting_date") or m.get("created_at", "")[:10]
                        table.add_row(m.get("meeting_name", "Untitled")[:40], date)
                    
                    console.print(table)
                else:
                    for m in result.data:
                        date = m.get("meeting_date") or m.get("created_at", "")[:10]
                        print(f"  - {m.get('meeting_name', 'Untitled')[:40]} ({date})")
            else:
                print("  No meetings found")
        else:
            print("  Supabase not configured")
    except Exception as e:
        print(f"  Error: {e}")
    
    print()


def cmd_signals():
    """View signal counts."""
    print_header("Signal Statistics")
    
    try:
        from src.app.infrastructure.supabase_client import get_client
        client = get_client()
        
        if client:
            result = client.table("signals").select("signal_type").execute()
            
            if result.data:
                counts = {}
                for s in result.data:
                    t = s.get("signal_type", "unknown")
                    counts[t] = counts.get(t, 0) + 1
                
                total = sum(counts.values())
                print_item("Total Signals", str(total), "info")
                print()
                
                for signal_type, count in sorted(counts.items(), key=lambda x: -x[1]):
                    bar = "█" * min(count, 20)
                    print(f"  {signal_type:15} {bar} {count}")
            else:
                print("  No signals found")
        else:
            print("  Supabase not configured")
    except Exception as e:
        print(f"  Error: {e}")
    
    print()


def cmd_errors():
    """Check for errors."""
    print_header("Error Check")
    
    # Check Python syntax
    import subprocess
    import glob
    
    py_files = glob.glob(str(project_root / "src/**/*.py"), recursive=True)
    errors = []
    
    print(f"Checking {len(py_files)} Python files...")
    
    for filepath in py_files:
        try:
            subprocess.run(
                ["python", "-m", "py_compile", filepath],
                capture_output=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            errors.append((filepath, e.stderr.decode()))
    
    if errors:
        print_item("Syntax Errors", f"{len(errors)} files", "failed")
        for filepath, error in errors[:5]:
            rel_path = Path(filepath).relative_to(project_root)
            print(f"\n  {rel_path}:")
            print(f"    {error[:100]}...")
    else:
        print_item("Syntax Check", "All files OK", "done")
    
    print()


def cmd_push():
    """Push changes to staging."""
    print_header("Push to Staging")
    
    import subprocess
    
    try:
        # Check for changes
        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=project_root, text=True
        )
        
        if status:
            print("Uncommitted changes detected:\n")
            print(status)
            
            response = input("\nStage and commit all changes? [y/N]: ")
            if response.lower() == 'y':
                # Stage all
                subprocess.run(["git", "add", "-A"], cwd=project_root, check=True)
                
                # Commit
                msg = input("Commit message: ")
                subprocess.run(["git", "commit", "-m", msg], cwd=project_root, check=True)
        
        # Push
        print("\nPushing to origin/dev...")
        subprocess.run(["git", "push", "origin", "dev"], cwd=project_root, check=True)
        print_item("Push", "Complete", "done")
        
    except subprocess.CalledProcessError as e:
        print_item("Push", f"Failed: {e}", "failed")
    except KeyboardInterrupt:
        print("\nCancelled")
    
    print()


def cmd_career():
    """View career progress and skills."""
    print_header("Career Progress")
    
    try:
        from src.app.infrastructure.supabase_client import get_client
        client = get_client()
        
        if not client:
            print("  ⚠️ Supabase not configured")
            return
        
        # Get top skills
        skills_result = client.table("skill_tracker").select(
            "skill_name, proficiency_level, projects_count, tickets_count"
        ).order("proficiency_level", desc=True).limit(10).execute()
        
        print("\n📊 Top Skills:")
        for skill in skills_result.data:
            level = skill['proficiency_level']
            bar = "█" * (level // 10) + "░" * (10 - level // 10)
            print(f"  {skill['skill_name']:20} [{bar}] {level}%")
        
        # Get recent career memories
        memories_result = client.table("career_memories").select(
            "memory_type, title, created_at"
        ).order("created_at", desc=True).limit(5).execute()
        
        print("\n\n🏆 Recent Achievements:")
        type_icons = {
            'completed_project': '🎯',
            'ai_implementation': '🤖',
            'skill_milestone': '📈',
            'achievement': '🏆',
            'learning': '📚'
        }
        
        for memory in memories_result.data:
            icon = type_icons.get(memory['memory_type'], '📋')
            print(f"  {icon} {memory['title']}")
            
    except Exception as e:
        print(f"  Error: {e}")
    
    print()


def main():
    parser = argparse.ArgumentParser(
        description="SignalFlow Developer CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Commands
    subparsers.add_parser("status", help="Show system status")
    subparsers.add_parser("tickets", help="View ticket checklist")
    subparsers.add_parser("tests", help="View test plan status")
    subparsers.add_parser("release", help="View release checklist")
    
    mode_parser = subparsers.add_parser("mode", help="Get/set current mode")
    mode_parser.add_argument("name", nargs="?", help="Mode name to set")
    
    timer_parser = subparsers.add_parser("timer", help="Toggle mode timer")
    timer_parser.add_argument("action", nargs="?", choices=["on", "off"], help="on or off")
    
    subparsers.add_parser("meetings", help="List recent meetings")
    subparsers.add_parser("signals", help="View signal counts")
    subparsers.add_parser("career", help="View career progress")
    subparsers.add_parser("errors", help="Check for errors")
    subparsers.add_parser("push", help="Push changes to staging")
    
    args = parser.parse_args()
    
    if not args.command:
        # Default: show status
        cmd_status()
        return
    
    commands = {
        "status": cmd_status,
        "tickets": cmd_tickets,
        "tests": cmd_tests,
        "release": cmd_release,
        "mode": lambda: cmd_mode(args.name if hasattr(args, 'name') else None),
        "timer": lambda: cmd_timer(args.action if hasattr(args, 'action') else None),
        "meetings": cmd_meetings,
        "signals": cmd_signals,
        "career": cmd_career,
        "errors": cmd_errors,
        "push": cmd_push,
    }
    
    if args.command in commands:
        commands[args.command]()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
