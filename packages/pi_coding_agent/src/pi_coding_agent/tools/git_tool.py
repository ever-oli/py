"""Git tool for version control operations."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


async def git_tool(
    command: str,
    args: list[str] | None = None,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Execute git commands.

    Args:
        command: Git command (status, log, diff, commit, push, pull, clone, etc.)
        args: Additional arguments for the command
        cwd: Working directory (defaults to current working directory)
        env: Environment variables to set

    Returns:
        Command output and status

    Example:
        >>> # Check status
        ... result = await git_tool("status")

        >>> # View recent commits
        ... result = await git_tool("log", args=["--oneline", "-10"])

        >>> # Stage and commit
        ... await git_tool("add", args=["."])
        ... result = await git_tool("commit", args=["-m", "Initial commit"])
    """
    try:
        import git
    except ImportError:
        # Fallback to subprocess if GitPython not available
        return await _git_subprocess(command, args or [], cwd, env)

    args = args or []
    cwd = cwd or os.getcwd()

    try:
        repo = git.Repo(cwd, search_parent_directories=True)
    except git.InvalidGitRepositoryError:
        if command == "init":
            repo = git.Repo.init(cwd)
        elif command == "clone":
            return await _git_subprocess(command, args, cwd, env)
        else:
            return {
                "success": False,
                "error": "Not a git repository (or any parent up to mount point)",
                "stdout": "",
                "stderr": "",
            }

    try:
        result = await _execute_gitpython_command(repo, command, args)
        return result
    except Exception as e:
        # Fallback to subprocess for unsupported commands
        return await _git_subprocess(command, args, cwd, env)


async def _execute_gitpython_command(repo, command: str, args: list[str]) -> dict[str, Any]:
    """Execute a git command using GitPython."""
    try:
        if command == "status":
            return _git_status(repo)
        elif command == "log":
            return _git_log(repo, args)
        elif command == "diff":
            return _git_diff(repo, args)
        elif command == "add":
            return _git_add(repo, args)
        elif command == "commit":
            return _git_commit(repo, args)
        elif command == "branch":
            return _git_branch(repo, args)
        elif command == "checkout":
            return _git_checkout(repo, args)
        elif command == "remote":
            return _git_remote(repo, args)
        else:
            # Use git command directly for other operations
            import asyncio

            proc = await asyncio.create_subprocess_exec(
                "git",
                command,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo.working_dir,
            )
            stdout, stderr = await proc.communicate()
            return {
                "success": proc.returncode == 0,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": "",
        }


def _git_status(repo) -> dict[str, Any]:
    """Get repository status."""
    status = {
        "success": True,
        "branch": repo.active_branch.name if repo.head.is_valid() else "HEAD",
        "is_dirty": repo.is_dirty(),
        "untracked_files": repo.untracked_files,
        "modified": [],
        "staged": [],
        "deleted": [],
        "renamed": [],
    }

    for item in repo.index.diff(None):
        if item.change_type == "M":
            status["modified"].append(item.a_path)
        elif item.change_type == "D":
            status["deleted"].append(item.a_path)
        elif item.change_type == "R":
            status["renamed"].append((item.a_path, item.b_path))

    for item in repo.index.diff(repo.head.commit) if repo.head.is_valid() else []:
        status["staged"].append(item.a_path)

    # Build text output
    lines = [f"On branch {status['branch']}"]

    if status["staged"]:
        lines.extend(
            ["", "Changes to be committed:", '  (use "git restore --staged <file>..." to unstage)']
        )
        for f in status["staged"]:
            lines.append(f"        modified: {f}")

    if status["modified"]:
        lines.extend(
            ["", "Changes not staged for commit:", '  (use "git add <file>..." to update)']
        )
        for f in status["modified"]:
            lines.append(f"        modified: {f}")

    if status["deleted"]:
        for f in status["deleted"]:
            lines.append(f"        deleted: {f}")

    if status["untracked_files"]:
        lines.extend(
            [
                "",
                "Untracked files:",
                '  (use "git add <file>..." to include in what will be committed)',
            ]
        )
        for f in status["untracked_files"]:
            lines.append(f"        {f}")

    if not any(
        [status["staged"], status["modified"], status["deleted"], status["untracked_files"]]
    ):
        lines.append("nothing to commit, working tree clean")

    status["stdout"] = "\n".join(lines)
    status["stderr"] = ""

    return status


def _git_log(repo, args: list[str]) -> dict[str, Any]:
    """Get commit history."""
    if not repo.head.is_valid():
        return {
            "success": True,
            "stdout": "No commits yet",
            "stderr": "",
            "commits": [],
        }

    max_count = 10
    for i, arg in enumerate(args):
        if arg in ("-n", "--max-count") and i + 1 < len(args):
            max_count = int(args[i + 1])
        elif arg.startswith("-") and arg[1:].isdigit():
            max_count = int(arg[1:])

    commits = []
    lines = []

    for commit in repo.iter_commits("HEAD", max_count=max_count):
        commits.append(
            {
                "hash": commit.hexsha,
                "short_hash": commit.hexsha[:7],
                "message": commit.message.strip(),
                "author": f"{commit.author.name} <{commit.author.email}>",
                "date": commit.committed_datetime.isoformat(),
            }
        )

        # Oneline format
        if "--oneline" in args:
            first_line = commit.message.split("\n")[0][:50]
            lines.append(f"{commit.hexsha[:7]} {first_line}")
        else:
            lines.append(f"commit {commit.hexsha}")
            lines.append(f"Author: {commit.author.name} <{commit.author.email}>")
            lines.append(f"Date:   {commit.committed_datetime.strftime('%a %b %d %H:%M:%S %Y')}")
            lines.append("")
            for line in commit.message.split("\n"):
                lines.append(f"    {line}")
            lines.append("")

    return {
        "success": True,
        "stdout": "\n".join(lines),
        "stderr": "",
        "commits": commits,
    }


def _git_diff(repo, args: list[str]) -> dict[str, Any]:
    """Show differences."""
    if args:
        diff = repo.git.diff(*args)
    else:
        diff = repo.git.diff()

    return {
        "success": True,
        "stdout": diff,
        "stderr": "",
    }


def _git_add(repo, args: list[str]) -> dict[str, Any]:
    """Stage files."""
    if not args:
        return {
            "success": False,
            "error": "Nothing specified, nothing added.",
            "stdout": "",
            "stderr": "",
        }

    try:
        repo.git.add(*args)
        return {
            "success": True,
            "stdout": "",
            "stderr": "",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": "",
        }


def _git_commit(repo, args: list[str]) -> dict[str, Any]:
    """Create a commit."""
    message = None
    for i, arg in enumerate(args):
        if arg in ("-m", "--message") and i + 1 < len(args):
            message = args[i + 1]
            break

    if not message:
        return {
            "success": False,
            "error": "Commit message required (-m)",
            "stdout": "",
            "stderr": "",
        }

    try:
        commit = repo.index.commit(message)
        return {
            "success": True,
            "stdout": f"[{repo.active_branch.name} {commit.hexsha[:7]}] {message}",
            "stderr": "",
            "commit_hash": commit.hexsha,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": "",
        }


def _git_branch(repo, args: list[str]) -> dict[str, Any]:
    """List or manage branches."""
    branches = []
    current = repo.active_branch.name if repo.head.is_valid() else None

    for branch in repo.branches:
        prefix = "* " if branch.name == current else "  "
        branches.append(f"{prefix}{branch.name}")

    return {
        "success": True,
        "stdout": "\n".join(branches),
        "stderr": "",
        "branches": [b.name for b in repo.branches],
        "current": current,
    }


def _git_checkout(repo, args: list[str]) -> dict[str, Any]:
    """Switch branches."""
    if not args:
        return {
            "success": False,
            "error": "Branch name required",
            "stdout": "",
            "stderr": "",
        }

    try:
        repo.git.checkout(*args)
        return {
            "success": True,
            "stdout": f"Switched to {args[-1]}",
            "stderr": "",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": "",
        }


def _git_remote(repo, args: list[str]) -> dict[str, Any]:
    """Manage remotes."""
    remotes = []
    for remote in repo.remotes:
        remotes.append(f"{remote.name}\t{remote.url}")

    return {
        "success": True,
        "stdout": "\n".join(remotes),
        "stderr": "",
        "remotes": [{"name": r.name, "url": r.url} for r in repo.remotes],
    }


async def _git_subprocess(
    command: str, args: list[str], cwd: str | None, env: dict | None
) -> dict[str, Any]:
    """Execute git using subprocess."""
    import asyncio

    cmd = ["git", command] + args

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env={**os.environ, **(env or {})},
        )
        stdout, stderr = await proc.communicate()

        return {
            "success": proc.returncode == 0,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": "Git not found. Please install git.",
            "stdout": "",
            "stderr": "",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": "",
        }


def create_git_tool(cwd: str | None = None) -> dict[str, Any]:
    """Create a git tool instance."""
    return {
        "name": "git",
        "description": """Git version control operations.
        
Execute git commands including status, log, diff, add, commit, push, pull, clone, etc.

Common commands:
- status: Show working tree status
- log: Show commit history (use --oneline -10 for brief)
- diff: Show changes between commits, commit and working tree, etc.
- add: Add files to staging area
- commit: Record changes (-m "message" required)
- branch: List, create, or delete branches
- checkout: Switch branches or restore files
- remote: Manage tracked repositories
- push: Push commits to remote
- pull: Fetch and merge from remote
- clone: Clone a repository
""",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": [
                        "status",
                        "log",
                        "diff",
                        "add",
                        "commit",
                        "branch",
                        "checkout",
                        "remote",
                        "push",
                        "pull",
                        "clone",
                        "init",
                        "fetch",
                        "merge",
                    ],
                    "description": "Git command to execute",
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional arguments for the command",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (defaults to current)",
                },
                "env": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Environment variables to set",
                },
            },
            "required": ["command"],
        },
        "execute": git_tool,
    }


git_tool_definition = create_git_tool()
