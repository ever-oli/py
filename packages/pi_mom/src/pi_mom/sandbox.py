"""Sandbox execution for Mom."""

import subprocess
from dataclasses import dataclass
from typing import Union


@dataclass
class HostConfig:
    type: str = "host"


@dataclass
class DockerConfig:
    container: str
    type: str = "docker"


SandboxConfig = Union[HostConfig, DockerConfig]


@dataclass
class ExecResult:
    stdout: str
    stderr: str
    code: int


class Executor:
    """Base executor interface."""

    async def exec(self, command: str, timeout: int | None = None) -> ExecResult:
        raise NotImplementedError

    def get_workspace_path(self, host_path: str) -> str:
        raise NotImplementedError


class HostExecutor(Executor):
    """Execute commands on the host."""

    async def exec(self, command: str, timeout: int | None = None) -> ExecResult:
        """Execute a command on the host."""
        import platform

        shell = ["cmd", "/c"] if platform.system() == "Windows" else ["sh", "-c"]

        try:
            process = await asyncio.create_subprocess_exec(
                shell[0],
                shell[1],
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            except TimeoutError:
                process.kill()
                return ExecResult(
                    stdout="", stderr=f"Command timed out after {timeout} seconds", code=-1
                )

            return ExecResult(
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                code=process.returncode or 0,
            )
        except Exception as e:
            return ExecResult(stdout="", stderr=str(e), code=1)

    def get_workspace_path(self, host_path: str) -> str:
        return host_path


class DockerExecutor(Executor):
    """Execute commands in a Docker container."""

    def __init__(self, container: str):
        self.container = container

    async def exec(self, command: str, timeout: int | None = None) -> ExecResult:
        """Execute a command in the Docker container."""
        docker_cmd = f"docker exec {self.container} sh -c {self._shell_escape(command)}"
        host_executor = HostExecutor()
        return await host_executor.exec(docker_cmd, timeout)

    def get_workspace_path(self, _host_path: str) -> str:
        return "/workspace"

    def _shell_escape(self, s: str) -> str:
        return "'" + s.replace("'", "'\\''") + "'"


def parse_sandbox_arg(value: str) -> SandboxConfig:
    """Parse sandbox argument from command line."""
    if value == "host":
        return HostConfig()
    if value.startswith("docker:"):
        container = value[7:]
        if not container:
            raise ValueError("docker sandbox requires container name (e.g., docker:mom-sandbox)")
        return DockerConfig(container=container)
    raise ValueError(f"Invalid sandbox type '{value}'. Use 'host' or 'docker:<container-name>'")


async def validate_sandbox(config: SandboxConfig) -> None:
    """Validate that the sandbox is available."""
    if isinstance(config, HostConfig):
        return

    # Check if Docker is available
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError("Docker is not installed or not in PATH")
    except FileNotFoundError:
        raise RuntimeError("Docker is not installed or not in PATH")

    # Check if container exists and is running
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", config.container],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Container '{config.container}' does not exist")
    if result.stdout.strip() != "true":
        raise RuntimeError(f"Container '{config.container}' is not running")

    print(f"  Docker container '{config.container}' is running.")


def create_executor(config: SandboxConfig) -> Executor:
    """Create an executor for the given sandbox config."""
    if isinstance(config, HostConfig):
        return HostExecutor()
    return DockerExecutor(config.container)


# Import asyncio at the end to avoid circular imports
import asyncio
