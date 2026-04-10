"""SSH operations for pi_pods."""

import asyncio
from dataclasses import dataclass


@dataclass
class SSHResult:
    """Result of an SSH command."""

    stdout: str
    stderr: str
    exit_code: int


async def ssh_exec(ssh_cmd: str, command: str, keep_alive: bool = False) -> SSHResult:
    """Execute an SSH command and return the result."""
    ssh_parts = ssh_cmd.split()
    ssh_binary = ssh_parts[0]
    ssh_args = ssh_parts[1:]

    if keep_alive:
        ssh_args = ["-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=120"] + ssh_args

    ssh_args.append(command)

    process = await asyncio.create_subprocess_exec(
        ssh_binary, *ssh_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    return SSHResult(
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
        exit_code=process.returncode or 0,
    )


async def ssh_exec_stream(
    ssh_cmd: str,
    command: str,
    silent: bool = False,
    force_tty: bool = False,
    keep_alive: bool = False,
) -> int:
    """Execute an SSH command with streaming output."""
    ssh_parts = ssh_cmd.split()
    ssh_binary = ssh_parts[0]
    ssh_args = ssh_parts[1:]

    if force_tty and "-t" not in ssh_args:
        ssh_args = ["-t"] + ssh_args

    if keep_alive:
        ssh_args = ["-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=120"] + ssh_args

    ssh_args.append(command)

    if silent:
        process = await asyncio.create_subprocess_exec(
            ssh_binary,
            *ssh_args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    else:
        process = await asyncio.create_subprocess_exec(
            ssh_binary, *ssh_args, stdin=asyncio.subprocess.PIPE
        )

    await process.wait()
    return process.returncode or 0


async def scp_file(ssh_cmd: str, local_path: str, remote_path: str) -> bool:
    """Copy a file to remote via SCP."""
    ssh_parts = ssh_cmd.split()

    # Extract host and port
    host = ""
    port = "22"
    i = 1  # Skip 'ssh'

    while i < len(ssh_parts):
        if ssh_parts[i] == "-p" and i + 1 < len(ssh_parts):
            port = ssh_parts[i + 1]
            i += 2
        elif not ssh_parts[i].startswith("-"):
            host = ssh_parts[i]
            break
        else:
            i += 1

    if not host:
        print("Could not parse host from SSH command")
        return False

    scp_args = ["-P", port, local_path, f"{host}:{remote_path}"]

    process = await asyncio.create_subprocess_exec("scp", *scp_args, stdin=asyncio.subprocess.PIPE)

    await process.wait()
    return process.returncode == 0
