#!/usr/bin/env python3
"""
Coding Agent Example - Using the coding agent programmatically.

This example demonstrates:
- Creating an agent session
- Running coding tasks
- Managing sessions
- Handling tool execution
"""

import asyncio
import os
from pathlib import Path

from pi_coding_agent import (
    create_agent_session,
    list_sessions,
    create_coding_tools,
    read_only_tools,
)
from pi_ai import get_model, ThinkingLevel


async def basic_session_example():
    """Example: Create and use a basic agent session."""
    print("=" * 60)
    print("Basic Session Example")
    print("=" * 60)
    
    # Create a session with default settings
    result = await create_agent_session()
    session = result.session
    
    print(f"Session created: {session.session_id}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Persistence enabled: {session.persistence_enabled}")
    
    # Run a simple task
    response = await session.run("What files are in the current directory?")
    print(f"\nAgent response:\n{response['content']}")
    print()


async def with_model_example():
    """Example: Use a specific model."""
    print("=" * 60)
    print("With Specific Model Example")
    print("=" * 60)
    
    # Create session with specific model and settings
    result = await create_agent_session(
        model=get_model("openai", "gpt-4o-mini"),
        thinking_level=ThinkingLevel.MEDIUM,
    )
    session = result.session
    
    print(f"Using model: openai/gpt-4o-mini")
    print(f"Thinking level: medium")
    
    # Run a coding task
    response = await session.run("Write a Python function to calculate factorial")
    print(f"\nAgent response:\n{response['content']}")
    
    if response.get('tool_calls'):
        print(f"\nTools used: {[tc['name'] for tc in response['tool_calls']]}")
    print()


async def with_tools_example():
    """Example: Use specific tool sets."""
    print("=" * 60)
    print("With Specific Tools Example")
    print("=" * 60)
    
    # Read-only tools (safe, can't modify files)
    result = await create_agent_session(
        tools=read_only_tools,
        no_session=True,  # Don't persist this session
    )
    session = result.session
    
    print("Using read-only tools")
    print("Available tools:", [t["name"] for t in session.get_tools()])
    
    # The agent can only read, not write
    response = await session.run("Read the README.md file if it exists")
    print(f"\nAgent response:\n{response['content']}")
    print()


async def session_persistence_example():
    """Example: Save and resume sessions."""
    print("=" * 60)
    print("Session Persistence Example")
    print("=" * 60)
    
    # Create a session
    result = await create_agent_session()
    session = result.session
    
    print(f"Created session: {session.session_id}")
    
    # Add some context
    await session.run("Remember: my favorite color is blue")
    
    # Save explicitly (also auto-saves during run)
    session.save_session()
    print("Session saved")
    
    # List sessions
    sessions = list_sessions(limit=5)
    print(f"\nRecent sessions: {len(sessions)}")
    for s in sessions[:3]:
        print(f"  - {s.id}")
    
    # Resume the session
    from pi_coding_agent import create_agent_session
    
    resumed = await create_agent_session(
        session_id=session.session_id,
    )
    
    print(f"\nResumed session: {resumed.session.session_id}")
    
    # The context should be preserved
    response = await resumed.session.run("What's my favorite color?")
    print(f"Agent response: {response['content']}")
    print()


async def direct_tool_execution_example():
    """Example: Execute tools directly without LLM."""
    print("=" * 60)
    print("Direct Tool Execution Example")
    print("=" * 60)
    
    result = await create_agent_session()
    session = result.session
    
    # Execute a tool directly
    read_result = await session.execute_tool(
        "read",
        file_path="README.md",
        limit=10
    )
    
    print(f"Direct tool execution result:")
    print(f"Type: {type(read_result)}")
    print(f"Keys: {list(read_result.keys()) if isinstance(read_result, dict) else 'N/A'}")
    
    # Execute ls tool
    ls_result = await session.execute_tool("ls", path=".")
    print(f"\nDirectory contents: {len(ls_result.get('entries', []))} items")
    print()


async def custom_cwd_example():
    """Example: Use a custom working directory."""
    print("=" * 60)
    print("Custom Working Directory Example")
    print("=" * 60)
    
    # Create temp directory
    temp_dir = "/tmp/pi_demo"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Create a file there
    with open(f"{temp_dir}/test.txt", "w") as f:
        f.write("Hello from pi_coding_agent!")
    
    # Create session with custom cwd
    result = await create_agent_session(cwd=temp_dir)
    session = result.session
    
    print(f"Working directory: {temp_dir}")
    
    # Agent operates in that directory
    response = await session.run("Read the test.txt file")
    print(f"\nAgent response:\n{response['content']}")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)
    print()


async def usage_tracking_example():
    """Example: Track token usage."""
    print("=" * 60)
    print("Usage Tracking Example")
    print("=" * 60)
    
    result = await create_agent_session(
        model=get_model("openai", "gpt-4o-mini"),
    )
    session = result.session
    
    # Run a few tasks
    await session.run("What is Python?")
    await session.run("What are its main features?")
    
    # Check usage
    usage = session.usage
    print(f"Total tokens: {usage.total}")
    print(f"  Input: {usage.input}")
    print(f"  Output: {usage.output}")
    print(f"  Cache read: {usage.cache_read}")
    print(f"  Cache write: {usage.cache_write}")
    print(f"Estimated cost: ${usage.cost:.6f}")
    print()


async def main():
    """Run all examples."""
    print("\nPi Coding Agent - Examples\n")
    
    await basic_session_example()
    await with_model_example()
    await with_tools_example()
    await session_persistence_example()
    await direct_tool_execution_example()
    await custom_cwd_example()
    await usage_tracking_example()
    
    print("=" * 60)
    print("Examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
