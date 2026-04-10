"""Configuration management for pi_coding_agent."""

import os
from pathlib import Path

APP_NAME = "pi"
VERSION = "0.1.0"
CONFIG_DIR_NAME = ".pi"
ENV_AGENT_DIR = "PI_AGENT_DIR"


def get_agent_dir() -> Path:
    """Get the global agent configuration directory.

    Returns the path to ~/.pi/agent or the directory specified by
    the PI_AGENT_DIR environment variable.
    """
    if ENV_AGENT_DIR in os.environ:
        return Path(os.environ[ENV_AGENT_DIR])

    home = Path.home()
    return home / CONFIG_DIR_NAME / "agent"


def get_models_path() -> Path:
    """Get the path to the models configuration file."""
    return get_agent_dir() / "models.json"


def get_auth_path() -> Path:
    """Get the path to the auth storage file."""
    return get_agent_dir() / "auth.json"


def get_docs_path() -> Path:
    """Get the path to the documentation directory."""
    # In the Python package, docs would be bundled
    package_dir = Path(__file__).parent
    return package_dir / "docs"


def get_default_session_dir(cwd: str | Path, agent_dir: str | Path | None = None) -> Path:
    """Get the default session directory for a project.

    Args:
        cwd: Current working directory (project root)
        agent_dir: Optional agent directory override

    Returns:
        Path to the session directory
    """
    cwd_path = Path(cwd).resolve()

    # Use .pi/sessions in the project directory
    return cwd_path / CONFIG_DIR_NAME / "sessions"
