#!/usr/bin/env python3
"""
LangSmith Setup Script for SignalFlow

This script helps you:
1. Verify LangSmith connection
2. Create datasets for evaluation
3. Set up annotation queues (provides instructions)
4. Populate datasets with example data

Usage:
    python scripts/setup_langsmith.py --verify
    python scripts/setup_langsmith.py --create-dataset signals
    python scripts/setup_langsmith.py --list-datasets
    python scripts/setup_langsmith.py --add-examples signals
"""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()


def get_client():
    """Get LangSmith client."""
    try:
        from langsmith import Client
        return Client()
    except ImportError:
        print("❌ langsmith package not installed. Run: pip install langsmith")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to create LangSmith client: {e}")
        sys.exit(1)


def verify_connection():
    """Verify LangSmith connection and show project info."""
    print("🔍 Verifying LangSmith connection...\n")
    
    # Check environment
    api_key = os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")
    tracing_v2 = os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true"
    project = os.environ.get("LANGSMITH_PROJECT") or os.environ.get("LANGCHAIN_PROJECT", "default")
    
    print(f"  API Key Set: {'✅' if api_key else '❌'}")
    print(f"  Tracing V2:  {'✅ Enabled' if tracing_v2 else '⚠️ Disabled'}")
    print(f"  Project:     {project}")
    
    if not api_key:
        print("\n❌ LANGSMITH_API_KEY not set. Get your key from https://smith.langchain.com/settings")
        return False
    
    # Test connection
    client = get_client()
    
    try:
        # List recent runs
        runs = list(client.list_runs(project_name=project, limit=5))
        print(f"\n✅ Connection successful!")
        print(f"   Recent runs in project '{project}': {len(runs)}")
        
        if runs:
            print("\n   Recent traces:")
            for run in runs[:5]:
                print(f"     - {run.name} ({run.run_type}) - {run.start_time}")
        
        # List datasets
        datasets = list(client.list_datasets())
        print(f"\n   Datasets: {len(datasets)}")
        for ds in datasets[:5]:
            print(f"     - {ds.name} ({ds.example_count} examples)")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        return False


def list_datasets():
    """List all datasets."""
    client = get_client()
    datasets = list(client.list_datasets())
    
    print(f"\n📊 Found {len(datasets)} datasets:\n")
    for ds in datasets:
        print(f"  {ds.name}")
        print(f"    ID: {ds.id}")
        print(f"    Examples: {ds.example_count}")
        print(f"    Created: {ds.created_at}")
        print()


def create_dataset(name: str, description: str = None):
    """Create a new dataset."""
    client = get_client()
    
    default_descriptions = {
        "signals": "Signal extraction quality evaluation - tests accuracy of extracted decisions, actions, blockers",
        "dikw": "DIKW knowledge synthesis evaluation - tests promotion from data→info→knowledge→wisdom",
        "assistant": "Arjuna assistant response evaluation - tests helpfulness, accuracy, and action execution",
        "meetings": "Meeting summarization evaluation - tests quality of meeting summaries and signal extraction",
    }
    
    description = description or default_descriptions.get(name, f"Evaluation dataset for {name}")
    
    try:
        dataset = client.create_dataset(
            dataset_name=f"signalflow-{name}",
            description=description,
        )
        print(f"✅ Created dataset: {dataset.name} (ID: {dataset.id})")
        return dataset
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"ℹ️  Dataset signalflow-{name} already exists")
            # Get existing dataset
            datasets = list(client.list_datasets())
            for ds in datasets:
                if ds.name == f"signalflow-{name}":
                    return ds
        else:
            print(f"❌ Failed to create dataset: {e}")
        return None


def add_signal_examples(dataset_name: str = "signalflow-signals"):
    """Add example signals to the dataset for evaluation."""
    client = get_client()
    
    # Example signals with expected evaluations
    examples = [
        {
            "inputs": {
                "signal_text": "We decided to migrate to Supabase by end of Q1",
                "signal_type": "decision",
                "meeting_context": "Technical planning meeting"
            },
            "outputs": {
                "expected_score": 0.9,
                "expected_reasoning": "Clear decision with timeline. Good signal."
            }
        },
        {
            "inputs": {
                "signal_text": "Rowan will update the documentation by Friday",
                "signal_type": "action_item",
                "meeting_context": "Sprint planning"
            },
            "outputs": {
                "expected_score": 0.95,
                "expected_reasoning": "Clear action with owner and deadline. Excellent signal."
            }
        },
        {
            "inputs": {
                "signal_text": "Blocked on API access from vendor",
                "signal_type": "blocker",
                "meeting_context": "Standup"
            },
            "outputs": {
                "expected_score": 0.85,
                "expected_reasoning": "Clear blocker but missing resolution path."
            }
        },
        {
            "inputs": {
                "signal_text": "Maybe we should think about possibly doing something",
                "signal_type": "decision",
                "meeting_context": "Brainstorm"
            },
            "outputs": {
                "expected_score": 0.2,
                "expected_reasoning": "Too vague - not a clear decision."
            }
        },
        {
            "inputs": {
                "signal_text": "Risk: The timeline is aggressive and may slip if integration issues arise",
                "signal_type": "risk",
                "meeting_context": "Project review"
            },
            "outputs": {
                "expected_score": 0.9,
                "expected_reasoning": "Clear risk with context about impact."
            }
        },
    ]
    
    try:
        for example in examples:
            client.create_example(
                dataset_name=dataset_name,
                inputs=example["inputs"],
                outputs=example["outputs"],
            )
        print(f"✅ Added {len(examples)} examples to {dataset_name}")
    except Exception as e:
        print(f"❌ Failed to add examples: {e}")


def add_assistant_examples(dataset_name: str = "signalflow-assistant"):
    """Add example assistant interactions for evaluation."""
    client = get_client()
    
    examples = [
        {
            "inputs": {
                "user_message": "Create a ticket for fixing the login bug",
                "context": {"has_auth": True}
            },
            "outputs": {
                "expected_intent": "create_ticket",
                "expected_response_contains": ["created", "ticket"],
                "expected_score": 0.9
            }
        },
        {
            "inputs": {
                "user_message": "What should I focus on today?",
                "context": {"active_blockers": 2, "overdue_items": 1}
            },
            "outputs": {
                "expected_intent": "focus_recommendations",
                "expected_response_contains": ["focus", "recommend"],
                "expected_score": 0.9
            }
        },
        {
            "inputs": {
                "user_message": "Show me my meetings from last week",
                "context": {}
            },
            "outputs": {
                "expected_intent": "search_meetings",
                "expected_response_contains": ["meeting"],
                "expected_score": 0.85
            }
        },
    ]
    
    try:
        for example in examples:
            client.create_example(
                dataset_name=dataset_name,
                inputs=example["inputs"],
                outputs=example["outputs"],
            )
        print(f"✅ Added {len(examples)} examples to {dataset_name}")
    except Exception as e:
        print(f"❌ Failed to add examples: {e}")


def setup_annotation_queue_instructions():
    """Print instructions for setting up annotation queues in LangSmith UI."""
    project = os.environ.get("LANGSMITH_PROJECT") or os.environ.get("LANGCHAIN_PROJECT", "default")
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    LANGSMITH ANNOTATION QUEUE SETUP                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

Annotation queues let you review and rate LLM outputs to improve quality.
You must set these up manually in the LangSmith UI.

STEPS:

1. 📝 Go to https://smith.langchain.com/

2. 🔍 Navigate to "Annotation Queues" in the left sidebar

3. ➕ Click "New Annotation Queue" and create:

   Queue Name: SignalFlow Signal Review
   Description: Review extracted signals for quality
   Default Dataset: signalflow-signals (created above)
   
   Rubric:
   - signal_quality (1-5): Is this a valid, actionable signal?
   - clarity (1-5): Is the signal clear and unambiguous?
   - completeness (1-5): Does it have owner/deadline/context?

4. ➕ Create another queue:

   Queue Name: SignalFlow Assistant Review  
   Description: Review assistant responses for helpfulness
   Default Dataset: signalflow-assistant
   
   Rubric:
   - helpfulness (1-5): Did the response help the user?
   - accuracy (1-5): Was the information correct?
   - action_success (1-5): Was the requested action completed?

5. 🔄 Set up automation rules to populate queues:

   Go to your project: """ + project + """
   Click "Rules" → "New Rule"
   
   Rule 1: Auto-queue low scores
   - Filter: feedback.score < 0.5
   - Action: Add to SignalFlow Signal Review queue
   
   Rule 2: Auto-queue user thumbs down
   - Filter: feedback.key = "user_feedback" AND feedback.score = 0
   - Action: Add to SignalFlow Assistant Review queue

6. 📊 Review runs in your queues regularly!

   The feedback you provide will be stored with traces and can be
   used to fine-tune prompts and improve agent behavior.
""")


def export_traces_to_dataset(
    dataset_name: str,
    project_name: str = None,
    limit: int = 10,
    filter_feedback: Optional[str] = None,
):
    """Export recent traces to a dataset for offline evaluation."""
    client = get_client()
    project_name = project_name or os.environ.get("LANGSMITH_PROJECT") or os.environ.get("LANGCHAIN_PROJECT", "default")
    
    print(f"📤 Exporting traces from '{project_name}' to '{dataset_name}'...")
    
    try:
        runs = list(client.list_runs(
            project_name=project_name,
            limit=limit,
            # Could add filters here
        ))
        
        exported = 0
        for run in runs:
            if run.inputs and run.outputs:
                try:
                    client.create_example(
                        dataset_name=dataset_name,
                        inputs=run.inputs,
                        outputs=run.outputs,
                    )
                    exported += 1
                except Exception as e:
                    print(f"  Skipped run {run.id}: {e}")
        
        print(f"✅ Exported {exported} traces to {dataset_name}")
        
    except Exception as e:
        print(f"❌ Failed to export: {e}")


def main():
    parser = argparse.ArgumentParser(description="LangSmith Setup for SignalFlow")
    parser.add_argument("--verify", action="store_true", help="Verify LangSmith connection")
    parser.add_argument("--list-datasets", action="store_true", help="List all datasets")
    parser.add_argument("--create-dataset", type=str, help="Create a dataset (signals, dikw, assistant)")
    parser.add_argument("--add-examples", type=str, help="Add example data to dataset")
    parser.add_argument("--queue-instructions", action="store_true", help="Show annotation queue setup instructions")
    parser.add_argument("--export-traces", type=str, help="Export recent traces to a dataset")
    parser.add_argument("--limit", type=int, default=10, help="Limit for trace export")
    parser.add_argument("--setup-all", action="store_true", help="Run full setup: verify + create datasets + add examples")
    
    args = parser.parse_args()
    
    if args.verify:
        verify_connection()
    
    elif args.list_datasets:
        list_datasets()
    
    elif args.create_dataset:
        create_dataset(args.create_dataset)
    
    elif args.add_examples:
        if args.add_examples == "signals":
            add_signal_examples()
        elif args.add_examples == "assistant":
            add_assistant_examples()
        else:
            print(f"Unknown dataset type: {args.add_examples}")
            print("Available: signals, assistant")
    
    elif args.queue_instructions:
        setup_annotation_queue_instructions()
    
    elif args.export_traces:
        export_traces_to_dataset(args.export_traces, limit=args.limit)
    
    elif args.setup_all:
        print("🚀 Running full LangSmith setup...\n")
        
        if not verify_connection():
            sys.exit(1)
        
        print("\n" + "="*60 + "\n")
        
        # Create datasets
        for ds in ["signals", "assistant", "dikw"]:
            create_dataset(ds)
        
        print()
        
        # Add examples
        add_signal_examples()
        add_assistant_examples()
        
        print("\n" + "="*60 + "\n")
        
        # Show queue instructions
        setup_annotation_queue_instructions()
    
    else:
        parser.print_help()
        print("\n💡 Quick start: python scripts/setup_langsmith.py --setup-all")


if __name__ == "__main__":
    main()
