#!/usr/bin/env python3
"""
Custom Tool Example - Creating and using custom tools.

This example demonstrates:
- Creating custom tool definitions
- Implementing tool execution functions
- Registering tools with the agent
- Tools with state and external APIs
"""

import asyncio
import random
from typing import Any
from datetime import datetime

from pi_coding_agent import create_agent_session
from pi_ai import get_model


# ============================================================================
# Example 1: Simple Calculator Tool
# ============================================================================

async def calculator_execute(expression: str) -> dict[str, Any]:
    """
    Execute a mathematical expression.
    
    Args:
        expression: Mathematical expression to evaluate (e.g., "2 + 2")
    """
    try:
        # Note: eval() is used for demo purposes only.
        # In production, use a safe math parser like ast.literal_eval or numexpr
        result = eval(expression, {"__builtins__": {}}, {
            "abs": abs,
            "max": max,
            "min": min,
            "pow": pow,
            "round": round,
            "sum": sum,
        })
        
        return {
            "content": f"Result: {result}",
            "details": {"expression": expression, "result": result}
        }
    except Exception as e:
        return {
            "content": f"Error evaluating expression: {e}",
            "is_error": True
        }


calculator_tool = {
    "name": "calculator",
    "description": "Evaluate mathematical expressions. Supports basic arithmetic (+, -, *, /), powers (pow), and functions like abs, max, min, round.",
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Mathematical expression to evaluate, e.g., '2 + 2', 'pow(2, 10)', 'max(1, 5, 3)'"
            }
        },
        "required": ["expression"]
    },
    "execute": calculator_execute
}


# ============================================================================
# Example 2: Random Generator Tool with State
# ============================================================================

class RandomGenerator:
    """Tool with internal state to track generation history."""
    
    def __init__(self):
        self.history = []
        self.seed = None
    
    async def generate(self, 
        min_value: int = 0, 
        max_value: int = 100,
        count: int = 1
    ) -> dict[str, Any]:
        """
        Generate random numbers.
        
        Args:
            min_value: Minimum value (inclusive)
            max_value: Maximum value (inclusive)
            count: Number of values to generate
        """
        numbers = [random.randint(min_value, max_value) for _ in range(count)]
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "range": (min_value, max_value),
            "numbers": numbers
        }
        self.history.append(entry)
        
        if count == 1:
            content = f"Generated random number: {numbers[0]}"
        else:
            content = f"Generated {count} random numbers: {numbers}"
        
        return {
            "content": content,
            "details": {"numbers": numbers, "total_generated": len(self.history)}
        }
    
    async def get_history(self) -> dict[str, Any]:
        """Get generation history."""
        if not self.history:
            return {"content": "No numbers generated yet."}
        
        lines = ["Generation History:"]
        for i, entry in enumerate(self.history[-10:], 1):  # Last 10
            lines.append(f"{i}. {entry['numbers']} (range: {entry['range']})")
        
        return {
            "content": "\n".join(lines),
            "details": {"total": len(self.history)}
        }


# Create instance
random_gen = RandomGenerator()

random_generate_tool = {
    "name": "random_generate",
    "description": "Generate random numbers within a specified range",
    "parameters": {
        "type": "object",
        "properties": {
            "min_value": {"type": "integer", "default": 0, "description": "Minimum value"},
            "max_value": {"type": "integer", "default": 100, "description": "Maximum value"},
            "count": {"type": "integer", "default": 1, "description": "How many numbers to generate"}
        }
    },
    "execute": random_gen.generate
}

random_history_tool = {
    "name": "random_history",
    "description": "View history of previously generated random numbers",
    "parameters": {"type": "object", "properties": {}},
    "execute": random_gen.get_history
}


# ============================================================================
# Example 3: Data Lookup Tool (Simulated Database)
# ============================================================================

# Simulated database
USERS_DB = {
    "alice": {"name": "Alice Smith", "role": "Engineer", "department": "Engineering"},
    "bob": {"name": "Bob Johnson", "role": "Designer", "department": "Design"},
    "charlie": {"name": "Charlie Brown", "role": "Manager", "department": "Engineering"},
}

async def lookup_user(username: str) -> dict[str, Any]:
    """
    Look up user information.
    
    Args:
        username: Username to look up
    """
    username = username.lower()
    
    if username not in USERS_DB:
        return {
            "content": f"User '{username}' not found. Available users: {', '.join(USERS_DB.keys())}",
            "is_error": True
        }
    
    user = USERS_DB[username]
    return {
        "content": f"User: {user['name']}\nRole: {user['role']}\nDepartment: {user['department']}",
        "details": user
    }


lookup_user_tool = {
    "name": "lookup_user",
    "description": "Look up information about a user by username",
    "parameters": {
        "type": "object",
        "properties": {
            "username": {
                "type": "string",
                "description": "Username to look up (e.g., 'alice', 'bob', 'charlie')"
            }
        },
        "required": ["username"]
    },
    "execute": lookup_user
}


# ============================================================================
# Example 4: File Analysis Tool
# ============================================================================

async def analyze_file(file_path: str) -> dict[str, Any]:
    """
    Analyze a file and return statistics.
    
    Args:
        file_path: Path to the file to analyze
    """
    from pathlib import Path
    
    path = Path(file_path)
    
    if not path.exists():
        return {
            "content": f"File not found: {file_path}",
            "is_error": True
        }
    
    try:
        content = path.read_text()
        lines = content.split('\n')
        words = content.split()
        
        stats = {
            "file_name": path.name,
            "file_size": path.stat().st_size,
            "line_count": len(lines),
            "word_count": len(words),
            "char_count": len(content),
            "extension": path.suffix,
        }
        
        report = f"""File Analysis: {path.name}
- Size: {stats['file_size']} bytes
- Lines: {stats['line_count']}
- Words: {stats['word_count']}
- Characters: {stats['char_count']}
- Extension: {stats['extension'] or 'none'}"""
        
        return {
            "content": report,
            "details": stats
        }
        
    except Exception as e:
        return {
            "content": f"Error reading file: {e}",
            "is_error": True
        }


analyze_file_tool = {
    "name": "analyze_file",
    "description": "Analyze a file and return statistics like size, line count, word count",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to analyze"
            }
        },
        "required": ["file_path"]
    },
    "execute": analyze_file
}


# ============================================================================
# Example 5: Current Time Tool
# ============================================================================

async def get_current_time(format: str = "%Y-%m-%d %H:%M:%S") -> dict[str, Any]:
    """
    Get the current date and time.
    
    Args:
        format: Date/time format string (Python strftime format)
    """
    now = datetime.now()
    formatted = now.strftime(format)
    
    return {
        "content": f"Current time: {formatted}",
        "details": {
            "iso": now.isoformat(),
            "timestamp": now.timestamp(),
            "formatted": formatted,
        }
    }


current_time_tool = {
    "name": "current_time",
    "description": "Get the current date and time",
    "parameters": {
        "type": "object",
        "properties": {
            "format": {
                "type": "string",
                "default": "%Y-%m-%d %H:%M:%S",
                "description": "Date format (default: YYYY-MM-DD HH:MM:SS)"
            }
        }
    },
    "execute": get_current_time
}


# ============================================================================
# Main Examples
# ============================================================================

async def calculator_example():
    """Demo the calculator tool."""
    print("=" * 60)
    print("Calculator Tool Example")
    print("=" * 60)
    
    result = await create_agent_session(
        model=get_model("openai", "gpt-4o-mini"),
        custom_tools=[calculator_tool],
        no_session=True,
    )
    session = result.session
    
    response = await session.run("Calculate 123 * 456 and then divide by 2")
    print(f"User: Calculate 123 * 456 and then divide by 2")
    print(f"Assistant: {response['content']}")
    
    if response.get('tool_calls'):
        print(f"\nTools used:")
        for tc in response['tool_calls']:
            print(f"  - {tc['name']}: {tc['arguments']}")
    print()


async def random_generator_example():
    """Demo the random generator tool."""
    print("=" * 60)
    print("Random Generator Tool Example")
    print("=" * 60)
    
    result = await create_agent_session(
        model=get_model("openai", "gpt-4o-mini"),
        custom_tools=[random_generate_tool, random_history_tool],
        no_session=True,
    )
    session = result.session
    
    response = await session.run("Generate 5 random numbers between 1 and 100")
    print(f"User: Generate 5 random numbers between 1 and 100")
    print(f"Assistant: {response['content']}")
    
    # Generate more
    response2 = await session.run("Generate 3 more and show me the history")
    print(f"\nUser: Generate 3 more and show me the history")
    print(f"Assistant: {response2['content']}")
    print()


async def user_lookup_example():
    """Demo the user lookup tool."""
    print("=" * 60)
    print("User Lookup Tool Example")
    print("=" * 60)
    
    result = await create_agent_session(
        model=get_model("openai", "gpt-4o-mini"),
        custom_tools=[lookup_user_tool],
        no_session=True,
    )
    session = result.session
    
    response = await session.run("Look up information about Alice")
    print(f"User: Look up information about Alice")
    print(f"Assistant: {response['content']}")
    
    response2 = await session.run("Now look up Bob and Charlie")
    print(f"\nUser: Now look up Bob and Charlie")
    print(f"Assistant: {response2['content']}")
    print()


async def file_analysis_example():
    """Demo the file analysis tool."""
    print("=" * 60)
    print("File Analysis Tool Example")
    print("=" * 60)
    
    # Create a test file
    test_file = "/tmp/test_analysis.txt"
    with open(test_file, "w") as f:
        f.write("Line 1\nLine 2\nLine 3\n")
    
    result = await create_agent_session(
        model=get_model("openai", "gpt-4o-mini"),
        custom_tools=[analyze_file_tool],
        no_session=True,
    )
    session = result.session
    
    response = await session.run(f"Analyze the file at {test_file}")
    print(f"User: Analyze the file at {test_file}")
    print(f"Assistant:\n{response['content']}")
    
    # Cleanup
    import os
    os.remove(test_file)
    print()


async def combined_tools_example():
    """Demo using multiple custom tools together."""
    print("=" * 60)
    print("Combined Tools Example")
    print("=" * 60)
    
    all_custom_tools = [
        calculator_tool,
        random_generate_tool,
        lookup_user_tool,
        current_time_tool,
    ]
    
    result = await create_agent_session(
        model=get_model("openai", "gpt-4o"),
        custom_tools=all_custom_tools,
        no_session=True,
    )
    session = result.session
    
    print("Available custom tools:")
    for tool in session.get_tools():
        if tool["name"] in ["calculator", "random_generate", "lookup_user", "current_time"]:
            print(f"  - {tool['name']}: {tool['description'][:50]}...")
    
    response = await session.run(
        "What's the current time? Also, who is charlie and what's 2+2?"
    )
    print(f"\nUser: What's the current time? Also, who is charlie and what's 2+2?")
    print(f"Assistant: {response['content']}")
    
    if response.get('tool_calls'):
        print(f"\nTools used: {len(response['tool_calls'])}")
        for tc in response['tool_calls']:
            print(f"  - {tc['name']}")
    print()


async def main():
    """Run all examples."""
    print("\nPi Coding Agent - Custom Tool Examples\n")
    print("These examples show how to create and use custom tools.\n")
    
    await calculator_example()
    await random_generator_example()
    await user_lookup_example()
    await file_analysis_example()
    await combined_tools_example()
    
    print("=" * 60)
    print("Examples complete!")
    print("=" * 60)
    print("\nTo create your own tools:")
    print("1. Define an async execute function")
    print("2. Create a tool dict with name, description, parameters, execute")
    print("3. Pass custom_tools to create_agent_session()")


if __name__ == "__main__":
    asyncio.run(main())
