"""
Simple options builder and reasoning helpers.
Python port of TypeScript providers/simple-options.ts
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import (
        Model,
        SimpleStreamOptions,
        StreamOptions,
        ThinkingBudgets,
        ThinkingLevel,
    )


def build_base_options(
    model: Model,
    options: SimpleStreamOptions | None = None,
    api_key: str | None = None,
) -> StreamOptions:
    """
    Build base stream options from simple options.

    Args:
        model: The model to use
        options: Simple stream options
        api_key: Optional API key

    Returns:
        StreamOptions with defaults applied
    """
    from ..types import StreamOptions

    return StreamOptions(
        temperature=options.temperature if options else None,
        max_tokens=options.max_tokens if options else min(model.context_window, 32000),
        signal=options.signal if options else None,
        api_key=api_key or (options.api_key if options else None),
        cache_retention=options.cache_retention if options else None,
        session_id=options.session_id if options else None,
        headers=options.headers if options else None,
        on_payload=options.on_payload if options else None,
        max_retry_delay_ms=options.max_retry_delay_ms if options else 60000,
        metadata=options.metadata if options else None,
    )


def clamp_reasoning(effort: ThinkingLevel | None) -> ThinkingLevel | None:
    """
    Clamp xhigh reasoning to high.

    Args:
        effort: The thinking level

    Returns:
        The clamped thinking level
    """
    if effort == "xhigh":
        return "high"
    return effort


def adjust_max_tokens_for_thinking(
    base_max_tokens: int,
    model_max_tokens: int,
    reasoning_level: ThinkingLevel,
    custom_budgets: ThinkingBudgets | None = None,
) -> dict[str, int]:
    """
    Adjust max tokens to account for thinking budget.

    Args:
        base_max_tokens: The base max tokens
        model_max_tokens: The model's max tokens
        reasoning_level: The reasoning level
        custom_budgets: Custom thinking budgets

    Returns:
        Dict with max_tokens and thinking_budget
    """
    default_budgets = {
        "minimal": 1024,
        "low": 2048,
        "medium": 8192,
        "high": 16384,
    }

    budgets = {**default_budgets}
    if custom_budgets:
        if custom_budgets.minimal is not None:
            budgets["minimal"] = custom_budgets.minimal
        if custom_budgets.low is not None:
            budgets["low"] = custom_budgets.low
        if custom_budgets.medium is not None:
            budgets["medium"] = custom_budgets.medium
        if custom_budgets.high is not None:
            budgets["high"] = custom_budgets.high

    min_output_tokens = 1024
    level = clamp_reasoning(reasoning_level) or "medium"
    thinking_budget = budgets.get(level, 8192)
    max_tokens = min(base_max_tokens + thinking_budget, model_max_tokens)

    if max_tokens <= thinking_budget:
        thinking_budget = max(0, max_tokens - min_output_tokens)

    return {"max_tokens": max_tokens, "thinking_budget": thinking_budget}


__all__ = [
    "build_base_options",
    "clamp_reasoning",
    "adjust_max_tokens_for_thinking",
]
