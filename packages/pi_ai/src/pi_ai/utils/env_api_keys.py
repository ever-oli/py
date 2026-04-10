"""
Environment-based API key management.
Python port of TypeScript env-api-keys.ts
"""

from __future__ import annotations

import os
from pathlib import Path


def _has_vertex_adc_credentials() -> bool:
    """Check if Vertex ADC credentials exist."""
    # Check GOOGLE_APPLICATION_CREDENTIALS env var first
    gac_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if gac_path:
        return Path(gac_path).exists()

    # Fall back to default ADC path
    home = Path.home()
    adc_path = home / ".config" / "gcloud" / "application_default_credentials.json"
    return adc_path.exists()


def get_env_api_key(provider: str) -> str | None:
    """
    Get API key for provider from known environment variables.

    Will not return API keys for providers that require OAuth tokens.

    Args:
        provider: The provider identifier

    Returns:
        The API key or None if not found
    """
    # GitHub Copilot
    if provider == "github-copilot":
        return (
            os.environ.get("COPILOT_GITHUB_TOKEN")
            or os.environ.get("GH_TOKEN")
            or os.environ.get("GITHUB_TOKEN")
        )

    # Anthropic: ANTHROPIC_OAUTH_TOKEN takes precedence
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_OAUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")

    # Vertex AI
    if provider == "google-vertex":
        if os.environ.get("GOOGLE_CLOUD_API_KEY"):
            return os.environ.get("GOOGLE_CLOUD_API_KEY")

        has_credentials = _has_vertex_adc_credentials()
        has_project = bool(
            os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT")
        )
        has_location = bool(os.environ.get("GOOGLE_CLOUD_LOCATION"))

        if has_credentials and has_project and has_location:
            return "<authenticated>"

    # Amazon Bedrock
    if provider == "amazon-bedrock":
        # Check various AWS credential sources
        if (
            os.environ.get("AWS_PROFILE")
            or (os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"))
            or os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
            or os.environ.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")
            or os.environ.get("AWS_CONTAINER_CREDENTIALS_FULL_URI")
            or os.environ.get("AWS_WEB_IDENTITY_TOKEN_FILE")
        ):
            return "<authenticated>"

    # Standard API key environment variables
    env_map = {
        "openai": "OPENAI_API_KEY",
        "azure-openai-responses": "AZURE_OPENAI_API_KEY",
        "google": "GEMINI_API_KEY",
        "groq": "GROQ_API_KEY",
        "cerebras": "CEREBRAS_API_KEY",
        "xai": "XAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "vercel-ai-gateway": "AI_GATEWAY_API_KEY",
        "zai": "ZAI_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "minimax": "MINIMAX_API_KEY",
        "minimax-cn": "MINIMAX_CN_API_KEY",
        "huggingface": "HF_TOKEN",
        "opencode": "OPENCODE_API_KEY",
        "opencode-go": "OPENCODE_API_KEY",
        "kimi-coding": "KIMI_API_KEY",
    }

    env_var = env_map.get(provider)
    return os.environ.get(env_var) if env_var else None


__all__ = ["get_env_api_key"]
