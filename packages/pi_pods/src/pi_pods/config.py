"""Config management for pi_pods."""

import json
import os
from pathlib import Path

from .types import Config, Pod


def get_config_dir() -> Path:
    """Get the config directory."""
    config_dir = Path(os.environ.get("PI_CONFIG_DIR", Path.home() / ".pi"))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get the config file path."""
    return get_config_dir() / "pods.json"


def load_config() -> Config:
    """Load the config from file."""
    config_path = get_config_path()
    if not config_path.exists():
        return Config()

    try:
        with open(config_path) as f:
            data = json.load(f)

        pods = {}
        for name, pod_data in data.get("pods", {}).items():
            from .types import GPU

            gpus = [GPU(**g) for g in pod_data.get("gpus", [])]
            models = {}
            for model_name, model_data in pod_data.get("models", {}).items():
                models[model_name] = Model(**model_data)
            pods[name] = Pod(
                ssh=pod_data["ssh"],
                gpus=gpus,
                models=models,
                models_path=pod_data.get("models_path"),
                vllm_version=pod_data.get("vllm_version", "release"),
            )

        return Config(pods=pods, active=data.get("active"))
    except Exception as e:
        print(f"Error reading config: {e}")
        return Config()


def save_config(config: Config) -> None:
    """Save the config to file."""
    config_path = get_config_path()

    data = {"pods": {}, "active": config.active}

    for name, pod in config.pods.items():
        data["pods"][name] = {
            "ssh": pod.ssh,
            "gpus": [{"id": g.id, "name": g.name, "memory": g.memory} for g in pod.gpus],
            "models": {
                name: {"model": m.model, "port": m.port, "gpu": m.gpu, "pid": m.pid}
                for name, m in pod.models.items()
            },
            "models_path": pod.models_path,
            "vllm_version": pod.vllm_version,
        }

    with open(config_path, "w") as f:
        json.dump(data, f, indent=2)


def get_active_pod() -> tuple[str, Pod] | None:
    """Get the active pod."""
    config = load_config()
    if not config.active or config.active not in config.pods:
        return None
    return (config.active, config.pods[config.active])


def add_pod(name: str, pod: Pod) -> None:
    """Add a pod to the config."""
    config = load_config()
    config.pods[name] = pod
    if not config.active:
        config.active = name
    save_config(config)


def remove_pod(name: str) -> None:
    """Remove a pod from the config."""
    config = load_config()
    if name in config.pods:
        del config.pods[name]
    if config.active == name:
        config.active = None
    save_config(config)


def set_active_pod(name: str) -> None:
    """Set the active pod."""
    config = load_config()
    if name not in config.pods:
        raise ValueError(f"Pod '{name}' not found")
    config.active = name
    save_config(config)


# Import at end
from .types import Model
