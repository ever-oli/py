"""CLI for Pi Web UI.

Provides command-line interface for starting the web server.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="pi-web-ui",
        description="Web-based User Interface for Pi Ecosystem",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    parser.add_argument(
        "--static-dir",
        type=Path,
        help="Path to custom static files directory",
    )
    parser.add_argument(
        "--templates-dir",
        type=Path,
        help="Path to custom templates directory",
    )

    args = parser.parse_args()

    # Import here to avoid slow startup
    from .server import run_server

    print(f"Starting Pi Web UI on http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop")

    try:
        run_server(
            host=args.host,
            port=args.port,
            reload=args.reload,
            static_dir=args.static_dir,
            templates_dir=args.templates_dir,
        )
    except KeyboardInterrupt:
        print("\nShutting down...")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
