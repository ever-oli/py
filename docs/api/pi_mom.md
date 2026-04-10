# Pi Mom API Reference

Slack bot for the Pi ecosystem.

## SlackBot

### Creating a Bot

```python
from pi_mom import SlackBot

bot = SlackBot(
    bot_token="xoxb-your-token",
    signing_secret="your-signing-secret",
    default_model="openai/gpt-4o",
)
```

### Running the Bot

```python
# Start the bot
await bot.start()

# Run with Socket Mode
await bot.start_socket_mode(app_token="xapp-your-token")
```

### Event Handlers

```python
@bot.on_message()
async def handle_message(event: SlackEvent, context: SlackContext):
    """Handle incoming messages."""
    
    # Access message data
    text = event.text
    channel = event.channel
    user = event.user
    
    # Send response
    await context.say("Hello!")
    
    # Or use blocks
    await context.say(blocks=[
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Hello!"}
        }
    ])
```

## Channel Store

### Managing Channel Data

```python
from pi_mom import ChannelStore

store = ChannelStore()

# Save a message
store.log_message(
    channel_id="C123456",
    user_id="U789012",
    text="Hello",
    timestamp="1234567890.123456",
)

# Get recent messages
messages = store.get_recent_messages("C123456", limit=50)

# Get thread messages
messages = store.get_thread_messages(
    channel_id="C123456",
    thread_ts="1234567890.123456"
)

# Save attachment
store.save_attachment(
    channel_id="C123456",
    attachment=Attachment(
        url="https://...",
        filename="image.png",
        mimetype="image/png",
    ),
)
```

## Agent Runner

### Running Agents in Slack

```python
from pi_mom import AgentRunner, get_or_create_runner

# Get or create runner for channel
runner = get_or_create_runner("C123456")

# Run agent with message
response = await runner.run(
    message="List all files",
    model="openai/gpt-4o",
    tools=[read_tool, bash_tool],
)

# Stream response
async for chunk in runner.run_stream("Tell me a story"):
    await context.say(chunk, ephemeral=True)
```

## Sandbox

### Executor Types

```python
from pi_mom import SandboxConfig, create_executor

# Host executor (runs on local machine)
config = SandboxConfig(type="host")
executor = create_executor(config)

# Docker executor (runs in container)
config = SandboxConfig(
    type="docker",
    image="python:3.11",
    memory="2g",
    cpus=2,
)
executor = create_executor(config)
```

### Running Commands

```python
from pi_mom import HostExecutor

executor = HostExecutor()

# Run command
result = await executor.run("ls -la", cwd="/tmp")
print(result.stdout)
print(result.stderr)
print(result.returncode)

# Run with timeout
try:
    result = await executor.run("sleep 100", timeout=10)
except TimeoutError:
    print("Command timed out")
```

## Types

### SlackEvent

```python
from pi_mom import SlackEvent

event = SlackEvent(
    type="message",
    channel="C123456",
    user="U789012",
    text="Hello",
    ts="1234567890.123456",
    thread_ts=None,  # If in thread
    files=[],  # Attached files
)
```

### SlackContext

```python
from pi_mom import SlackContext

context = SlackContext(
    channel="C123456",
    thread_ts="1234567890.123456",
    user="U789012",
)

# Methods
await context.say("Hello")  # Send message
await context.react("+1")   # Add reaction
await context.ephemeral("Only you see this")  # Ephemeral message
```

### LoggedMessage

```python
from pi_mom import LoggedMessage

message = LoggedMessage(
    user_id="U789012",
    text="Hello",
    timestamp="1234567890.123456",
    thread_ts=None,
    attachments=[],
)
```

### Attachment

```python
from pi_mom import Attachment

attachment = Attachment(
    url="https://...",
    filename="document.pdf",
    mimetype="application/pdf",
    size=1024,
)
```
