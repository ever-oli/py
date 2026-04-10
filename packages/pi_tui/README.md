# Pi TUI

Terminal UI library with differential rendering.

## Installation

```bash
pip install pi_tui
```

## Quick Start

```python
from pi_tui import TUI, Container
from pi_tui.components import Box, Text

# Create TUI
tui = TUI()

# Create components
container = Container()
box = Box(x=0, y=0, width=40, height=10, border=True)
text = Text(x=2, y=1, text="Hello, World!")

# Add to container
container.add_component(box)
container.add_component(text)

# Run
tui.set_root(container)
tui.run()
```

## Features

- **Differential Rendering**: Only redraw changed cells
- **Components**: Box, Text, Editor, SelectList, Input, Markdown
- **Key Handling**: Comprehensive keyboard input
- **Images**: Kitty and iTerm2 image protocols

## Components

```python
from pi_tui.components import (
    Box, Text, Editor, SelectList, Input, Markdown
)
```

## Documentation

- [Full API Docs](../docs/api/pi_tui.md)
