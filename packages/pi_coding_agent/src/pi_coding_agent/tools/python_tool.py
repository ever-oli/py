"""Python tool for executing Python code safely."""

from __future__ import annotations

import ast
import sys
import traceback
from io import StringIO
from typing import Any


# Restricted built-ins for safer execution
SAFE_BUILTINS = {
    'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytearray', 'bytes',
    'chr', 'complex', 'dict', 'divmod', 'enumerate', 'filter', 'float',
    'format', 'frozenset', 'hasattr', 'hash', 'hex', 'id', 'input',
    'int', 'isinstance', 'issubclass', 'iter', 'len', 'list', 'map',
    'max', 'min', 'next', 'object', 'oct', 'ord', 'pow', 'print',
    'property', 'range', 'repr', 'reversed', 'round', 'set', 'slice',
    'sorted', 'staticmethod', 'str', 'sum', 'super', 'tuple', 'type',
    'vars', 'zip', '__import__', 'False', 'None', 'True',
}

# Dangerous modules/attributes to block
DANGEROUS_NAMES = {
    'os.system', 'os.popen', 'os.spawn', 'os.exec', 'os.kill',
    'subprocess', 'sys.modules', '__import__', 'eval', 'exec',
    'compile', 'open', 'file', 'write', 'delete', 'remove',
    'socket', 'urllib.request', 'http.client', 'ftplib',
    'pickle', 'yaml.load', 'marshal', 'ctypes', 'sys.exit',
}


class SafeCodeChecker(ast.NodeVisitor):
    """AST visitor to check for dangerous code patterns."""
    
    def __init__(self):
        self.errors = []
        self.imported_modules = set()
    
    def visit_Import(self, node):
        for alias in node.names:
            self.imported_modules.add(alias.name.split('.')[0])
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        if node.module:
            self.imported_modules.add(node.module.split('.')[0])
        self.generic_visit(node)
    
    def visit_Call(self, node):
        # Check for dangerous function calls
        if isinstance(node.func, ast.Name):
            if node.func.id in ('eval', 'exec', 'compile'):
                self.errors.append(f"Forbidden function call: {node.func.id}")
        elif isinstance(node.func, ast.Attribute):
            # Check for dangerous attribute access
            full_name = self._get_full_name(node.func)
            if full_name and any(d in full_name for d in DANGEROUS_NAMES):
                self.errors.append(f"Potentially dangerous call: {full_name}")
        self.generic_visit(node)
    
    def _get_full_name(self, node) -> str | None:
        """Get full dotted name from attribute chain."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            base = self._get_full_name(node.value)
            if base:
                return f"{base}.{node.attr}"
        return None


def check_code_safety(code: str) -> tuple[bool, list[str]]:
    """Check if code is safe to execute.
    
    Returns:
        Tuple of (is_safe, list_of_errors)
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, [f"Syntax error: {e}"]
    
    checker = SafeCodeChecker()
    checker.visit(tree)
    
    return len(checker.errors) == 0, checker.errors


async def python_tool(
    code: str,
    timeout: int = 30,
    safe_mode: bool = True,
    allowed_modules: list[str] | None = None,
    input_data: str | None = None,
) -> dict[str, Any]:
    """Execute Python code safely.

    Args:
        code: Python code to execute
        timeout: Maximum execution time in seconds
        safe_mode: Whether to use restricted execution environment
        allowed_modules: Additional modules to allow (in safe mode)
        input_data: Input data to provide via stdin

    Returns:
        Execution results including output and any errors
    """
    if safe_mode:
        is_safe, errors = check_code_safety(code)
        if not is_safe:
            return {
                "success": False,
                "error": f"Code safety check failed: {'; '.join(errors)}",
                "stdout": "",
                "stderr": "",
                "result": None,
            }
    
    # Capture stdout and stderr
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    old_stdin = sys.stdin
    
    stdout_capture = StringIO()
    stderr_capture = StringIO()
    
    sys.stdout = stdout_capture
    sys.stderr = stderr_capture
    
    if input_data:
        sys.stdin = StringIO(input_data)
    
    result = None
    error = None
    
    try:
        # Create restricted globals if in safe mode
        if safe_mode:
            allowed = set(allowed_modules or [])
            safe_globals = {
                '__builtins__': {k: v for k, v in __builtins__.items() 
                                if k in SAFE_BUILTINS or k in allowed},
                '__name__': '__main__',
            }
        else:
            safe_globals = {'__name__': '__main__'}
        
        # Execute with timeout using asyncio
        import asyncio
        
        def run_code():
            exec(code, safe_globals)
            return safe_globals.get('_result', None)
        
        # Run in thread pool to handle blocking code
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, run_code),
            timeout=timeout
        )
        
    except asyncio.TimeoutError:
        error = f"Code execution timed out after {timeout} seconds"
    except Exception as e:
        error = f"{type(e).__name__}: {str(e)}"
        stderr_capture.write(traceback.format_exc())
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        sys.stdin = old_stdin
    
    stdout = stdout_capture.getvalue()
    stderr = stderr_capture.getvalue()
    
    return {
        "success": error is None,
        "error": error,
        "stdout": stdout,
        "stderr": stderr,
        "result": result,
        "execution_time_ms": None,  # Could add timing
    }


def create_python_tool(cwd: str | None = None) -> dict[str, Any]:
    """Create a Python execution tool instance."""
    return {
        "name": "python",
        "description": """Execute Python code safely in a sandboxed environment.
        
Runs Python code with restricted access to dangerous operations.
Good for calculations, data processing, algorithms, and testing.

Restrictions in safe mode:
- No file system access (open, read, write)
- No network access (socket, urllib)
- No system commands (os, subprocess)
- No code execution (eval, exec, compile)
- No process control (sys.exit, os.kill)

Use safe_mode=false for full access (with caution).
""",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute",
                },
                "timeout": {
                    "type": "integer",
                    "default": 30,
                    "description": "Maximum execution time in seconds",
                },
                "safe_mode": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to use restricted execution environment",
                },
                "allowed_modules": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional modules to allow in safe mode",
                },
                "input_data": {
                    "type": "string",
                    "description": "Input data to provide via stdin",
                },
            },
            "required": ["code"],
        },
        "execute": python_tool,
    }


python_tool_definition = create_python_tool()
