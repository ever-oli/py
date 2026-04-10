"""Process tool for managing background processes."""

from __future__ import annotations

import asyncio
import os
import signal
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# In-memory store for background processes
_processes: dict[str, "BackgroundProcess"] = {}
_process_counter = 0


@dataclass
class BackgroundProcess:
    """Represents a background process."""
    id: str
    command: str
    proc: asyncio.subprocess.Process
    created_at: datetime
    cwd: str
    env: dict[str, str] | None
    stdout_buffer: list[str] = field(default_factory=list)
    stderr_buffer: list[str] = field(default_factory=list)
    completed: bool = False
    return_code: int | None = None


async def process_tool(
    action: str,
    command: list[str] | str | None = None,
    process_id: str | None = None,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    signal_name: str | None = None,
    timeout: int | None = None,
    background: bool = False,
) -> dict[str, Any]:
    """Process management tool for running and managing system processes.
    
    Args:
        action: Action to perform (run, status, list, kill, wait, read)
        command: Command to run (for 'run' action)
        process_id: Process ID for management actions
        cwd: Working directory for the process
        env: Environment variables
        signal_name: Signal to send (SIGTERM, SIGKILL, etc.)
        timeout: Timeout in seconds
        background: Whether to run in background
        
    Returns:
        Process information and results
        
    Example:
        >>> # Run a command
        ... result = await process_tool("run", command=["ls", "-la"])
        
        >>> # Run in background
        ... result = await process_tool(
        ...     "run", 
        ...     command=["sleep", "60"],
        ...     background=True
        ... )
        
        >>> # Check status
        ... result = await process_tool("status", process_id="proc_1")
        
        >>> # List all background processes
        ... result = await process_tool("list")
        
        >>> # Kill a process
        ... result = await process_tool("kill", process_id="proc_1")
    """
    global _process_counter
    
    if action == "run":
        if not command:
            return {
                "success": False,
                "error": "Command required for 'run' action",
            }
        
        # Convert string command to list if needed
        if isinstance(command, str):
            import shlex
            command = shlex.split(command)
        
        if background:
            # Run in background
            _process_counter += 1
            proc_id = f"proc_{_process_counter}"
            
            try:
                proc = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    env={**os.environ, **(env or {})},
                )
                
                bg_proc = BackgroundProcess(
                    id=proc_id,
                    command=" ".join(command),
                    proc=proc,
                    created_at=datetime.now(),
                    cwd=cwd or os.getcwd(),
                    env=env,
                )
                
                _processes[proc_id] = bg_proc
                
                # Start background reader
                asyncio.create_task(_read_process_output(bg_proc))
                
                return {
                    "success": True,
                    "process_id": proc_id,
                    "pid": proc.pid,
                    "command": " ".join(command),
                    "status": "running",
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                }
        else:
            # Run synchronously with timeout
            try:
                proc = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    env={**os.environ, **(env or {})},
                )
                
                if timeout:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=timeout
                    )
                else:
                    stdout, stderr = await proc.communicate()
                
                return {
                    "success": proc.returncode == 0,
                    "return_code": proc.returncode,
                    "stdout": stdout.decode('utf-8', errors='replace'),
                    "stderr": stderr.decode('utf-8', errors='replace'),
                    "command": " ".join(command),
                }
                
            except asyncio.TimeoutError:
                proc.kill()
                return {
                    "success": False,
                    "error": f"Command timed out after {timeout} seconds",
                    "return_code": -1,
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                }
    
    elif action == "status":
        if not process_id:
            return {
                "success": False,
                "error": "process_id required for 'status' action",
            }
        
        if process_id not in _processes:
            return {
                "success": False,
                "error": f"Process {process_id} not found",
            }
        
        proc = _processes[process_id]
        
        # Check if still running
        if proc.proc.returncode is None:
            status = "running"
        else:
            status = "completed" if not proc.completed else "completed"
            proc.return_code = proc.proc.returncode
            proc.completed = True
        
        return {
            "success": True,
            "process_id": process_id,
            "pid": proc.proc.pid,
            "status": status,
            "return_code": proc.return_code,
            "command": proc.command,
            "created_at": proc.created_at.isoformat(),
            "cwd": proc.cwd,
        }
    
    elif action == "list":
        processes = []
        for proc_id, proc in _processes.items():
            # Update status
            if proc.proc.returncode is not None:
                proc.completed = True
                proc.return_code = proc.proc.returncode
            
            processes.append({
                "process_id": proc_id,
                "pid": proc.proc.pid,
                "status": "completed" if proc.completed else "running",
                "return_code": proc.return_code,
                "command": proc.command,
                "created_at": proc.created_at.isoformat(),
            })
        
        return {
            "success": True,
            "processes": processes,
            "count": len(processes),
        }
    
    elif action == "read":
        if not process_id:
            return {
                "success": False,
                "error": "process_id required for 'read' action",
            }
        
        if process_id not in _processes:
            return {
                "success": False,
                "error": f"Process {process_id} not found",
            }
        
        proc = _processes[process_id]
        
        stdout = "\n".join(proc.stdout_buffer)
        stderr = "\n".join(proc.stderr_buffer)
        
        return {
            "success": True,
            "process_id": process_id,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_lines": len(proc.stdout_buffer),
            "stderr_lines": len(proc.stderr_buffer),
        }
    
    elif action == "kill":
        if not process_id:
            return {
                "success": False,
                "error": "process_id required for 'kill' action",
            }
        
        if process_id not in _processes:
            return {
                "success": False,
                "error": f"Process {process_id} not found",
            }
        
        proc = _processes[process_id]
        
        # Determine signal
        sig = signal.SIGTERM
        if signal_name:
            sig = getattr(signal, signal_name, signal.SIGTERM)
        
        try:
            proc.proc.send_signal(sig)
            
            # Wait a bit for graceful shutdown
            try:
                await asyncio.wait_for(proc.proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                if not proc.proc.returncode:
                    proc.proc.kill()
                    await proc.proc.wait()
            
            proc.completed = True
            proc.return_code = proc.proc.returncode
            
            return {
                "success": True,
                "process_id": process_id,
                "return_code": proc.return_code,
                "message": f"Process {process_id} terminated",
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    elif action == "wait":
        if not process_id:
            return {
                "success": False,
                "error": "process_id required for 'wait' action",
            }
        
        if process_id not in _processes:
            return {
                "success": False,
                "error": f"Process {process_id} not found",
            }
        
        proc = _processes[process_id]
        
        try:
            if timeout:
                await asyncio.wait_for(proc.proc.wait(), timeout=timeout)
            else:
                await proc.proc.wait()
            
            proc.completed = True
            proc.return_code = proc.proc.returncode
            
            stdout = "\n".join(proc.stdout_buffer)
            stderr = "\n".join(proc.stderr_buffer)
            
            return {
                "success": proc.return_code == 0,
                "process_id": process_id,
                "return_code": proc.return_code,
                "stdout": stdout,
                "stderr": stderr,
            }
            
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Wait timed out after {timeout} seconds",
                "status": "running",
            }
    
    elif action == "cleanup":
        """Remove completed processes from memory."""
        removed = []
        for proc_id in list(_processes.keys()):
            proc = _processes[proc_id]
            if proc.completed or (proc.proc.returncode is not None):
                del _processes[proc_id]
                removed.append(proc_id)
        
        return {
            "success": True,
            "removed": removed,
            "count": len(removed),
        }
    
    else:
        return {
            "success": False,
            "error": f"Unknown action: {action}",
        }


async def _read_process_output(proc: BackgroundProcess) -> None:
    """Read output from a background process."""
    try:
        while True:
            if proc.proc.returncode is not None:
                break
            
            # Read stdout
            try:
                line = await asyncio.wait_for(
                    proc.proc.stdout.readline(),
                    timeout=0.1
                )
                if line:
                    proc.stdout_buffer.append(line.decode('utf-8', errors='replace').rstrip())
            except asyncio.TimeoutError:
                pass
            
            # Read stderr
            try:
                line = await asyncio.wait_for(
                    proc.proc.stderr.readline(),
                    timeout=0.1
                )
                if line:
                    proc.stderr_buffer.append(line.decode('utf-8', errors='replace').rstrip())
            except asyncio.TimeoutError:
                pass
        
        # Read remaining output
        stdout_remaining = await proc.proc.stdout.read()
        if stdout_remaining:
            for line in stdout_remaining.decode('utf-8', errors='replace').split('\n'):
                if line:
                    proc.stdout_buffer.append(line)
        
        stderr_remaining = await proc.proc.stderr.read()
        if stderr_remaining:
            for line in stderr_remaining.decode('utf-8', errors='replace').split('\n'):
                if line:
                    proc.stderr_buffer.append(line)
        
        proc.completed = True
        proc.return_code = proc.proc.returncode
        
    except Exception:
        proc.completed = True


def create_process_tool(cwd: str | None = None) -> dict[str, Any]:
    """Create a process tool instance."""
    return {
        "name": "process",
        "description": """Process management for running and managing system processes.
        
Run commands synchronously or in background, check status, read output, and control processes.

Actions:
- run: Execute a command (set background=true for async)
- status: Check process status
- list: List all background processes
- read: Read process output
- kill: Terminate a process
- wait: Wait for a process to complete
- cleanup: Remove completed processes from memory

Examples:
Run command: {"action": "run", "command": ["ls", "-la"]}
Background task: {"action": "run", "command": ["sleep", "60"], "background": true}
Check status: {"action": "status", "process_id": "proc_1"}
Kill process: {"action": "kill", "process_id": "proc_1"}
""",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["run", "status", "list", "kill", "wait", "read", "cleanup"],
                    "description": "Action to perform",
                },
                "command": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ],
                    "description": "Command to run (for 'run' action)",
                },
                "process_id": {
                    "type": "string",
                    "description": "Process ID for management actions",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory",
                },
                "env": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Environment variables",
                },
                "signal_name": {
                    "type": "string",
                    "description": "Signal to send (SIGTERM, SIGKILL, etc.)",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                },
                "background": {
                    "type": "boolean",
                    "default": False,
                    "description": "Run in background",
                },
            },
            "required": ["action"],
        },
        "execute": process_tool,
    }


process_tool_definition = create_process_tool()
