"""
Quick LangSmith Tracing Test

This tests the basic LangSmith tracing setup before running the full sandbox.
Traces will appear in project: pr-minty-sigh-36

Run: python -m sandbox.langchain_evaluation.test_langsmith_trace
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load sandbox env first, then main .env for OPENAI_API_KEY fallback
sandbox_env = Path(__file__).parent / ".env.sandbox"
if sandbox_env.exists():
    load_dotenv(sandbox_env, override=True)
    print(f"✅ Loaded sandbox env from {sandbox_env}")

# Load main .env for OPENAI_API_KEY if not already set
main_env = Path(__file__).parent.parent.parent / ".env"
if main_env.exists() and not os.getenv("OPENAI_API_KEY"):
    load_dotenv(main_env, override=False)
    print(f"✅ Loaded OPENAI_API_KEY from main .env")

# Verify environment
print(f"\n📋 Environment Check:")
print(f"  LANGSMITH_TRACING: {os.getenv('LANGSMITH_TRACING')}")
print(f"  LANGSMITH_PROJECT: {os.getenv('LANGSMITH_PROJECT')}")
print(f"  LANGSMITH_API_KEY: {'***' + os.getenv('LANGSMITH_API_KEY', '')[-8:] if os.getenv('LANGSMITH_API_KEY') else 'NOT SET'}")
print(f"  OPENAI_API_KEY: {'***' + os.getenv('OPENAI_API_KEY', '')[-4:] if os.getenv('OPENAI_API_KEY') else 'NOT SET'}")

if not os.getenv("OPENAI_API_KEY"):
    print("\n❌ OPENAI_API_KEY not set. Please add it to your .env file.")
    exit(1)

# Now import LangChain
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

print("\n🚀 Running LangSmith Traced Agent Test...")


@tool
def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"


def main():
    # Create the model with tools
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    llm_with_tools = llm.bind_tools([get_weather])
    
    print("\n📤 Sending request to agent...")
    
    # First call - get tool call
    response = llm_with_tools.invoke([
        HumanMessage(content="What is the weather in San Francisco?")
    ])
    
    print(f"\n📥 Response:")
    print(f"  Content: {response.content}")
    
    if response.tool_calls:
        print(f"  Tool Calls: {response.tool_calls}")
        
        # Execute the tool
        for tool_call in response.tool_calls:
            if tool_call["name"] == "get_weather":
                result = get_weather.invoke(tool_call["args"])
                print(f"  Tool Result: {result}")
    
    print(f"\n✅ Test complete! Check traces at: https://smith.langchain.com/o/default/projects/p/pr-minty-sigh-36")
    print(f"   (or search for project 'pr-minty-sigh-36' in LangSmith)")


if __name__ == "__main__":
    main()
