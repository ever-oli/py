# Pi Mom

Slack bot for the Pi ecosystem.

## Installation

```bash
pip install pi_mom
```

## Quick Start

### Environment Variables

```bash
export SLACK_BOT_TOKEN=xoxb-your-token
export SLACK_SIGNING_SECRET=your-secret
```

### Running the Bot

```bash
# HTTP Mode
python -m pi_mom

# Socket Mode (development)
python -m pi_mom --socket-mode
```

## Features

- **Message Handling**: Respond to messages and mentions
- **Agent Integration**: Run coding agents in Slack
- **Slash Commands**: `/pi` command for quick access
- **Sandboxing**: Docker-based execution for safety

## Usage

### Custom Handlers

```python
from pi_mom import SlackBot, SlackEvent, SlackContext

bot = SlackBot(token="xoxb-...", signing_secret="...")

@bot.on_message()
async def handle_message(event: SlackEvent, context: SlackContext):
    await context.say(f"You said: {event.text}")

bot.start()
```

### Agent Runner

```python
from pi_mom import get_or_create_runner

runner = get_or_create_runner(channel_id)
response = await runner.run("List files")
```

## Documentation

- [Full API Docs](../docs/api/pi_mom.md)
- [Example](../examples/slack_bot.py)
