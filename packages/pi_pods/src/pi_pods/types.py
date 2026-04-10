"""Types for pi_pods."""

from dataclasses import dataclass, field


@dataclass
class GPU:
    """Represents a GPU."""

    id: int
    name: str
    memory: str


@dataclass
class Model:
    """Represents a running vLLM model."""

    model: str
    port: int
    gpu: list[int]
    pid: int


@dataclass
class Pod:
    """Represents a GPU pod."""

    ssh: str
    gpus: list[GPU]
    models: dict[str, Model] = field(default_factory=dict)
    models_path: str | None = None
    vllm_version: str | None = "release"


@dataclass
class Config:
    """Represents the pods configuration."""

    pods: dict[str, Pod] = field(default_factory=dict)
    active: str | None = None
