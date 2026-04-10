#!/usr/bin/env python3
"""
Slack Bot Example - Running pi_mom as a Slack bot.

This example demonstrates:
- Setting up a Slack bot
- Handling messages and events
- Running agents in response to Slack messages
- Using sandboxed execution

Prerequisites:
- SLACK_BOT_TOKEN environment variable
- SLACK_SIGNING_SECRET environment variable
"""

import asyncio
import os
from typing import Any

# Note: These imports require pi_mom to be installed
# pip install -e packages/pi_mom

try:
    from pi_mom import SlackBot, SlackEvent, SlackContext
    from pi_mom import ChannelStore, AgentRunner
    from pi_mom import SandboxConfig, create_executor
except ImportError:
    print("pi_mom package not installed. Install with:")
    print("  pip install -e packages/pi_mom")
    exit(1)


# ============================================================================
# Example 1: Basic Bot Setup
# ============================================================================

async def basic_bot_example():
    """Example: Basic bot setup and message handling."""
    print("=" * 60)
    print("Basic Slack Bot Example")
    print("=" * 60)
    
    # Check environment variables
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    signing_secret = os.getenv("SLACK_SIGNING_SECRET")
    
    if not bot_token or not signing_secret:
        print("Missing required environment variables:")
        print("  - SLACK_BOT_TOKEN")
        print("  - SLACK_SIGNING_SECRET")
        print("\nSet them with:")
        print("  export SLACK_BOT_TOKEN=xoxb-your-token")
        print("  export SLACK_SIGNING_SECRET=your-secret")
        print("\nSkipping this example.")
        return
    
    print("Environment variables found!")
    print(f"Bot token: {bot_token[:10]}...")
    print(f"Signing secret: {signing_secret[:5]}...")
    print("\nTo run a real bot, use:")
    print("  python -m pi_mom")
    print()


# ============================================================================
# Example 2: Message Handlers
# ============================================================================

def create_demo_bot():
    """Create a demo bot with handlers (for illustration)."""
    
    bot = SlackBot(
        bot_token="xoxb-demo-token",  # Replace with real token
        signing_secret="demo-secret",  # Replace with real secret
        default_model="openai/gpt-4o-mini",
    )
    
    @bot.on_message()
    async def handle_message(event: SlackEvent, context: SlackContext):
        """Handle incoming messages."""
        
        # Ignore bot messages
        if event.bot_id:
            return
        
        # Simple echo for demo
        await context.say(f"You said: {event.text}")
    
    @bot.on_mention()
    async def handle_mention(event: SlackEvent, context: SlackContext):
        """Handle when bot is mentioned."""
        
        # Extract the mention from text
        text = event.text.replace(f"<@{bot.bot_id}>", "").strip()
        
        # Use agent to respond
        await context.say("Thinking...", ephemeral=True)
        
        # In real usage:
        # runner = get_or_create_runner(event.channel)
        # response = await runner.run(text)
        # await context.say(response)
        
        await context.say(f"You mentioned me about: {text}")
    
    @bot.on_command("/pi")
    async def handle_slash_command(command: dict[str, Any], context: SlackContext):
        """Handle slash command /pi."""
        
        text = command.get("text", "")
        
        await context.say(f"Running: {text}")
        
        # Execute command with agent
        # response = await runner.run(text)
        # await context.say(response)
    
    return bot


async def message_handlers_example():
    """Example: Different message handlers."""
    print("=" * 60)
    print("Message Handlers Example")
    print("=" * 60)
    
    print("Creating demo bot with handlers...")
    bot = create_demo_bot()
    
    print("\nHandler types available:")
    print("  - @bot.on_message() - All messages")
    print("  - @bot.on_mention() - When bot is @mentioned")
    print("  - @bot.on_command('/cmd') - Slash commands")
    print("  - @bot.on_reaction() - Emoji reactions")
    print("  - @bot.on_file_shared() - File uploads")
    
    print("\nExample handler:")
    print("""
    @bot.on_message()
    async def handle_message(event: SlackEvent, context: SlackContext):
        # event.text - message text
        # event.user - user ID
        # event.channel - channel ID
        # event.thread_ts - thread timestamp (if in thread)
        
        await context.say("Response text")
        await context.react("+1")  # Add reaction
    """)
    print()


# ============================================================================
# Example 3: Agent Runner
# ============================================================================

async def agent_runner_example():
    """Example: Running agents in Slack."""
    print("=" * 60)
    print("Agent Runner Example")
    print("=" * 60)
    
    print("""
The AgentRunner manages agent instances per channel:

    from pi_mom import get_or_create_runner
    
    @bot.on_message()
    async def handle_message(event: SlackEvent, context: SlackContext):
        # Get or create runner for this channel
        runner = get_or_create_runner(event.channel)
        
        # Run with agent
        response = await runner.run(
            message=event.text,
            model="openai/gpt-4o",
            tools=[read_tool, bash_tool],
        )
        
        await context.say(response)
""")
    
    print("\nStreaming responses:")
    print("""
    @bot.on_message()
    async def handle_streaming(event: SlackEvent, context: SlackContext):
        runner = get_or_create_runner(event.channel)
        
        # Stream response chunks
        message_ts = None
        async for chunk in runner.run_stream(event.text):
            if message_ts is None:
                # First chunk - create message
                result = await context.say(chunk)
                message_ts = result["ts"]
            else:
                # Update existing message
                await context.update(message_ts, chunk)
""")
    print()


# ============================================================================
# Example 4: Sandbox Execution
# ============================================================================

async def sandbox_example():
    """Example: Using sandboxed execution."""
    print("=" * 60)
    print("Sandbox Execution Example")
    print("=" * 60)
    
    print("""
Execute code safely using different sandbox types:

1. Host Executor (local machine):
    
    from pi_mom import HostExecutor
    
    executor = HostExecutor()
    result = await executor.run("ls -la", cwd="/tmp")
    print(result.stdout)
    print(result.returncode)

2. Docker Executor (containerized):
    
    from pi_mom import SandboxConfig, create_executor
    
    config = SandboxConfig(
        type="docker",
        image="python:3.11-slim",
        memory="1g",
        cpus=1,
    )
    executor = create_executor(config)
    
    result = await executor.run("python --version")
    print(result.stdout)  # Python 3.11.x

3. Timeout and limits:
    
    try:
        result = await executor.run(
            "sleep 100",
            timeout=10,  # 10 second timeout
        )
    except TimeoutError:
        print("Command timed out")
""")
    print()


# ============================================================================
# Example 5: Channel Storage
# ============================================================================

async def channel_storage_example():
    """Example: Storing channel data."""
    print("=" * 60)
    print("Channel Storage Example")
    print("=" * 60)
    
    print("""
The ChannelStore persists message history and context:

    from pi_mom import ChannelStore, LoggedMessage
    
    store = ChannelStore()
    
    # Log a message
    store.log_message(
        channel_id="C123456",
        user_id="U789012",
        text="Hello!",
        timestamp="1234567890.123456",
    )
    
    # Get recent messages
    messages = store.get_recent_messages("C123456", limit=50)
    
    # Get thread messages
    thread = store.get_thread_messages(
        channel_id="C123456",
        thread_ts="1234567890.123456",
    )
    
    # Save attachment
    store.save_attachment(
        channel_id="C123456",
        attachment=Attachment(
            url="https://...",
            filename="document.pdf",
        ),
    )

This enables context-aware conversations where the agent
remembers previous messages in the channel.
""")
    print()


# ============================================================================
# Example 6: Running the Bot
# ============================================================================

async def running_bot_example():
    """Example: How to run the bot."""
    print("=" * 60)
    print("Running the Bot")
    print("=" * 60)
    
    print("""
1. HTTP Mode (for production with Slack Events API):

    export SLACK_BOT_TOKEN=xoxb-your-token
    export SLACK_SIGNING_SECRET=your-secret
    
    python -m pi_mom
    # or
    pi-mom-server --port 3000

2. Socket Mode (for development, no public URL needed):

    export SLACK_BOT_TOKEN=xoxb-your-token
    export SLACK_APP_TOKEN=xapp-your-app-token
    
    python -m pi_mom --socket-mode

3. Programmatically:

    from pi_mom import SlackBot
    
    bot = SlackBot(
        bot_token=os.getenv("SLACK_BOT_TOKEN"),
        signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
    )
    
    # HTTP mode
    await bot.start(host="0.0.0.0", port=3000)
    
    # Socket mode
    await bot.start_socket_mode(
        app_token=os.getenv("SLACK_APP_TOKEN")
    )
""")
    print()


# ============================================================================
# Main
# ============================================================================

async def main():
    """Run all examples."""
    print("\nPi Mom - Slack Bot Examples\n")
    print("These examples show how to run a Slack bot with Pi.\n")
    
    await basic_bot_example()
    await message_handlers_example()
    await agent_runner_example()
    await sandbox_example()
    await channel_storage_example()
    await running_bot_example()
    
    print("=" * 60)
    print("Examples complete!")
    print("=" * 60)
    print("\nTo run a real bot:")
    print("1. Create a Slack app at https://api.slack.com/apps")
    print("2. Add Bot Token Scopes: chat:write, channels:read, etc.")
    print("3. Install app to your workspace")
    print("4. Set environment variables")
    print("5. Run: python -m pi_mom")


if __name__ == "__main__":
    asyncio.run(main())
