"""Generated models for pi_ai.

This file contains model definitions for various LLM providers.
Python port of TypeScript models_generated.ts
"""

from __future__ import annotations

from .models import register_model
from .types import (
    Model,
    ModelCapabilities,
    ModelPricing,
)


# Provider constants (Literal values)
PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_OPENROUTER = "openrouter"
PROVIDER_GOOGLE = "google"
PROVIDER_FAUX = "faux"
PROVIDER_KIMI = "kimi-coding"

# API constants
API_OPENAI_RESPONSES = "openai-responses"
API_OPENAI_COMPLETIONS = "openai-completions"
API_ANTHROPIC_MESSAGES = "anthropic-messages"
API_GOOGLE_GENERATIVE_AI = "google-generative-ai"
API_FAUX = "faux"
API_KIMI = "openai-completions"


def _register_openai_models() -> None:
    """Register OpenAI models."""
    register_model(
        provider=PROVIDER_OPENAI,
        model=Model(
            id="gpt-4o",
            api=API_OPENAI_RESPONSES,
            provider=PROVIDER_OPENAI,
            name="GPT-4o",
            base_url="https://api.openai.com/v1",
            capabilities=ModelCapabilities(
                supports_tools=True,
                supports_vision=True,
                supports_json_mode=True,
                supports_streaming=True,
                supports_reasoning=False,
                supports_cache_control=False,
            ),
            pricing=ModelPricing(
                input=2.50,
                output=10.00,
            ),
            context_window=128000,
        ),
    )

    register_model(
        provider=PROVIDER_OPENAI,
        model=Model(
            id="gpt-4o-mini",
            api=API_OPENAI_RESPONSES,
            provider=PROVIDER_OPENAI,
            name="GPT-4o Mini",
            base_url="https://api.openai.com/v1",
            capabilities=ModelCapabilities(
                supports_tools=True,
                supports_vision=True,
                supports_json_mode=True,
                supports_streaming=True,
                supports_reasoning=False,
                supports_cache_control=False,
            ),
            pricing=ModelPricing(
                input=0.15,
                output=0.60,
            ),
            context_window=128000,
        ),
    )

    register_model(
        provider=PROVIDER_OPENAI,
        model=Model(
            id="o3-mini",
            api=API_OPENAI_RESPONSES,
            provider=PROVIDER_OPENAI,
            name="o3 Mini",
            base_url="https://api.openai.com/v1",
            capabilities=ModelCapabilities(
                supports_tools=True,
                supports_vision=False,
                supports_json_mode=True,
                supports_streaming=True,
                supports_reasoning=True,
                supports_cache_control=False,
            ),
            pricing=ModelPricing(
                input=1.10,
                output=4.40,
            ),
            context_window=200000,
            reasoning=True,
        ),
    )


def _register_anthropic_models() -> None:
    """Register Anthropic models."""
    register_model(
        provider=PROVIDER_ANTHROPIC,
        model=Model(
            id="claude-3-5-sonnet-20241022",
            api=API_ANTHROPIC_MESSAGES,
            provider=PROVIDER_ANTHROPIC,
            name="Claude 3.5 Sonnet",
            capabilities=ModelCapabilities(
                supports_tools=True,
                supports_vision=True,
                supports_json_mode=True,
                supports_streaming=True,
                supports_reasoning=True,
                supports_cache_control=True,
            ),
            pricing=ModelPricing(
                input=3.00,
                output=15.00,
                cache_write=3.75,
                cache_read=0.30,
            ),
            context_window=200000,
        ),
    )

    register_model(
        provider=PROVIDER_ANTHROPIC,
        model=Model(
            id="claude-3-opus-20240229",
            api=API_ANTHROPIC_MESSAGES,
            provider=PROVIDER_ANTHROPIC,
            name="Claude 3 Opus",
            capabilities=ModelCapabilities(
                supports_tools=True,
                supports_vision=True,
                supports_json_mode=True,
                supports_streaming=True,
                supports_reasoning=True,
                supports_cache_control=True,
            ),
            pricing=ModelPricing(
                input=15.00,
                output=75.00,
                cache_write=18.75,
                cache_read=1.50,
            ),
            context_window=200000,
        ),
    )


def _register_openrouter_models() -> None:
    """Register OpenRouter models."""
    # FREE TIER MODELS (rate limited, $0)
    free_models = [
        ("google/gemma-4-26b-a4b-it:free", "Gemma 4 26B (Free)", 128000),
        ("nvidia/nemotron-3-nano-30b-a3b:free", "Nemotron 3 Nano (Free)", 128000),
        ("liquid/lfm-2.5-1.2b-instruct:free", "Liquid LFM 1.2B (Free)", 32768),
    ]
    
    for model_id, name, context in free_models:
        register_model(
            provider=PROVIDER_OPENROUTER,
            model=Model(
                id=model_id,
                api=API_OPENAI_COMPLETIONS,
                provider=PROVIDER_OPENROUTER,
                name=name,
                base_url="https://openrouter.ai/api/v1",
                capabilities=ModelCapabilities(
                    supports_tools=True,
                    supports_vision=False,
                    supports_json_mode=True,
                    supports_streaming=True,
                    supports_reasoning=False,
                    supports_cache_control=False,
                ),
                pricing=ModelPricing(
                    input=0.0,
                    output=0.0,
                ),
                context_window=context,
            ),
        )

    register_model(
        provider=PROVIDER_OPENROUTER,
        model=Model(
            id="meta-llama/llama-3.3-70b-instruct:free",
            api=API_OPENAI_COMPLETIONS,
            provider=PROVIDER_OPENROUTER,
            name="Llama 3.3 70B (Free)",
            base_url="https://openrouter.ai/api/v1",
            capabilities=ModelCapabilities(
                supports_tools=True,
                supports_vision=False,
                supports_json_mode=True,
                supports_streaming=True,
                supports_reasoning=False,
                supports_cache_control=False,
            ),
            pricing=ModelPricing(
                input=0.0,
                output=0.0,
            ),
            context_window=128000,
        ),
    )

    register_model(
        provider=PROVIDER_OPENROUTER,
        model=Model(
            id="openai/gpt-4o-mini",
            api=API_OPENAI_COMPLETIONS,
            provider=PROVIDER_OPENROUTER,
            name="GPT-4o Mini (via OpenRouter)",
            base_url="https://openrouter.ai/api/v1",
            capabilities=ModelCapabilities(
                supports_tools=True,
                supports_vision=True,
                supports_json_mode=True,
                supports_streaming=True,
                supports_reasoning=False,
                supports_cache_control=False,
            ),
            pricing=ModelPricing(
                input=0.15,
                output=0.60,
            ),
            context_window=128000,
        ),
    )

    register_model(
        provider=PROVIDER_OPENROUTER,
        model=Model(
            id="anthropic/claude-3.5-sonnet",
            api=API_OPENAI_COMPLETIONS,
            provider=PROVIDER_OPENROUTER,
            name="Claude 3.5 Sonnet (via OpenRouter)",
            base_url="https://openrouter.ai/api/v1",
            capabilities=ModelCapabilities(
                supports_tools=True,
                supports_vision=True,
                supports_json_mode=True,
                supports_streaming=True,
                supports_reasoning=True,
                supports_cache_control=False,
            ),
            pricing=ModelPricing(
                input=3.00,
                output=15.00,
            ),
            context_window=200000,
        ),
    )

    register_model(
        provider=PROVIDER_OPENROUTER,
        model=Model(
            id="google/gemini-2.0-flash-001",
            api=API_OPENAI_COMPLETIONS,
            provider=PROVIDER_OPENROUTER,
            name="Gemini 2.0 Flash (via OpenRouter)",
            base_url="https://openrouter.ai/api/v1",
            capabilities=ModelCapabilities(
                supports_tools=True,
                supports_vision=True,
                supports_json_mode=True,
                supports_streaming=True,
                supports_reasoning=False,
                supports_cache_control=False,
            ),
            pricing=ModelPricing(
                input=0.10,
                output=0.40,
            ),
            context_window=1000000,
        ),
    )


def _register_google_models() -> None:
    """Register Google models."""
    register_model(
        provider=PROVIDER_GOOGLE,
        model=Model(
            id="gemini-2.0-flash-001",
            api=API_GOOGLE_GENERATIVE_AI,
            provider=PROVIDER_GOOGLE,
            name="Gemini 2.0 Flash",
            capabilities=ModelCapabilities(
                supports_tools=True,
                supports_vision=True,
                supports_json_mode=True,
                supports_streaming=True,
                supports_reasoning=False,
                supports_cache_control=False,
            ),
            pricing=ModelPricing(
                input=0.10,
                output=0.40,
            ),
            context_window=1000000,
        ),
    )


def _register_faux_models() -> None:
    """Register faux/mock models for testing."""
    register_model(
        provider=PROVIDER_FAUX,
        model=Model(
            id="faux",
            api=API_FAUX,
            provider=PROVIDER_FAUX,
            name="Faux (Mock)",
            capabilities=ModelCapabilities(
                supports_tools=True,
                supports_vision=False,
                supports_json_mode=True,
                supports_streaming=True,
                supports_reasoning=False,
                supports_cache_control=False,
            ),
            pricing=ModelPricing(
                input=0.0,
                output=0.0,
            ),
            context_window=128000,
        ),
    )


def _register_kimi_models() -> None:
    """Register Kimi models."""
    register_model(
        provider=PROVIDER_KIMI,
        model=Model(
            id="kimi-k2.5",
            api=API_KIMI,
            provider=PROVIDER_KIMI,
            name="Kimi K2.5",
            base_url="https://api.moonshot.cn/v1",
            capabilities=ModelCapabilities(
                supports_tools=True,
                supports_vision=True,
                supports_json_mode=True,
                supports_streaming=True,
                supports_reasoning=False,
                supports_cache_control=False,
            ),
            pricing=ModelPricing(
                input=0.5,
                output=1.0,
            ),
            context_window=256000,
        ),
    )


def register_all_models() -> None:
    """Register all built-in models."""
    _register_openai_models()
    _register_anthropic_models()
    _register_openrouter_models()
    _register_google_models()
    _register_faux_models()
    _register_kimi_models()
