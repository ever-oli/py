"""Diagnostics for the IO hybrid setup."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckResult:
    """Result of a diagnostic check."""

    name: str
    status: str  # "ok", "warn", "error"
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def check_package_installed(package_name: str) -> CheckResult:
    """Check if a Python package is installed."""
    spec = importlib.util.find_spec(package_name.replace("-", "_"))
    if spec is None:
        return CheckResult(
            name=f"Package: {package_name}",
            status="error",
            message="Not installed",
        )
    return CheckResult(
        name=f"Package: {package_name}",
        status="ok",
        message=f"Installed at {spec.origin}",
    )


def check_pi_ai_models() -> CheckResult:
    """Check if pi_ai has models configured."""
    try:
        from pi_ai import get_models, register_built_in_api_providers
        register_built_in_api_providers()

        total_models = 0
        for provider in ["faux", "openai-completions", "anthropic-messages"]:
            models = get_models(provider)
            total_models += len(models)

        if total_models == 0:
            return CheckResult(
                name="pi_ai models",
                status="error",
                message="No models registered",
                details={"fix": "Create packages/pi_ai/src/pi_ai/models_generated.py from TypeScript"},
            )

        return CheckResult(
            name="pi_ai models",
            status="ok",
            message=f"{total_models} models available",
        )
    except Exception as e:
        return CheckResult(
            name="pi_ai models",
            status="error",
            message=f"Error checking models: {e}",
        )


def check_io_home() -> CheckResult:
    """Check IO_HOME directory setup."""
    from .constants import get_io_home

    try:
        home = get_io_home()
        if not home.exists():
            return CheckResult(
                name="IO_HOME",
                status="warn",
                message=f"Directory does not exist: {home}",
                details={"fix": f"Run: mkdir -p {home}"},
            )
        return CheckResult(
            name="IO_HOME",
            status="ok",
            message=f"{home}",
        )
    except Exception as e:
        return CheckResult(
            name="IO_HOME",
            status="error",
            message=f"Error: {e}",
        )


def check_api_keys() -> CheckResult:
    """Check if API keys are configured."""
    import os

    keys_found = []
    key_names = [
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
    ]

    for key in key_names:
        if os.environ.get(key):
            keys_found.append(key)

    if not keys_found:
        return CheckResult(
            name="API Keys",
            status="warn",
            message="No API keys found in environment",
            details={"fix": "Set at least one of: " + ", ".join(key_names)},
        )

    return CheckResult(
        name="API Keys",
        status="ok",
        message=f"Found: {', '.join(keys_found)}",
    )


def run_diagnostics() -> list[CheckResult]:
    """Run all diagnostic checks."""
    checks = [
        check_package_installed("io_cli"),
        check_package_installed("pi_coding_agent"),
        check_package_installed("pi_ai"),
        check_package_installed("pi_agent_core"),
        check_pi_ai_models(),
        check_io_home(),
        check_api_keys(),
    ]
    return checks


def print_diagnostics() -> int:
    """Print diagnostic results."""
    print("IO Hybrid Diagnostics")
    print("=" * 50)
    print()

    checks = run_diagnostics()
    exit_code = 0

    for check in checks:
        icon = "✓" if check.status == "ok" else "⚠" if check.status == "warn" else "✗"
        print(f"{icon} {check.name}")
        print(f"   {check.message}")

        if check.details:
            for key, value in check.details.items():
                print(f"   {key}: {value}")

        if check.status == "error":
            exit_code = 1

        print()

    if exit_code == 0:
        print("All checks passed!")
    else:
        print("Some checks failed. See details above.")

    return exit_code
