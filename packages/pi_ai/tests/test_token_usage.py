"""Tests for token usage calculation."""
from __future__ import annotations

import pytest
from pi_ai.types import (
    AssistantMessage,
    Cost,
    TextContent,
    ToolCall,
    Usage,
    UserMessage,
)


class TestTokenUsage:
    """Test token usage calculations."""

    def test_basic_token_counting(self):
        """Test basic token counting."""
        usage = Usage(
            input=100,
            output=50,
            total_tokens=150,
        )
        assert usage.input == 100
        assert usage.output == 50
        assert usage.total_tokens == 150

    def test_token_counting_with_cache(self):
        """Test token counting with cache."""
        usage = Usage(
            input=1000,
            output=500,
            cache_read=800,
            cache_write=200,
            total_tokens=1500,
        )
        assert usage.cache_read == 800
        assert usage.cache_write == 200

    def test_cost_calculation_per_mtok(self):
        """Test cost calculation per million tokens."""
        # Example: GPT-4 pricing
        input_cost_per_mtok = 30.0  # $30 per million input tokens
        output_cost_per_mtok = 60.0  # $60 per million output tokens
        
        input_tokens = 2000
        output_tokens = 1000
        
        input_cost = (input_tokens / 1_000_000) * input_cost_per_mtok
        output_cost = (output_tokens / 1_000_000) * output_cost_per_mtok
        total_cost = input_cost + output_cost
        
        assert abs(input_cost - 0.06) < 0.001  # $0.06
        assert abs(output_cost - 0.06) < 0.001  # $0.06
        assert abs(total_cost - 0.12) < 0.001  # $0.12

    def test_cost_from_usage(self):
        """Test extracting cost from usage."""
        cost = Cost(
            input=0.06,
            output=0.06,
            cache_read=0.001,
            cache_write=0.002,
            total=0.123,
        )
        
        usage = Usage(
            input=2000,
            output=1000,
            cache_read=100,
            cache_write=50,
            cost=cost,
        )
        
        assert abs(usage.cost.total - 0.123) < 0.0001
        assert abs(usage.cost.input - 0.06) < 0.0001
        assert abs(usage.cost.output - 0.06) < 0.0001

    def test_usage_default_values(self):
        """Test usage default values."""
        usage = Usage()
        
        assert usage.input == 0
        assert usage.output == 0
        assert usage.cache_read == 0
        assert usage.cache_write == 0
        assert usage.total_tokens == 0
        assert usage.cost.total == 0.0

    def test_cost_default_values(self):
        """Test cost default values."""
        cost = Cost()
        
        assert cost.input == 0.0
        assert cost.output == 0.0
        assert cost.cache_read == 0.0
        assert cost.cache_write == 0.0
        assert cost.total == 0.0

    def test_usage_with_message(self):
        """Test usage associated with a message."""
        from pi_ai.types import StopReason
        
        usage = Usage(
            input=100,
            output=50,
            total_tokens=150,
            cost=Cost(input=0.003, output=0.003, total=0.006),
        )
        
        msg = AssistantMessage(
            role="assistant",
            content=[TextContent(type="text", text="Hello")],
            stop_reason=StopReason.STOP,
            usage=usage,
        )
        
        assert msg.usage.input == 100
        assert msg.usage.output == 50
        assert abs(msg.usage.cost.total - 0.006) < 0.0001

    def test_aggregate_usage(self):
        """Test aggregating usage across multiple calls."""
        usages = [
            Usage(input=100, output=50, cost=Cost(input=0.003, output=0.003, total=0.006)),
            Usage(input=200, output=100, cost=Cost(input=0.006, output=0.006, total=0.012)),
            Usage(input=150, output=75, cost=Cost(input=0.0045, output=0.0045, total=0.009)),
        ]
        
        total_input = sum(u.input for u in usages)
        total_output = sum(u.output for u in usages)
        total_cost = sum(u.cost.total for u in usages)
        
        assert total_input == 450
        assert total_output == 225
        assert abs(total_cost - 0.027) < 0.0001

    def test_cache_token_pricing(self):
        """Test cache token pricing (Anthropic style)."""
        # Anthropic cache pricing example
        # Input: $3/Mtok, Cache write: $3.75/Mtok, Cache read: $0.30/Mtok
        # Output: $15/Mtok
        
        prompt_tokens = 10000
        cache_write_tokens = 10000
        cache_read_tokens = 90000  # 90% cache hit
        output_tokens = 5000
        
        input_cost = (prompt_tokens / 1_000_000) * 3.0
        cache_write_cost = (cache_write_tokens / 1_000_000) * 3.75
        cache_read_cost = (cache_read_tokens / 1_000_000) * 0.30
        output_cost = (output_tokens / 1_000_000) * 15.0
        
        total_cost = input_cost + cache_write_cost + cache_read_cost + output_cost
        
        assert abs(input_cost - 0.03) < 0.001
        assert abs(cache_write_cost - 0.0375) < 0.001
        assert abs(cache_read_cost - 0.027) < 0.001
        assert abs(output_cost - 0.075) < 0.001
        assert abs(total_cost - 0.1695) < 0.001

    def test_usage_with_tool_calls(self):
        """Test usage with tool calls."""
        from pi_ai.types import StopReason
        
        usage = Usage(
            input=500,  # Includes tool definitions
            output=200,  # Tool call arguments
            total_tokens=700,
        )
        
        msg = AssistantMessage(
            role="assistant",
            content=[
                ToolCall(
                    id="call_1",
                    name="search",
                    arguments='{"query": "test"}',
                )
            ],
            stop_reason=StopReason.TOOL_USE,
            usage=usage,
        )
        
        assert msg.usage.input == 500
        assert msg.usage.output == 200

    def test_cost_rounding(self):
        """Test cost rounding behavior."""
        cost = Cost(
            input=0.000001,
            output=0.000002,
            total=0.000003,
        )
        
        # Very small costs should still be accurate
        assert abs(cost.input + cost.output - cost.total) < 0.0000001

    def test_usage_immutability(self):
        """Test that usage fields can be modified (dataclass behavior)."""
        usage = Usage(input=100, output=50)
        
        # Dataclasses are mutable by default
        usage.input = 200
        assert usage.input == 200

    def test_usage_equality(self):
        """Test usage equality comparison."""
        usage1 = Usage(input=100, output=50, cost=Cost(total=0.01))
        usage2 = Usage(input=100, output=50, cost=Cost(total=0.01))
        usage3 = Usage(input=200, output=50)
        
        assert usage1 == usage2
        assert usage1 != usage3

    def test_usage_string_representation(self):
        """Test usage string representation."""
        usage = Usage(
            input=1000,
            output=500,
            cache_read=800,
            total_tokens=1500,
            cost=Cost(total=0.015),
        )
        
        # String representation should contain key info
        usage_str = str(usage)
        assert "Usage" in usage_str or "input" in usage_str.lower()
