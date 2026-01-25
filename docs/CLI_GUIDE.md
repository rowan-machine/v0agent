# SignalFlow Developer CLI Guide

Quick command-line access to your SignalFlow data without leaving VS Code.

## Installation

### Prerequisites
- Python 3.11+
- SignalFlow repository cloned
- Environment variables configured (see below)

### Quick Setup

```bash
# From the project root
cd /path/to/v0agent

# Install dependencies (if not already done)
pip install -r requirements.txt

# Optional: Install rich for better formatting
pip install rich

# Set environment variables
export SUPABASE_URL="your-supabase-url"
export SUPABASE_KEY="your-supabase-key"
```

### Add to PATH (Optional)

For quick access from anywhere:

```bash
# Create alias in your shell profile (.zshrc or .bashrc)
echo 'alias sf="python /path/to/v0agent/scripts/dev_cli.py"' >> ~/.zshrc
source ~/.zshrc
```

Now you can use `sf status` instead of `python scripts/dev_cli.py status`.

## Usage

### Basic Commands

```bash
# Show all commands
python scripts/dev_cli.py --help

# System status overview
python scripts/dev_cli.py status

# View your sprint tickets
python scripts/dev_cli.py tickets

# Check test status
python scripts/dev_cli.py tests

# View release checklist
python scripts/dev_cli.py release
```

### Ticket Management

```bash
# View current sprint tickets with checklists
python scripts/dev_cli.py tickets

# Filter by status
python scripts/dev_cli.py tickets --status in_progress
python scripts/dev_cli.py tickets --status todo

# Show ticket details with full checklist
python scripts/dev_cli.py tickets --detail TICKET-123
```

### Mode Control

Manage your focus mode without opening the app:

```bash
# View current mode
python scripts/dev_cli.py mode

# Set focus mode
python scripts/dev_cli.py mode focus

# Available modes: focus, meeting, review, break
python scripts/dev_cli.py mode meeting

# Toggle timer
python scripts/dev_cli.py timer on
python scripts/dev_cli.py timer off
```

### Data Views

```bash
# Recent meetings
python scripts/dev_cli.py meetings

# Signal statistics
python scripts/dev_cli.py signals

# Career progress
python scripts/dev_cli.py career
```

### Git & Deployment

```bash
# Check for syntax errors
python scripts/dev_cli.py errors

# Push to staging (interactive)
python scripts/dev_cli.py push
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SUPABASE_URL` | Your Supabase project URL | Yes |
| `SUPABASE_KEY` | Supabase anon/service key | Yes |
| `SIGNALFLOW_MODE` | Persist current mode | No |
| `SIGNALFLOW_TIMER` | Timer on/off state | No |
| `ENVIRONMENT` | development/staging/production | No |

## VS Code Integration

### Terminal Task

Add to `.vscode/tasks.json`:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "SF: Status",
      "type": "shell",
      "command": "python scripts/dev_cli.py status",
      "problemMatcher": []
    },
    {
      "label": "SF: Tickets",
      "type": "shell",
      "command": "python scripts/dev_cli.py tickets",
      "problemMatcher": []
    }
  ]
}
```

### Keyboard Shortcuts

Add to `keybindings.json`:

```json
[
  {
    "key": "ctrl+shift+t",
    "command": "workbench.action.tasks.runTask",
    "args": "SF: Tickets"
  }
]
```

## Output Examples

### Status Command
```
═══ System Status ═══

  ✅ Local Server (8001): Running
  ℹ️ Environment: development
  ✅ Supabase: Connected
  ℹ️ Git Branch: dev
  ✅ Working Directory: Clean
```

### Tickets Command
```
═══ Sprint Tickets ═══

┌──────────────────────────────────────────────────┐
│ DEV-1234: Implement user authentication          │
├──────────────────────────────────────────────────┤
│ Status: in_progress    Points: 5                 │
│ ✅ Set up auth provider                          │
│ ✅ Create login screen                           │
│ ⏳ Add token refresh                             │
│ ⬜ Write tests                                   │
└──────────────────────────────────────────────────┘
```

## Troubleshooting

### "Supabase not configured"
Set the environment variables:
```bash
export SUPABASE_URL="https://xxx.supabase.co"
export SUPABASE_KEY="your-key-here"
```

### "No module named 'rich'"
Install optional dependency for better output:
```bash
pip install rich
```

### "Connection refused"
The local server isn't running. Start it with:
```bash
python -m uvicorn src.app.main:app --host 0.0.0.0 --port 8001 --reload
```

## Quick Reference

| Command | Description |
|---------|-------------|
| `status` | System overview |
| `tickets` | Sprint tickets with checklists |
| `tests` | Test plan status |
| `release` | Release checklist |
| `mode [name]` | Get/set focus mode |
| `timer [on\|off]` | Toggle mode timer |
| `meetings` | Recent meetings |
| `signals` | Signal statistics |
| `errors` | Check for syntax errors |
| `push` | Push to staging |
| `career` | Career progress |

---

*This CLI is for development mode only. For full functionality, use the SignalFlow mobile or web app.*
