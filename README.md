# V1 Local Meeting Intake Service

This service stores authoritative meeting syntheses and supporting documents.

## What this version does
- Provides a paste-based UI for meeting summaries
- Stores meeting syntheses verbatim
- Stores full documents (Slack, transcripts, notes)

## What this version does NOT do
- No LLM calls
- No MCP tools
- No task derivation
- No parsing

This version exists to reduce friction and stabilize memory intake.

## Run
uvicorn src.app.main:app --reload

Open:
http://localhost:8000/meetings/new
