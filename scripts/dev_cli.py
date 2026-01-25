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
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Try to import rich for better formatting
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
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
    """View ticket checklist."""
    print_header("Ticket Checklist")
    
    # This would typically load from a file or database
    checklist = [
        ("Review PR", "pending"),
        ("Write tests", "pending"),
        ("Update documentation", "pending"),
        ("Run integration tests", "pending"),
        ("Deploy to staging", "pending"),
        ("Verify staging", "pending"),
        ("Merge to main", "pending"),
    ]
    
    if HAS_RICH:
        table = Table(title="Current Sprint Tasks", box=box.ROUNDED)
        table.add_column("Task", style="cyan")
        table.add_column("Status", style="green")
        
        for task, status in checklist:
            icon = "✅" if status == "done" else "⏳"
            table.add_row(task, f"{icon} {status}")
        
        console.print(table)
    else:
        for task, status in checklist:
            icon = "✅" if status == "done" else "⏳"
            print(f"  {icon} {task}: {status}")
    
    print()


def cmd_tests():
    """View test plan status."""
    print_header("Test Plan Status")
    
    # Run pytest --collect-only to get test count
    import subprocess
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "--collect-only", "-q"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Parse output for test count
        lines = result.stdout.strip().split('\n')
        if lines:
            last_line = lines[-1]
            print_item("Tests Found", last_line, "info")
    except Exception as e:
        print_item("Test Collection", f"Error: {e}", "failed")
    
    # Show test categories
    test_categories = [
        ("Unit Tests", "tests/test_*.py"),
        ("API Tests", "tests/test_api_*.py"),
        ("Integration Tests", "tests/test_*_integration.py"),
    ]
    
    import glob
    for name, pattern in test_categories:
        files = glob.glob(str(project_root / pattern))
        print_item(name, f"{len(files)} files", "info")
    
    print("\nRun tests: python -m pytest -v")
    print()


def cmd_release():
    """View release checklist."""
    print_header("Release Checklist")
    
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
    
    done = sum(1 for _, s in checklist if s == "done")
    total = len(checklist)
    
    if HAS_RICH:
        console.print(f"[bold]Progress: {done}/{total}[/bold]\n")
        
        for task, status in checklist:
            icon = "✅" if status == "done" else "⬜"
            console.print(f"  {icon} {task}")
    else:
        print(f"Progress: {done}/{total}\n")
        for task, status in checklist:
            icon = "✅" if status == "done" else "⬜"
            print(f"  {icon} {task}")
    
    print()


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
        "errors": cmd_errors,
        "push": cmd_push,
    }
    
    if args.command in commands:
        commands[args.command]()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
