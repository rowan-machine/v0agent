# src/app/domains/workflow/__init__.py
"""
Workflow Domain

Manages workflow modes (A-G), timer sessions, background jobs,
and workflow progress tracking.

Sub-modules:
- modes: Mode settings and suggested mode detection
- progress: Workflow checklist progress
- timer: Timer session management
- jobs: Background job execution
- tracing: LangSmith tracing status

API Routes:
- /api/settings/mode - Get/set current workflow mode
- /api/settings/mode/suggested - Get suggested mode based on sprint cadence
- /api/settings/mode/expected-duration - Get expected durations per mode
- /api/settings/workflow-progress - Save/get workflow checklist progress
- /api/workflow/check-completion - Check if mode workflow is complete
- /api/workflow/overdue-check - Check overdue status
- /api/mode-timer/* - Timer session management
- /api/v1/jobs/* - Background job execution
- /api/v1/tracing/status - LangSmith tracing status
"""

from .api import router as workflow_router

__all__ = ["workflow_router"]
