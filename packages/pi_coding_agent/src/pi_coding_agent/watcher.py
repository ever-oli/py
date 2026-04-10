"""File watching functionality for pi_coding_agent.

Watch files for changes and auto-run commands when they change.
"""

from __future__ import annotations

import asyncio
import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class WatchTask:
    """A file watch task."""
    id: str
    patterns: list[str]
    command: str | Callable
    cwd: Path
    recursive: bool = True
    debounce_ms: int = 300
    running: bool = False
    _task: asyncio.Task | None = field(default=None, repr=False)
    _last_run: float = field(default=0)


class FileWatcher:
    """File watcher for auto-running on changes."""
    
    def __init__(self):
        self._tasks: dict[str, WatchTask] = {}
        self._task_counter = 0
        self._observer = None
        self._running = False
    
    def _get_watchdog_observer(self):
        """Get or create watchdog observer."""
        if self._observer is None:
            try:
                from watchdog.observers import Observer
                self._observer = Observer()
                self._observer.start()
            except ImportError:
                return None
        return self._observer
    
    async def add_watch(
        self,
        patterns: list[str] | str,
        command: str | Callable,
        cwd: str | Path | None = None,
        recursive: bool = True,
        debounce_ms: int = 300,
    ) -> str:
        """Add a file watch task.
        
        Args:
            patterns: File patterns to watch (e.g., ["*.py", "src/**/*.js"])
            command: Command to run on change (string or callable)
            cwd: Working directory
            recursive: Whether to watch recursively
            debounce_ms: Debounce time in milliseconds
            
        Returns:
            Watch task ID
        """
        self._task_counter += 1
        task_id = f"watch_{self._task_counter}"
        
        if isinstance(patterns, str):
            patterns = [patterns]
        
        task = WatchTask(
            id=task_id,
            patterns=patterns,
            command=command,
            cwd=Path(cwd) if cwd else Path.cwd(),
            recursive=recursive,
            debounce_ms=debounce_ms,
        )
        
        self._tasks[task_id] = task
        
        # Start watching
        await self._start_watch(task)
        
        return task_id
    
    async def _start_watch(self, task: WatchTask) -> None:
        """Start watching for a task."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler, FileSystemEvent
            
            class ChangeHandler(FileSystemEventHandler):
                def __init__(self, task: WatchTask, callback: Callable):
                    self.task = task
                    self.callback = callback
                    self._debounce_timer: asyncio.TimerHandle | None = None
                
                def on_any_event(self, event: FileSystemEvent):
                    if event.is_directory:
                        return
                    
                    # Check if file matches patterns
                    file_path = Path(event.src_path)
                    if not self._matches_patterns(file_path):
                        return
                    
                    # Debounce
                    if self._debounce_timer:
                        self._debounce_timer.cancel()
                    
                    loop = asyncio.get_event_loop()
                    self._debounce_timer = loop.call_later(
                        self.task.debounce_ms / 1000,
                        lambda: asyncio.create_task(self.callback(file_path))
                    )
                
                def _matches_patterns(self, file_path: Path) -> bool:
                    rel_path = str(file_path.relative_to(self.task.cwd)) if file_path.is_relative_to(self.task.cwd) else str(file_path)
                    name = file_path.name
                    
                    for pattern in self.task.patterns:
                        if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(name, pattern):
                            return True
                    return False
            
            observer = self._get_watchdog_observer()
            if observer is None:
                raise ImportError("watchdog not installed")
            
            handler = ChangeHandler(task, lambda p: self._on_file_changed(task, p))
            observer.schedule(handler, str(task.cwd), recursive=task.recursive)
            
            task.running = True
            
        except ImportError:
            # Fallback to polling
            task._task = asyncio.create_task(self._poll_watch(task))
            task.running = True
    
    async def _poll_watch(self, task: WatchTask) -> None:
        """Poll for file changes (fallback when watchdog not available)."""
        file_mtimes: dict[Path, float] = {}
        
        # Initialize mtimes
        for file_path in self._find_files(task):
            try:
                file_mtimes[file_path] = file_path.stat().st_mtime
            except:
                pass
        
        while task.running:
            await asyncio.sleep(1)
            
            if not task.running:
                break
            
            for file_path in self._find_files(task):
                try:
                    mtime = file_path.stat().st_mtime
                    
                    if file_path in file_mtimes:
                        if mtime > file_mtimes[file_path]:
                            file_mtimes[file_path] = mtime
                            await self._on_file_changed(task, file_path)
                    else:
                        file_mtimes[file_path] = mtime
                        await self._on_file_changed(task, file_path)
                        
                except:
                    pass
    
    def _find_files(self, task: WatchTask) -> list[Path]:
        """Find files matching patterns."""
        files = []
        
        for pattern in task.patterns:
            if '**' in pattern:
                # Recursive glob
                for path in task.cwd.rglob(pattern.replace('**/', '')):
                    if path.is_file():
                        files.append(path)
            else:
                # Simple glob
                for path in task.cwd.glob(pattern):
                    if path.is_file():
                        files.append(path)
        
        return files
    
    async def _on_file_changed(self, task: WatchTask, file_path: Path) -> None:
        """Handle file change."""
        import time
        
        # Debounce check
        current_time = time.time()
        if current_time - task._last_run < (task.debounce_ms / 1000):
            return
        
        task._last_run = current_time
        
        print(f"[watch] File changed: {file_path}")
        
        try:
            if callable(task.command):
                if asyncio.iscoroutinefunction(task.command):
                    await task.command(file_path)
                else:
                    task.command(file_path)
            else:
                # Run as shell command
                import subprocess
                env = {
                    **os.environ,
                    "WATCH_FILE": str(file_path),
                    "WATCH_TASK": task.id,
                }
                result = subprocess.run(
                    task.command,
                    shell=True,
                    cwd=task.cwd,
                    env=env,
                    capture_output=True,
                    text=True,
                )
                
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr, file=__import__('sys').stderr)
                
                if result.returncode == 0:
                    print(f"[watch] Command completed successfully")
                else:
                    print(f"[watch] Command failed with code {result.returncode}")
                    
        except Exception as e:
            print(f"[watch] Error running command: {e}")
    
    def stop_watch(self, task_id: str) -> bool:
        """Stop a watch task.
        
        Args:
            task_id: Task ID to stop
            
        Returns:
            True if stopped successfully
        """
        if task_id not in self._tasks:
            return False
        
        task = self._tasks[task_id]
        task.running = False
        
        if task._task:
            task._task.cancel()
        
        del self._tasks[task_id]
        return True
    
    def list_watches(self) -> list[dict[str, Any]]:
        """List all watch tasks."""
        return [
            {
                "id": task.id,
                "patterns": task.patterns,
                "cwd": str(task.cwd),
                "running": task.running,
                "recursive": task.recursive,
            }
            for task in self._tasks.values()
        ]
    
    def stop_all(self) -> None:
        """Stop all watch tasks."""
        for task in list(self._tasks.values()):
            self.stop_watch(task.id)
        
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None


# Global file watcher instance
_watcher: FileWatcher | None = None


def get_file_watcher() -> FileWatcher:
    """Get the global file watcher."""
    global _watcher
    if _watcher is None:
        _watcher = FileWatcher()
    return _watcher


async def watch(
    patterns: list[str] | str,
    command: str | Callable,
    cwd: str | Path | None = None,
    recursive: bool = True,
    debounce_ms: int = 300,
) -> str:
    """Start watching files for changes.
    
    Args:
        patterns: File patterns to watch
        command: Command to run on change
        cwd: Working directory
        recursive: Whether to watch recursively
        debounce_ms: Debounce time in milliseconds
        
    Returns:
        Watch task ID
    """
    return await get_file_watcher().add_watch(
        patterns=patterns,
        command=command,
        cwd=cwd,
        recursive=recursive,
        debounce_ms=debounce_ms,
    )


def unwatch(task_id: str) -> bool:
    """Stop watching files.
    
    Args:
        task_id: Watch task ID
        
    Returns:
        True if stopped successfully
    """
    return get_file_watcher().stop_watch(task_id)


def list_watches() -> list[dict[str, Any]]:
    """List all active watches."""
    return get_file_watcher().list_watches()
