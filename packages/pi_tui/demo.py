"""Demo script for pi-tui."""

from pi_tui import TUI, Container
from pi_tui.components import Editor, EditorOptions, EditorTheme, SelectListTheme, Text


def main():
    """Run a simple TUI demo."""
    # Create TUI
    tui = TUI()

    # Create root container
    container = Container()

    # Add header text
    header = Text("Welcome to pi-tui Demo", padding_x=2, padding_y=1)
    container.add_child(header)

    # Add description
    desc = Text(
        "This is a demo of the pi-tui library.\n"
        "Features: differential rendering, keyboard handling, word wrapping,\n"
        "wide character support, and Emacs key bindings.",
        padding_x=2,
        padding_y=1,
    )
    container.add_child(desc)

    # Create editor theme
    editor_theme = EditorTheme(
        border_color=lambda s: f"\x1b[36m{s}\x1b[0m",  # Cyan border
        select_list=SelectListTheme(
            selected_prefix=lambda s: f"\x1b[1m{s}\x1b[0m",
            selected_text=lambda s: f"\x1b[1;7m{s}\x1b[0m",
            description=lambda s: f"\x1b[2m{s}\x1b[0m",
            scroll_info=lambda s: f"\x1b[2m{s}\x1b[0m",
            no_match=lambda s: f"\x1b[2m{s}\x1b[0m",
        ),
    )

    # Create editor
    editor_options = EditorOptions(padding_x=1, autocomplete_max_visible=5)
    editor = Editor(tui, editor_theme, editor_options)

    def on_submit(text):
        print(f"\nSubmitted: {text}")
        tui.exit()

    editor.on_submit = on_submit
    container.add_child(editor)

    # Set root and start
    tui.set_root(container)

    print("Starting TUI demo...")
    print("Type some text and press Enter to submit.")
    print("Use Ctrl+C to exit without submitting.")
    print()

    try:
        tui.start()
        # Keep running until submit or interrupt
        import time

        while tui._running:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        tui.stop()
        print("\nTUI demo ended.")


if __name__ == "__main__":
    main()
