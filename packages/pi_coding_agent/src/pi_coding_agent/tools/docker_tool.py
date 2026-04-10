"""Docker tool for container management."""

from __future__ import annotations

import json
import os
from typing import Any


async def docker_tool(
    command: str,
    args: list[str] | None = None,
    options: dict | None = None,
) -> dict[str, Any]:
    """Execute Docker commands for container management.
    
    Args:
        command: Docker command (ps, images, run, exec, stop, rm, build, etc.)
        args: Positional arguments (image name, container name, etc.)
        options: Command options as dict (--name, -p, -v, etc.)
        
    Returns:
        Command output and status
        
    Example:
        >>> # List running containers
        ... result = await docker_tool("ps")
        
        >>> # Run a container
        ... result = await docker_tool(
        ...     "run",
        ...     args=["nginx:latest"],
        ...     options={"name": "my-nginx", "p": ["8080:80"], "d": True}
        ... )
        
        >>> # Execute command in container
        ... result = await docker_tool("exec", args=["my-nginx", "ls", "-la"])
    """
    try:
        import docker
        client = docker.from_env()
    except ImportError:
        # Fallback to subprocess
        return await _docker_subprocess(command, args or [], options or {})
    except Exception:
        # Docker not available
        return await _docker_subprocess(command, args or [], options or {})
    
    args = args or []
    options = options or {}
    
    try:
        if command == "ps":
            return _docker_ps(client, options)
        elif command == "images":
            return _docker_images(client, options)
        elif command == "run":
            return await _docker_run(client, args, options)
        elif command == "stop":
            return _docker_stop(client, args)
        elif command == "rm":
            return _docker_rm(client, args, options)
        elif command == "exec":
            return await _docker_exec(client, args)
        elif command == "logs":
            return _docker_logs(client, args, options)
        elif command == "inspect":
            return _docker_inspect(client, args)
        elif command == "pull":
            return await _docker_pull(client, args)
        elif command == "build":
            return await _docker_build(client, args, options)
        elif command == "network":
            return _docker_network(client, args, options)
        elif command == "volume":
            return _docker_volume(client, args, options)
        else:
            return await _docker_subprocess(command, args, options)
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": str(e),
        }


def _docker_ps(client, options: dict) -> dict[str, Any]:
    """List containers."""
    all_containers = options.get("all", False) or options.get("a", False)
    containers = client.containers.list(all=all_containers)
    
    lines = ["CONTAINER ID\tIMAGE\tCOMMAND\tCREATED\tSTATUS\tPORTS\tNAMES"]
    result_containers = []
    
    for container in containers:
        short_id = container.id[:12]
        image = container.image.tags[0] if container.image.tags else container.image.id[:12]
        command = container.attrs['Config']['Cmd']
        command_str = ' '.join(command) if command else ""
        if len(command_str) > 30:
            command_str = command_str[:27] + "..."
        
        created = container.attrs['Created'][:19].replace('T', ' ')
        status = container.status
        
        ports = []
        for port, bindings in container.ports.items():
            if bindings:
                for binding in bindings:
                    host_port = binding.get('HostPort', '')
                    host_ip = binding.get('HostIp', '')
                    if host_port:
                        ports.append(f"{host_ip}:{host_port}->{port}" if host_ip else f"{host_port}->{port}")
        ports_str = ", ".join(ports) if ports else ""
        
        names = ",".join(container.names)
        
        lines.append(f"{short_id}\t{image}\t{command_str}\t{created}\t{status}\t{ports_str}\t{names}")
        
        result_containers.append({
            "id": container.id,
            "short_id": short_id,
            "image": image,
            "status": status,
            "names": container.names,
            "ports": ports,
        })
    
    return {
        "success": True,
        "stdout": "\n".join(lines),
        "stderr": "",
        "containers": result_containers,
    }


def _docker_images(client, options: dict) -> dict[str, Any]:
    """List images."""
    images = client.images.list()
    
    lines = ["REPOSITORY\tTAG\tIMAGE ID\tCREATED\tSIZE"]
    result_images = []
    
    for image in images:
        if image.tags:
            for tag in image.tags:
                repo, image_tag = tag.rsplit(":", 1) if ":" in tag else (tag, "latest")
                short_id = image.id.split(":")[-1][:12]
                created = image.attrs['Created'][:19].replace('T', ' ')
                size_mb = image.attrs['Size'] / (1024 * 1024)
                
                lines.append(f"{repo}\t{image_tag}\t{short_id}\t{created}\t{size_mb:.1f}MB")
                result_images.append({
                    "repository": repo,
                    "tag": image_tag,
                    "id": image.id,
                    "short_id": short_id,
                    "size_mb": size_mb,
                })
        else:
            short_id = image.id.split(":")[-1][:12]
            created = image.attrs['Created'][:19].replace('T', ' ')
            size_mb = image.attrs['Size'] / (1024 * 1024)
            lines.append(f"<none>\t<none>\t{short_id}\t{created}\t{size_mb:.1f}MB")
    
    return {
        "success": True,
        "stdout": "\n".join(lines),
        "stderr": "",
        "images": result_images,
    }


async def _docker_run(client, args: list[str], options: dict) -> dict[str, Any]:
    """Run a container."""
    if not args:
        return {
            "success": False,
            "error": "Image name required",
            "stdout": "",
            "stderr": "",
        }
    
    image = args[0]
    command = args[1:] if len(args) > 1 else None
    
    run_options = {
        "image": image,
        "command": command,
        "detach": options.get("detach", options.get("d", True)),
        "remove": options.get("rm", False),
        "name": options.get("name"),
        "ports": _parse_ports(options.get("p", options.get("publish", []))),
        "volumes": _parse_volumes(options.get("v", options.get("volume", []))),
        "environment": options.get("e", options.get("env", {})),
        "network": options.get("network"),
    }
    
    # Remove None values
    run_options = {k: v for k, v in run_options.items() if v is not None}
    
    try:
        container = client.containers.run(**run_options)
        
        if run_options.get("detach"):
            return {
                "success": True,
                "stdout": f"Container started: {container.id[:12]}",
                "stderr": "",
                "container_id": container.id,
                "short_id": container.id[:12],
            }
        else:
            return {
                "success": True,
                "stdout": container.decode('utf-8') if isinstance(container, bytes) else str(container),
                "stderr": "",
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": str(e),
        }


def _docker_stop(client, args: list[str]) -> dict[str, Any]:
    """Stop containers."""
    if not args:
        return {
            "success": False,
            "error": "Container name/ID required",
            "stdout": "",
            "stderr": "",
        }
    
    stopped = []
    errors = []
    
    for container_id in args:
        try:
            container = client.containers.get(container_id)
            container.stop()
            stopped.append(container_id)
        except Exception as e:
            errors.append(f"{container_id}: {e}")
    
    return {
        "success": len(errors) == 0,
        "stdout": f"Stopped: {', '.join(stopped)}" if stopped else "",
        "stderr": "\n".join(errors) if errors else "",
    }


def _docker_rm(client, args: list[str], options: dict) -> dict[str, Any]:
    """Remove containers."""
    if not args:
        return {
            "success": False,
            "error": "Container name/ID required",
            "stdout": "",
            "stderr": "",
        }
    
    force = options.get("force", options.get("f", False))
    removed = []
    errors = []
    
    for container_id in args:
        try:
            container = client.containers.get(container_id)
            container.remove(force=force)
            removed.append(container_id)
        except Exception as e:
            errors.append(f"{container_id}: {e}")
    
    return {
        "success": len(errors) == 0,
        "stdout": f"Removed: {', '.join(removed)}" if removed else "",
        "stderr": "\n".join(errors) if errors else "",
    }


async def _docker_exec(client, args: list[str]) -> dict[str, Any]:
    """Execute command in container."""
    if len(args) < 2:
        return {
            "success": False,
            "error": "Container name/ID and command required",
            "stdout": "",
            "stderr": "",
        }
    
    container_id = args[0]
    command = args[1:]
    
    try:
        container = client.containers.get(container_id)
        result = container.exec_run(command)
        
        return {
            "success": result.exit_code == 0,
            "stdout": result.output.decode('utf-8', errors='replace') if result.output else "",
            "stderr": "",
            "exit_code": result.exit_code,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": str(e),
        }


def _docker_logs(client, args: list[str], options: dict) -> dict[str, Any]:
    """Get container logs."""
    if not args:
        return {
            "success": False,
            "error": "Container name/ID required",
            "stdout": "",
            "stderr": "",
        }
    
    container_id = args[0]
    tail = options.get("tail", 100)
    follow = options.get("follow", options.get("f", False))
    
    try:
        container = client.containers.get(container_id)
        logs = container.logs(tail=tail, follow=follow, stream=False)
        
        return {
            "success": True,
            "stdout": logs.decode('utf-8', errors='replace') if logs else "",
            "stderr": "",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": str(e),
        }


def _docker_inspect(client, args: list[str]) -> dict[str, Any]:
    """Inspect container or image."""
    if not args:
        return {
            "success": False,
            "error": "Container/image name/ID required",
            "stdout": "",
            "stderr": "",
        }
    
    target_id = args[0]
    
    try:
        # Try container first
        try:
            target = client.containers.get(target_id)
        except:
            target = client.images.get(target_id)
        
        return {
            "success": True,
            "stdout": json.dumps(target.attrs, indent=2, default=str),
            "stderr": "",
            "attributes": target.attrs,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": str(e),
        }


async def _docker_pull(client, args: list[str]) -> dict[str, Any]:
    """Pull an image."""
    if not args:
        return {
            "success": False,
            "error": "Image name required",
            "stdout": "",
            "stderr": "",
        }
    
    image = args[0]
    
    try:
        client.images.pull(image)
        return {
            "success": True,
            "stdout": f"Pulled: {image}",
            "stderr": "",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": str(e),
        }


async def _docker_build(client, args: list[str], options: dict) -> dict[str, Any]:
    """Build an image."""
    if not args:
        return {
            "success": False,
            "error": "Build path required",
            "stdout": "",
            "stderr": "",
        }
    
    path = args[0]
    tag = options.get("t", options.get("tag"))
    dockerfile = options.get("f", options.get("file", "Dockerfile"))
    
    try:
        build_args = {"path": path, "dockerfile": dockerfile}
        if tag:
            build_args["tag"] = tag
        
        image = client.images.build(**build_args)
        
        return {
            "success": True,
            "stdout": f"Built: {tag or image[0].id}",
            "stderr": "",
            "image_id": image[0].id,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": str(e),
        }


def _docker_network(client, args: list[str], options: dict) -> dict[str, Any]:
    """Manage networks."""
    if not args:
        # List networks
        networks = client.networks.list()
        lines = ["NETWORK ID\tNAME\tDRIVER\tSCOPE"]
        for network in networks:
            short_id = network.id[:12]
            lines.append(f"{short_id}\t{network.name}\t{network.driver}\t{network.scope}")
        
        return {
            "success": True,
            "stdout": "\n".join(lines),
            "stderr": "",
            "networks": [{"id": n.id, "name": n.name, "driver": n.driver} for n in networks],
        }
    
    subcommand = args[0]
    
    if subcommand == "create" and len(args) > 1:
        try:
            network = client.networks.create(args[1], driver=options.get("d", "bridge"))
            return {
                "success": True,
                "stdout": network.id,
                "stderr": "",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": str(e),
            }
    
    return {
        "success": False,
        "error": f"Unknown network subcommand: {subcommand}",
        "stdout": "",
        "stderr": "",
    }


def _docker_volume(client, args: list[str], options: dict) -> dict[str, Any]:
    """Manage volumes."""
    if not args:
        # List volumes
        volumes = client.volumes.list()
        lines = ["DRIVER\tVOLUME NAME"]
        for volume in volumes:
            lines.append(f"{volume.driver}\t{volume.name}")
        
        return {
            "success": True,
            "stdout": "\n".join(lines),
            "stderr": "",
            "volumes": [{"name": v.name, "driver": v.driver} for v in volumes],
        }
    
    subcommand = args[0]
    
    if subcommand == "create" and len(args) > 1:
        try:
            volume = client.volumes.create(args[1], driver=options.get("d", "local"))
            return {
                "success": True,
                "stdout": volume.name,
                "stderr": "",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": str(e),
            }
    
    return {
        "success": False,
        "error": f"Unknown volume subcommand: {subcommand}",
        "stdout": "",
        "stderr": "",
    }


def _parse_ports(port_list: list) -> dict:
    """Parse port mappings."""
    ports = {}
    if isinstance(port_list, str):
        port_list = [port_list]
    
    for port in port_list:
        if isinstance(port, str) and ":" in port:
            parts = port.split(":")
            if len(parts) == 2:
                host_port, container_port = parts
                ports[f"{container_port}/tcp"] = ("0.0.0.0", int(host_port))
            elif len(parts) == 3:
                host_ip, host_port, container_port = parts
                ports[f"{container_port}/tcp"] = (host_ip, int(host_port))
    
    return ports


def _parse_volumes(volume_list: list) -> dict:
    """Parse volume mappings."""
    volumes = {}
    if isinstance(volume_list, str):
        volume_list = [volume_list]
    
    for vol in volume_list:
        if isinstance(vol, str) and ":" in vol:
            parts = vol.split(":")
            host_path = parts[0]
            container_path = parts[1]
            mode = parts[2] if len(parts) > 2 else "rw"
            volumes[host_path] = {"bind": container_path, "mode": mode}
    
    return volumes


async def _docker_subprocess(command: str, args: list[str], options: dict) -> dict[str, Any]:
    """Execute docker using subprocess."""
    import asyncio
    
    # Build command
    cmd = ["docker", command]
    
    # Add options
    for key, value in options.items():
        if value is True:
            cmd.append(f"--{key}")
        elif isinstance(value, list):
            for v in value:
                cmd.extend([f"--{key}", str(v)])
        elif value is not False and value is not None:
            cmd.extend([f"--{key}", str(value)])
    
    # Add args
    cmd.extend(args)
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        
        return {
            "success": proc.returncode == 0,
            "stdout": stdout.decode('utf-8', errors='replace'),
            "stderr": stderr.decode('utf-8', errors='replace'),
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": "Docker not found. Please install Docker.",
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


def create_docker_tool(cwd: str | None = None) -> dict[str, Any]:
    """Create a Docker tool instance."""
    return {
        "name": "docker",
        "description": """Docker container management.
        
Execute Docker commands including ps, images, run, exec, stop, rm, build, etc.

Common commands:
- ps: List containers (use {"a": true} for all)
- images: List images
- run: Run a container (requires image name in args)
- stop: Stop containers
- rm: Remove containers (use {"force": true} to force)
- exec: Execute command in container
- logs: Get container logs (use {"tail": 100})
- inspect: Get detailed info
- pull: Pull an image
- build: Build from Dockerfile
- network: Manage networks
- volume: Manage volumes
""",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": ["ps", "images", "run", "stop", "rm", "exec", "logs",
                            "inspect", "pull", "build", "network", "volume"],
                    "description": "Docker command to execute",
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Positional arguments (image name, container name, command)",
                },
                "options": {
                    "type": "object",
                    "description": "Command options (--name, -p, -v, etc.)",
                },
            },
            "required": ["command"],
        },
        "execute": docker_tool,
    }


docker_tool_definition = create_docker_tool()
