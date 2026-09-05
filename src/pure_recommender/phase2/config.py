"""Typed configuration for the Phase 2 Sequential baseline.

The Phase 2 config is deliberately separate from the local-server config:
- ``config/local_llm.toml`` identifies the active localhost endpoint/model.
- ``config/phase2.toml`` defines the recommender experiment itself.

This separation lets us change the local runtime/model later without changing
how the Sequential baseline constructs or evaluates recommendation sessions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True, slots=True)
class Phase2InputConfig:
    items_path: Path
    interactions_path: Path
    sessions_path: Path


@dataclass(frozen=True, slots=True)
class Phase2ExperimentConfig:
    max_sessions: int = 3
    resume: bool = True
    fail_fast: bool = True


@dataclass(frozen=True, slots=True)
class Phase2GenerationConfig:
    temperature: float = 0.0
    max_tokens: int = 512
    seed: int = 42


@dataclass(frozen=True, slots=True)
class Phase2OutputConfig:
    directory: Path = Path("outputs/phase2_sequential")


@dataclass(frozen=True, slots=True)
class Phase2Config:
    input: Phase2InputConfig
    experiment: Phase2ExperimentConfig
    generation: Phase2GenerationConfig
    output: Phase2OutputConfig


def _resolve(repo_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (repo_root / path).resolve()


def load_phase2_config(config_path: str | Path) -> Phase2Config:
    """Load Phase 2 TOML settings and resolve project-relative paths."""

    path = Path(config_path).resolve()
    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    repo_root = path.parent.parent
    input_raw = raw.get("input", {})
    experiment_raw = raw.get("experiment", {})
    generation_raw = raw.get("generation", {})
    output_raw = raw.get("output", {})

    input_config = Phase2InputConfig(
        items_path=_resolve(repo_root, str(input_raw["items_path"])),
        interactions_path=_resolve(repo_root, str(input_raw["interactions_path"])),
        sessions_path=_resolve(repo_root, str(input_raw["sessions_path"])),
    )
    experiment_config = Phase2ExperimentConfig(
        max_sessions=int(experiment_raw.get("max_sessions", 3)),
        resume=bool(experiment_raw.get("resume", True)),
        fail_fast=bool(experiment_raw.get("fail_fast", True)),
    )
    generation_config = Phase2GenerationConfig(
        temperature=float(generation_raw.get("temperature", 0.0)),
        max_tokens=int(generation_raw.get("max_tokens", 512)),
        seed=int(generation_raw.get("seed", 42)),
    )
    output_config = Phase2OutputConfig(
        directory=_resolve(
            repo_root,
            str(output_raw.get("directory", "outputs/phase2_sequential")),
        )
    )

    if experiment_config.max_sessions < 0:
        raise ValueError("max_sessions must be >= 0; use 0 to run every frozen session")
    if generation_config.max_tokens < 1:
        raise ValueError("generation.max_tokens must be >= 1")
    if generation_config.temperature < 0:
        raise ValueError("generation.temperature must be >= 0")

    return Phase2Config(
        input=input_config,
        experiment=experiment_config,
        generation=generation_config,
        output=output_config,
    )
