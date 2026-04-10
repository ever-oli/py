"""Example extension for pi_coding_agent.

This extension demonstrates how to create custom tools and commands
that extend the functionality of pi_coding_agent.
"""

from __future__ import annotations

import uuid
from typing import Any

from pi_coding_agent.tools import Tool


# ============== Tool Functions ==============

async def calculator_tool(
    expression: str,
    precision: int = 2,
    show_steps: bool = False,
) -> dict[str, Any]:
    """Evaluate a mathematical expression.
    
    Args:
        expression: Mathematical expression to evaluate
        precision: Number of decimal places for result
        show_steps: Whether to show calculation steps
        
    Returns:
        Calculation result
    """
    try:
        # Safe evaluation using ast
        import ast
        import operator
        
        # Define allowed operators
        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }
        
        def safe_eval(node):
            if isinstance(node, ast.Num):
                return node.n
            elif isinstance(node, ast.BinOp):
                left = safe_eval(node.left)
                right = safe_eval(node.right)
                op_type = type(node.op)
                if op_type in operators:
                    return operators[op_type](left, right)
                else:
                    raise ValueError(f"Unsupported operator: {op_type}")
            elif isinstance(node, ast.UnaryOp):
                operand = safe_eval(node.operand)
                op_type = type(node.op)
                if op_type in operators:
                    return operators[op_type](operand)
                else:
                    raise ValueError(f"Unsupported unary operator: {op_type}")
            elif isinstance(node, ast.Expression):
                return safe_eval(node.body)
            else:
                raise ValueError(f"Unsupported expression type: {type(node)}")
        
        tree = ast.parse(expression, mode='eval')
        result = safe_eval(tree)
        
        return {
            "success": True,
            "result": round(result, precision) if isinstance(result, float) else result,
            "expression": expression,
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "expression": expression,
        }


def create_calculator_tool(cwd: str | None = None) -> Tool:
    """Create a calculator tool."""
    return {
        "name": "calculator",
        "description": """Evaluate mathematical expressions safely.
        
Supports basic arithmetic: +, -, *, /, //, %, **, and parentheses.

Examples:
- "2 + 2 * 5" = 12
- "(100 - 32) * 5/9" = 37.78 (F to C conversion)
- "2 ** 10" = 1024
""",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate",
                },
                "precision": {
                    "type": "integer",
                    "default": 2,
                    "description": "Number of decimal places",
                },
                "show_steps": {
                    "type": "boolean",
                    "default": False,
                    "description": "Show calculation steps",
                },
            },
            "required": ["expression"],
        },
        "execute": calculator_tool,
    }


async def uuid_tool(
    count: int = 1,
    format: str = "standard",
) -> dict[str, Any]:
    """Generate UUIDs (Universally Unique Identifiers).
    
    Args:
        count: Number of UUIDs to generate
        format: Output format (standard, compact, urn)
        
    Returns:
        Generated UUIDs
    """
    try:
        uuids = []
        for _ in range(count):
            uid = uuid.uuid4()
            
            if format == "compact":
                uuids.append(uid.hex)
            elif format == "urn":
                uuids.append(f"urn:uuid:{uid}")
            else:  # standard
                uuids.append(str(uid))
        
        return {
            "success": True,
            "uuids": uuids,
            "count": len(uuids),
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def create_uuid_tool(cwd: str | None = None) -> Tool:
    """Create a UUID generation tool."""
    return {
        "name": "uuid",
        "description": """Generate UUIDs (Universally Unique Identifiers).
        
Useful for generating unique IDs, API keys, or identifiers.

Formats:
- standard: 550e8400-e29b-41d4-a716-446655440000
- compact: 550e8400e29b41d4a716446655440000
- urn: urn:uuid:550e8400-e29b-41d4-a716-446655440000
""",
        "parameters": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "default": 1,
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Number of UUIDs to generate (max 100)",
                },
                "format": {
                    "type": "string",
                    "enum": ["standard", "compact", "urn"],
                    "default": "standard",
                    "description": "Output format",
                },
            },
        },
        "execute": uuid_tool,
    }


async def qrcode_tool(
    data: str,
    size: int = 10,
    error_correction: str = "M",
) -> dict[str, Any]:
    """Generate a QR code.
    
    Args:
        data: Data to encode in the QR code
        size: Module size (pixels per module)
        error_correction: Error correction level (L, M, Q, H)
        
    Returns:
        QR code as ASCII art or error
    """
    try:
        import qrcode
        
        # Map error correction
        ec_levels = {
            "L": qrcode.constants.ERROR_CORRECT_L,
            "M": qrcode.constants.ERROR_CORRECT_M,
            "Q": qrcode.constants.ERROR_CORRECT_Q,
            "H": qrcode.constants.ERROR_CORRECT_H,
        }
        
        qr = qrcode.QRCode(
            version=None,
            error_correction=ec_levels.get(error_correction, qrcode.constants.ERROR_CORRECT_M),
            box_size=size,
            border=2,
        )
        
        qr.add_data(data)
        qr.make(fit=True)
        
        # Generate ASCII art
        ascii_qr = []
        matrix = qr.get_matrix()
        
        for row in matrix:
            line = ""
            for cell in row:
                line += "██" if cell else "  "
            ascii_qr.append(line)
        
        return {
            "success": True,
            "data": data,
            "ascii": "\n".join(ascii_qr),
            "dimensions": f"{len(matrix)}x{len(matrix[0])}",
        }
        
    except ImportError:
        return {
            "success": False,
            "error": "qrcode module not installed. Run: pip install qrcode[pil]",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def create_qrcode_tool(cwd: str | None = None) -> Tool:
    """Create a QR code generation tool."""
    return {
        "name": "qrcode",
        "description": """Generate QR codes from text or URLs.
        
Returns an ASCII art representation of the QR code.

Error correction levels:
- L: ~7% correction
- M: ~15% correction (default)
- Q: ~25% correction
- H: ~30% correction
""",
        "parameters": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": "Data to encode (text, URL, etc.)",
                },
                "size": {
                    "type": "integer",
                    "default": 10,
                    "description": "Module size (pixels per module)",
                },
                "error_correction": {
                    "type": "string",
                    "enum": ["L", "M", "Q", "H"],
                    "default": "M",
                    "description": "Error correction level",
                },
            },
            "required": ["data"],
        },
        "execute": qrcode_tool,
    }


# ============== Command Functions ==============

def example_command(args: list[str]) -> int:
    """Example CLI command.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code
    """
    print("Example extension command!")
    print(f"Arguments: {args}")
    
    if "--help" in args or "-h" in args:
        print("\nUsage: pi --example-command [options]")
        print("\nOptions:")
        print("  -h, --help    Show this help")
        print("  --version     Show version")
        return 0
    
    print("\nThis is an example of how extensions can add CLI commands.")
    print("Try: pi --calculator '2 + 2'")
    print("     pi --uuid --count 5")
    
    return 0


# ============== Lifecycle Functions ==============

_extension_config: dict[str, Any] = {}


def on_extension_init(config: dict[str, Any]) -> None:
    """Called when the extension is initialized."""
    global _extension_config
    _extension_config = config
    print(f"[Example Extension] Initialized with config: {config}")


def init(config: dict[str, Any]) -> None:
    """Initialize the extension (called by extension manager)."""
    global _extension_config
    _extension_config = config


def shutdown() -> None:
    """Shutdown the extension."""
    print("[Example Extension] Shutdown")
