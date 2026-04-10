"""
Model management and discovery.
Python port of TypeScript models.ts
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import Model, Usage


# Model registry: provider -> model_id -> Model
_model_registry: dict[str, dict[str, Model]] = {}


def register_model(provider: str, model: Model) -> None:
    """Register a model in the registry."""
    if provider not in _model_registry:
        _model_registry[provider] = {}
    _model_registry[provider][model.id] = model


def get_model(provider: str, model_id: str) -> Model | None:
    """Get a model by provider and model ID."""
    provider_models = _model_registry.get(provider)
    return provider_models.get(model_id) if provider_models else None


def get_providers() -> list[str]:
    """Get all registered providers."""
    return list(_model_registry.keys())


def get_models(provider: str) -> list[Model]:
    """Get all models for a provider."""
    provider_models = _model_registry.get(provider)
    return list(provider_models.values()) if provider_models else []


def calculate_cost(model: Model, usage: Usage) -> Usage:
    """
    Calculate the cost for token usage.
    Updates usage.cost in place and returns the usage object.
    """
    # Cost is in $/million tokens
    usage.cost.input = (model.cost.get("input", 0) / 1_000_000) * usage.input
    usage.cost.output = (model.cost.get("output", 0) / 1_000_000) * usage.output
    usage.cost.cache_read = (model.cost.get("cache_read", 0) / 1_000_000) * usage.cache_read
    usage.cost.cache_write = (model.cost.get("cache_write", 0) / 1_000_000) * usage.cache_write
    usage.cost.total = (
        usage.cost.input + usage.cost.output + usage.cost.cache_read + usage.cost.cache_write
    )
    return usage


def supports_xhigh(model: Model) -> bool:
    """
    Check if a model supports xhigh thinking level.

    Supported today:
    - GPT-5.2 / GPT-5.3 / GPT-5.4 model families
    - Opus 4.6 models (xhigh maps to adaptive effort "max" on Anthropic-compatible providers)
    """
    model_id = model.id.lower()
    if "gpt-5.2" in model_id or "gpt-5.3" in model_id or "gpt-5.4" in model_id:
        return True
    return bool("opus-4-6" in model_id or "opus-4.6" in model_id)


def models_are_equal(
    a: Model | None,
    b: Model | None,
) -> bool:
    """
    Check if two models are equal by comparing both their id and provider.
    Returns False if either model is null or undefined.
    """
    if a is None or b is None:
        return False
    return a.id == b.id and a.provider == b.provider


# Import and register built-in models
def _register_builtin_models() -> None:
    """Register built-in models from the generated models file."""
    try:
        from .models_generated import MODELS

        for provider, models_dict in MODELS.items():
            for _model_id, model_data in models_dict.items():
                register_model(provider, model_data)
    except ImportError:
        # models_generated.py doesn't exist yet
        pass


# Register built-in models on module load
_register_builtin_models()


__all__ = [
    "register_model",
    "get_model",
    "get_providers",
    "get_models",
    "calculate_cost",
    "supports_xhigh",
    "models_are_equal",
]
