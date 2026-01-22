#!/usr/bin/env python3
"""
Quick test to verify LangSmith tracing is working.

Run: python -m src.app.test_tracing
"""

import asyncio
import os
from pathlib import Path

# Load env vars
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from src.app.tracing import (
    is_tracing_enabled,
    traced_llm_call,
    TracingContext,
    get_langsmith_client,
    get_project_name,
    start_thread,
)


async def test_basic_tracing():
    """Test basic traced LLM call."""
    print("\n🧪 Test 1: Basic Traced LLM Call")
    print(f"   Tracing enabled: {is_tracing_enabled()}")
    print(f"   Project: {get_project_name()}")
    
    if not is_tracing_enabled():
        print("   ⚠️  Tracing not enabled. Set LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY")
        return False
    
    client = get_langsmith_client()
    if not client:
        print("   ❌ Failed to create LangSmith client")
        return False
    
    print("   ✅ LangSmith client initialized")
    
    # Make a traced call
    thread_id = start_thread(agent_name="TestAgent")
    response = await traced_llm_call(
        prompt="Say 'Hello from SignalFlow tracing test!' in exactly those words.",
        agent_name="TestAgent",
        model="gpt-4o-mini",
        thread_id=thread_id,
        task_type="test",
        tags=["test", "verification"],
    )
    
    print(f"   Response: {response[:100]}...")
    print(f"   ✅ Traced call completed. Check LangSmith dashboard for trace.")
    return True


async def test_context_manager():
    """Test TracingContext for multi-step operations."""
    print("\n🧪 Test 2: Multi-Step Tracing Context")
    
    if not is_tracing_enabled():
        print("   ⚠️  Skipping (tracing not enabled)")
        return False
    
    async with TracingContext(
        agent_name="DIKWSynthesizer",
        thread_id="test-thread-123",
        task_type="synthesis",
    ) as ctx:
        # Step 1
        step1_id = ctx.trace_step(
            step_name="extract_signals",
            inputs={"meeting_text": "Test meeting content..."},
            model="gpt-4o-mini",
        )
        ctx.update_step(step1_id, outputs={"signals": ["decision: test"]})
        
        # Step 2
        step2_id = ctx.trace_step(
            step_name="synthesize",
            inputs={"signals": ["decision: test"]},
            model="gpt-4o-mini",
        )
        ctx.update_step(step2_id, outputs={"synthesis": "Test synthesis complete"})
    
    print("   ✅ Multi-step tracing completed. Check LangSmith for grouped trace.")
    return True


async def test_agent_tags():
    """Test that different agents get different tags."""
    print("\n🧪 Test 3: Agent-Specific Tags")
    
    if not is_tracing_enabled():
        print("   ⚠️  Skipping (tracing not enabled)")
        return False
    
    agents = ["Arjuna", "DIKWSynthesizer", "CareerCoach", "TicketAgent"]
    thread_id = start_thread(agent_name="MultiAgentTest")
    
    for agent in agents:
        response = await traced_llm_call(
            prompt=f"Respond with just the word '{agent}'",
            agent_name=agent,
            model="gpt-4o-mini",
            thread_id=thread_id,
            task_type="identification",
        )
        print(f"   {agent}: {response[:50]}")
    
    print("   ✅ Check LangSmith - filter by tag 'agent:Arjuna', 'agent:DIKWSynthesizer', etc.")
    return True


async def main():
    print("=" * 60)
    print("SignalFlow LangSmith Tracing Verification")
    print("=" * 60)
    
    # Check env
    print(f"\n📋 Environment:")
    print(f"   LANGCHAIN_TRACING_V2: {os.environ.get('LANGCHAIN_TRACING_V2', 'not set')}")
    print(f"   LANGCHAIN_PROJECT: {os.environ.get('LANGCHAIN_PROJECT', 'not set')}")
    print(f"   LANGCHAIN_API_KEY: {'***' + os.environ.get('LANGCHAIN_API_KEY', '')[-4:] if os.environ.get('LANGCHAIN_API_KEY') else 'not set'}")
    
    results = []
    results.append(await test_basic_tracing())
    results.append(await test_context_manager())
    results.append(await test_agent_tags())
    
    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    
    if all(results):
        print("✅ All tracing tests passed!")
        print("\n🔗 View traces at: https://smith.langchain.com/")
    else:
        print("⚠️  Some tests skipped or failed")
    
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
