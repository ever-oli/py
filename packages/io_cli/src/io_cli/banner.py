"""Banner and branding for IO CLI."""

from .constants import APP_NAME, VERSION

ASCII_BANNER = """
╔═══════════════════════════════════════════╗
║                                           ║
║   ██╗   ██╗ ██████╗ ██╗      ██╗      ██╗ ║
║   ██║   ██║██╔═══██╗██║      ██║      ██║ ║
║   ██║   ██║██║   ██║██║      ██║      ██║ ║
║   ██║   ██║██║   ██║██║      ██║      ██║ ║
║   ╚██████╔╝╚██████╔╝███████╗ ███████╗ ██║ ║
║    ╚═════╝  ╚═════╝ ╚══════╝ ╚══════╝ ╚═╝ ║
║                                           ║
║         Hermes/Pi/Python Hybrid           ║
╚═══════════════════════════════════════════╝
"""

SIMPLE_BANNER = f"""
╔══════════════════════════════════════╗
║  {APP_NAME.upper()} v{VERSION:<28} ║
║  Hermes/Pi/Python Hybrid             ║
╚══════════════════════════════════════╝
"""

MINIMAL_BANNER = f"{APP_NAME} v{VERSION}"


def get_banner(style: str = "simple") -> str:
    """Get the banner string.

    Args:
        style: Banner style - 'ascii', 'simple', or 'minimal'

    Returns:
        Banner string
    """
    if style == "ascii":
        return ASCII_BANNER
    elif style == "minimal":
        return MINIMAL_BANNER
    else:
        return SIMPLE_BANNER


def print_banner(style: str = "simple") -> None:
    """Print the banner to stdout."""
    print(get_banner(style))
