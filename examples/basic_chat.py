#!/usr/bin/env python3
"""
Basic Chat Example - Simple conversation with an LLM.

This example demonstrates:
- Getting a model
- Creating a conversation context
- Streaming vs non-streaming responses
"""

import asyncio
import os

from pi_ai import (
    get_model,
    stream,
    complete,
    Context,
    UserMessage,
    EventType,
)


async def streaming_example():
    """Example: Stream a response token by token."""
    print("=" * 60)
    print("Streaming Example")
    print("=" * 60)
    
    # Get a model (requires OPENAI_API_KEY env var)
    model = get_model("openai", "gpt-4o-mini")
    
    # Create context with a user message
    context = Context(messages=[
        UserMessage(content="Write a haiku about Python programming")
    ])
    
    # Stream the response
    print("Response: ", end="", flush=True)
    
    stream_obj = stream(model, context)
    async for event in stream_obj:
        if event.type == EventType.TEXT:
            # Print each token as it arrives
            print(event.text, end="", flush=True)
    
    print()  # New line after response
    print()


async def complete_example():
    """Example: Get a complete response at once."""
    print("=" * 60)
    print("Complete Example")
    print("=" * 60)
    
    model = get_model("openai", "gpt-4o-mini")
    
    context = Context(messages=[
        UserMessage(content="What is 2+2? Answer in one word.")
    ])
    
    # Get complete response
    response = await complete(model, context)
    
    # Extract text content
    text_parts = []
    for content in response.content:
        if hasattr(content, 'text'):
            text_parts.append(content.text)
    
    print(f"Response: {''.join(text_parts)}")
    print(f"Tokens used: {response.usage.total_tokens}")
    print(f"Cost: ${response.usage.cost.total:.6f}")
    print()


async def conversation_example():
    """Example: Multi-turn conversation."""
    print("=" * 60)
    print("Conversation Example")
    print("=" * 60)
    
    model = get_model("openai", "gpt-4o-mini")
    
    # Start with system context (optional)
    messages = [
        UserMessage(content="My name is Alice. Remember this.")
    ]
    
    # First turn
    context = Context(messages=messages)
    response1 = await complete(model, context)
    
    print("User: My name is Alice. Remember this.")
    print(f"Assistant: {response1.content[0].text}")
    
    # Add response to context for next turn
    messages.append(response1)
    messages.append(UserMessage(content="What's my name?"))
    
    # Second turn
    context = Context(messages=messages)
    response2 = await complete(model, context)
    
    print("User: What's my name?")
    print(f"Assistant: {response2.content[0].text}")
    print()


async def error_handling_example():
    """Example: Handle API errors gracefully."""
    print("=" * 60)
    print("Error Handling Example")
    print("=" * 60)
    
    # Check if API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("Note: OPENAI_API_KEY not set. This example would fail.")
        print("Set it with: export OPENAI_API_KEY=your-key")
        return
    
    try:
        model = get_model("openai", "gpt-4o-mini")
        context = Context(messages=[
            UserMessage(content="Hello!")
        ])
        
        response = await complete(model, context)
        print(f"Success: {response.content[0].text}")
        
    except Exception as e:
        print(f"Error: {e}")
        print("Tips:")
        print("- Check your API key")
        print("- Check your internet connection")
        print("- Check API rate limits")
    print()


async def main():
    """Run all examples."""
    print("\nPi AI - Basic Chat Examples\n")
    
    await streaming_example()
    await complete_example()
    await conversation_example()
    await error_handling_example()
    
    print("=" * 60)
    print("Examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
