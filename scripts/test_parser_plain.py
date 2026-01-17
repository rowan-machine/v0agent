#!/usr/bin/env python3
# Test parser with plain text format

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.mcp.parser import parse_meeting_summary
from app.mcp.extract import extract_structured_signals


test_text = """Work Identified (candidates, not tasks)
Reallocation Lists UI under Organization Details

File import/export for formulary reallocation lists

Backend ingestion patterns for UI-triggered data loads

Reallocated claims file generation logic

RX messaging enhancements (threads, infinite scroll)


Outcomes
Reallocation Lists confirmed as an Organization-level feature in the UI

Agreement to reuse existing RX claims ingestion patterns for reallocation files

Direction to simplify reallocation logic using highest-rate NDC selection

Messaging work split into spikes vs implementation to manage scope

Acceptance that some tickets will iterate as design stabilizes


Context
RX backlog grooming with product, frontend, and backend engineering.

Session focused on clarifying scope and sequencing for multiple RX tickets already in motion.

Raw notes and UI screenshot add clarity on how reallocation surfaces in the product.


Key Signal (Problem)
Several RX initiatives (reallocation, file ingestion, messaging) intersect UI, backend, and Airflow.
 The core challenge is maintaining consistent ingestion and recalculation semantics without overcomplicating backend architecture or introducing unnecessary variability.

Notes
DEV-8095


Synthesized Signals (Authoritative)
Decision:
Reuse existing RX claims DAG ingestion patterns for reallocation files.

Favor deterministic reallocation outputs to reduce noise across repricing runs.

Treat messaging enhancements as incremental and separable.

Action items:
Proceed with DEV-8095 UI work for Reallocation Lists.

Define q2c endpoints + DAG triggers for DEV-8101 if UI rendering is unnecessary.

Implement DEV-8111 with highest-rate NDC logic and controlled recalculation.

Continue spikes for messaging before locking implementation details.

Blocked:
Architectural clarity on Airflow vs backend services for UI-triggered work.

Messaging scope may change based on spike outcomes.


Risks / Open Questions
Risk of over-reliance on Airflow for synchronous application behavior.

Ensuring reallocation recalculation rules are clearly documented and enforced.

Potential rework if messaging UX requirements expand after spikes.


Commitments
Rowan will align reallocation ingestion with existing RX claims patterns.

Rowan will flag backend architectural concerns early when DAGs are proposed for app flows.

Ideas
Abstract "file ingestion via UI" into a single reusable pattern across RX.

Document recalculation triggers to avoid confusion between repricing variability and data changes.

Treat messaging improvements as UX-driven iterations, not platform refactors.
"""


def test_parser():
    print("=== Parsing plain text format ===\n")
    
    # Parse
    parsed_sections = parse_meeting_summary(test_text)
    
    print("Parsed sections:")
    for key in parsed_sections:
        print(f"  - {key}: {len(parsed_sections[key])} chars")
    
    print("\n")
    
    # Extract signals
    signals = extract_structured_signals(parsed_sections)
    
    print("Extracted signals:")
    print(f"  Decisions: {len(signals['decisions'])}")
    for d in signals['decisions']:
        print(f"    - {d[:80]}...")
    
    print(f"\n  Action items: {len(signals['action_items'])}")
    for a in signals['action_items']:
        print(f"    - {a[:80]}...")
    
    print(f"\n  Blockers: {len(signals['blockers'])}")
    for b in signals['blockers']:
        print(f"    - {b[:80]}...")
    
    print(f"\n  Risks: {len(signals['risks'])}")
    for r in signals['risks']:
        print(f"    - {r[:80]}...")
    
    print(f"\n  Ideas: {len(signals['ideas'])}")
    for i in signals['ideas']:
        print(f"    - {i[:80]}...")
    
    print(f"\n  Context: {len(signals['context'])} chars")
    print(f"  Notes: {len(signals['notes'])} chars")
    print(f"  Key Signals: {len(signals['key_signals'])}")


if __name__ == "__main__":
    test_parser()
