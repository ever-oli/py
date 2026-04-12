"""Skills system - agent-created tools.

Python port of Hermes skills functionality.
Allows agents to create, manage, and execute custom Python tools.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .constants import get_io_home

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class Skill:
    """A custom agent-created tool."""

    id: str
    name: str
    description: str
    code: str  # Python code
    parameters: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    usage_count: int = 0
    last_used: str | None = None
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(UTC).isoformat()

    def record_usage(self) -> None:
        """Record that this skill was used."""
        self.usage_count += 1
        self.last_used = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Skill:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            code=data.get("code", ""),
            parameters=data.get("parameters", {}),
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            updated_at=data.get("updated_at", datetime.now(UTC).isoformat()),
            usage_count=data.get("usage_count", 0),
            last_used=data.get("last_used"),
            version=data.get("version", "1.0.0"),
            tags=data.get("tags", []),
        )


class SkillRegistry:
    """Registry for agent-created skills."""

    def __init__(self, skills_dir: Path | None = None):
        self.skills_dir = skills_dir or (get_io_home() / "skills")
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._skills: dict[str, Skill] = {}
        self._loaded_modules: dict[str, Any] = {}
        self._load_all()

    def _get_skill_path(self, skill_id: str) -> Path:
        """Get the path for a skill file."""
        return self.skills_dir / f"{skill_id}.json"

    def _get_skill_code_path(self, skill_id: str) -> Path:
        """Get the path for skill Python code."""
        return self.skills_dir / f"{skill_id}.py"

    def _load_all(self) -> None:
        """Load all skills from disk."""
        for skill_file in self.skills_dir.glob("*.json"):
            try:
                data = json.loads(skill_file.read_text())
                skill = Skill.from_dict(data)
                self._skills[skill.id] = skill
            except (json.JSONDecodeError, KeyError):
                continue

    def _save_skill(self, skill: Skill) -> None:
        """Save a skill to disk."""
        skill_path = self._get_skill_path(skill.id)
        skill_path.write_text(json.dumps(skill.to_dict(), indent=2))

        # Also save the code as a separate .py file for editing
        code_path = self._get_skill_code_path(skill.id)
        code_path.write_text(skill.code)

    def create_skill(
        self,
        name: str,
        description: str,
        code: str,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Skill:
        """Create a new skill.

        Args:
            name: Skill name (must be unique)
            description: What the skill does
            code: Python code implementing the skill
            parameters: JSON schema for parameters
            tags: Tags for categorization

        Returns:
            Created skill
        """
        # Generate ID from name
        skill_id = name.lower().replace(" ", "_").replace("-", "_")

        # Check for existing
        if skill_id in self._skills:
            raise ValueError(f"Skill '{name}' already exists")

        skill = Skill(
            id=skill_id,
            name=name,
            description=description,
            code=code,
            parameters=parameters or {},
            tags=tags or [],
        )

        self._skills[skill_id] = skill
        self._save_skill(skill)
        return skill

    def update_skill(
        self,
        skill_id: str,
        description: str | None = None,
        code: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> Skill:
        """Update an existing skill."""
        skill = self._skills.get(skill_id)
        if not skill:
            raise ValueError(f"Skill '{skill_id}' not found")

        if description is not None:
            skill.description = description
        if code is not None:
            skill.code = code
        if parameters is not None:
            skill.parameters = parameters

        skill.touch()
        self._save_skill(skill)
        return skill

    def delete_skill(self, skill_id: str) -> bool:
        """Delete a skill."""
        if skill_id not in self._skills:
            return False

        del self._skills[skill_id]

        # Remove files
        skill_path = self._get_skill_path(skill_id)
        code_path = self._get_skill_code_path(skill_id)
        skill_path.unlink(missing_ok=True)
        code_path.unlink(missing_ok=True)

        # Remove from loaded modules
        self._loaded_modules.pop(skill_id, None)

        return True

    def get_skill(self, skill_id: str) -> Skill | None:
        """Get a skill by ID."""
        return self._skills.get(skill_id)

    def list_skills(self, tag: str | None = None) -> list[Skill]:
        """List all skills, optionally filtered by tag."""
        skills = list(self._skills.values())

        if tag:
            skills = [s for s in skills if tag in s.tags]

        # Sort by usage (most used first), then by name
        skills.sort(key=lambda s: (-s.usage_count, s.name))
        return skills

    def _load_skill_module(self, skill: Skill) -> Any:
        """Dynamically load a skill's Python module."""
        if skill.id in self._loaded_modules:
            return self._loaded_modules[skill.id]

        # Write code to temp file
        code_path = self._get_skill_code_path(skill.id)
        code_path.write_text(skill.code)

        # Load the module
        spec = importlib.util.spec_from_file_location(
            f"io_skill_{skill.id}",
            code_path,
        )
        if not spec or not spec.loader:
            raise ImportError(f"Could not load skill module: {skill.id}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        self._loaded_modules[skill.id] = module
        return module

    def execute_skill(
        self,
        skill_id: str,
        **kwargs,
    ) -> Any:
        """Execute a skill with given parameters.

        Args:
            skill_id: ID of the skill to execute
            **kwargs: Parameters to pass to the skill

        Returns:
            Skill return value
        """
        skill = self._skills.get(skill_id)
        if not skill:
            raise ValueError(f"Skill '{skill_id}' not found")

        module = self._load_skill_module(skill)

        # Look for main function
        if not hasattr(module, "main"):
            raise ValueError(f"Skill '{skill_id}' has no main() function")

        # Execute and record usage
        result = module.main(**kwargs)
        skill.record_usage()
        self._save_skill(skill)

        return result

    def get_skill_as_tool(self, skill: Skill) -> dict[str, Any]:
        """Convert a skill to a tool definition for the model."""
        return {
            "type": "function",
            "function": {
                "name": skill.id,
                "description": skill.description,
                "parameters": skill.parameters or {
                    "type": "object",
                    "properties": {},
                },
            },
        }


def get_skill_registry() -> SkillRegistry:
    """Get the global skill registry."""
    return SkillRegistry()
