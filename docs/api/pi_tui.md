# Pi TUI API Reference

Terminal UI library with differential rendering.

## Terminal

### Terminal Classes

```python
from pi_tui import Terminal, ProcessTerminal, MockTerminal

# Real terminal
term = ProcessTerminal()

# Mock terminal for testing
mock = MockTerminal(width=80, height=24)
```

### Terminal Operations

```python
# Get size
width, height = term.get_size()

# Clear screen
term.clear()

# Move cursor
term.move_to(x=0, y=0)

# Write text
term.write("Hello, World!")

# Hide/show cursor
term.hide_cursor()
term.show_cursor()

# Read input
key = term.read_key()
```

## Buffer

### Creating a Buffer

```python
from pi_tui import Buffer

buf = Buffer(width=80, height=24)
```

### Drawing

```python
# Set cell
buf.set_cell(x=0, y=0, char="H")

# Set with attributes
buf.set_cell(x=1, y=0, char="i", fg="blue", bg="white", bold=True)

# Write string
buf.write_string(x=0, y=1, text="Hello, World!")

# Clear
buf.clear()
```

### Diff Rendering

```python
from pi_tui import BufferDiff

# Create two buffers
old_buf = Buffer(80, 24)
new_buf = Buffer(80, 24)

# ... draw on new_buf ...

# Calculate diff
diff = BufferDiff.calculate(old_buf, new_buf)

# Apply diff to terminal
for (x, y, cell) in diff.changes:
    term.move_to(x, y)
    term.write(cell.char)
```

## Components

### Box

```python
from pi_tui.components import Box

box = Box(
    x=0, y=0,
    width=40, height=10,
    border=True,
    title="My Box",
)

box.render(buf)
```

### Text

```python
from pi_tui.components import Text

text = Text(
    x=2, y=1,
    text="Hello, World!",
    fg="green",
    bold=True,
)

text.render(buf)
```

### Editor

```python
from pi_tui.components import Editor, EditorOptions

editor = Editor(
    options=EditorOptions(
        x=0, y=0,
        width=80, height=24,
        theme=EditorTheme(),
    )
)

# Set content
editor.set_text("Hello, World!")

# Get content
content = editor.get_text()

# Handle key
editor.handle_key(key_event)

# Render
editor.render(buf)
```

### Select List

```python
from pi_tui.components import SelectList, SelectItem

items = [
    SelectItem(label="Option 1", value="opt1"),
    SelectItem(label="Option 2", value="opt2"),
    SelectItem(label="Option 3", value="opt3"),
]

select = SelectList(
    x=0, y=0,
    width=40, height=10,
    items=items,
)

# Navigate
select.move_down()
select.move_up()

# Get selection
selected = select.get_selected()

# Render
select.render(buf)
```

### Input

```python
from pi_tui.components import Input

inp = Input(
    x=0, y=0,
    width=40,
    placeholder="Type here...",
)

# Handle key
inp.handle_key(key_event)

# Get value
value = inp.get_value()

# Set value
inp.set_value("Hello")
```

### Markdown

```python
from pi_tui.components import Markdown

md = Markdown(
    x=0, y=0,
    width=80, height=24,
    content="""
# Heading

Some **bold** and *italic* text.

- List item 1
- List item 2
""",
)

md.render(buf)
```

## Keys

### Key Handling

```python
from pi_tui import Key, KeyId, matches_key, parse_key

# Parse key
key = parse_key("\x1b[A")  # Up arrow

# Check key
if key.id == KeyId.UP:
    print("Up arrow pressed")

# Match key pattern
if matches_key(key, Key(ctrl=True, char="c")):
    print("Ctrl+C pressed")

# Check key type
if key.is_printable:
    print(f"Character: {key.char}")
```

### Key Constants

```python
from pi_tui import KeyId

KeyId.ENTER
KeyId.ESCAPE
KeyId.TAB
KeyId.BACKSPACE
KeyId.UP
KeyId.DOWN
KeyId.LEFT
KeyId.RIGHT
KeyId.HOME
KeyId.END
KeyId.DELETE
KeyId.PAGE_UP
KeyId.PAGE_DOWN
```

## TUI Framework

### Creating a TUI

```python
from pi_tui import TUI, Container, Component

class MyComponent(Component):
    def __init__(self):
        self.buffer = Buffer(80, 24)
    
    def render(self) -> Buffer:
        self.buffer.clear()
        # ... draw on buffer ...
        return self.buffer
    
    def handle_key(self, key: Key) -> bool:
        # Return True if key was handled
        if key.id == KeyId.ESCAPE:
            return True
        return False

tui = TUI()
container = Container()
container.add_component(MyComponent())

tui.set_root(container)
tui.run()
```

### Focus Management

```python
from pi_tui import Focusable

class MyFocusable(Focusable, Component):
    def on_focus(self):
        print("Got focus")
    
    def on_blur(self):
        print("Lost focus")

# Navigate focus
tui.focus_next()
tui.focus_prev()
```

### Overlays

```python
from pi_tui import OverlayOptions, OverlayAnchor

# Show overlay
overlay = tui.show_overlay(
    component=my_dialog,
    options=OverlayOptions(
        anchor=OverlayAnchor.CENTER,
        margin=OverlayMargin(x=2, y=1),
    ),
)

# Close overlay
overlay.close()
```

## Terminal Images

### Rendering Images

```python
from pi_tui import (
    render_image,
    get_capabilities,
    ImageRenderOptions,
)

# Detect capabilities
caps = get_capabilities()

if caps.kitty_graphics:
    # Use Kitty graphics protocol
    result = render_image(
        image_path="image.png",
        options=ImageRenderOptions(
            width=400,
            height=300,
        ),
    )
elif caps.iterm2_graphics:
    # Use iTerm2 inline images
    result = render_image(...)
else:
    # Fall back to ASCII/Unicode
    result = render_image(..., force_text=True)
```

### Kitty Graphics

```python
from pi_tui import encode_kitty

data = encode_kitty(
    image_data=png_bytes,
    width=400,
    height=300,
)
term.write(data)
```

### iTerm2 Graphics

```python
from pi_tui import encode_iterm2

data = encode_iterm2(
    image_data=png_bytes,
    width=400,
    height=300,
)
term.write(data)
```
