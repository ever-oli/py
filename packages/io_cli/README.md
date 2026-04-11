# IO CLI

Hermes/Pi/Python Hybrid CLI

## Installation

```bash
pip install -e packages/io_cli
```

## Usage

```bash
# Run agent
io "Create a Python script..."

# Continue session
io --continue

# Cron management
io cron --list
io cron --add

# Gateway management
io gateway --status
```

## Features

- **Agent**: AI coding agent powered by pi_coding_agent
- **Cron**: Scheduled task management
- **Gateway**: Distributed node management (coming soon)
- **Config**: Profile-based configuration
