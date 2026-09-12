"""Typed configuration for PURE Phase 5 recommender experiments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True, slots=True)
class Phase5InputConfig:
    items_path: Path
    interactions_path: Path
    sessions_path: Path
    profile_states_path: Path


@dataclass(frozen=True, slots=True)
class Phase5ExperimentConfig:
    max_sessions: int = 6
    fail_fast: bool = True


@dataclass(frozen=True, slots=True)
class Phase5GenerationConfig:
    temperature: float = 0.0
    max_tokens: int = 512
    seed: int = 42


@dataclass(frozen=True, slots=True)
class Phase5OutputConfig:
    directory: Path


@dataclass(frozen=True, slots=True)
class Phase5Config:
    input: Phase5InputConfig
    experiment: Phase5ExperimentConfig
    generation: Phase5GenerationConfig
    output: Phase5OutputConfig


def _resolve(repo_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (repo_root / path).resolve()


def load_phase5_config(config_path: str | Path) -> Phase5Config:
    path = Path(config_path).resolve()
    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    repo_root = path.parent.parent
    input_raw = raw.get("input", {})
    experiment_raw = raw.get("experiment", {})
    generation_raw = raw.get("generation", {})
    output_raw = raw.get("output", {})

    config = Phase5Config(
        input=Phase5InputConfig(
            items_path=_resolve(repo_root, str(input_raw["items_path"])),
            interactions_path=_resolve(repo_root, str(input_raw["interactions_path"])),
            sessions_path=_resolve(repo_root, str(input_raw["sessions_path"])),
            profile_states_path=_resolve(repo_root, str(input_raw["profile_states_path"])),
        ),
        experiment=Phase5ExperimentConfig(
            max_sessions=int(experiment_raw.get("max_sessions", 6)),
            fail_fast=bool(experiment_raw.get("fail_fast", True)),
        ),
        generation=Phase5GenerationConfig(
            temperature=float(generation_raw.get("temperature", 0.0)),
            max_tokens=int(generation_raw.get("max_tokens", 512)),
            seed=int(generation_raw.get("seed", 42)),
        ),
        output=Phase5OutputConfig(
            directory=_resolve(repo_root, str(output_raw["directory"])),
        ),
    )

    if config.experiment.max_sessions < 0:
        raise ValueError("max_sessions must be >= 0")
    if config.generation.temperature < 0:
        raise ValueError("temperature must be >= 0")
    if config.generation.max_tokens < 1:
        raise ValueError("max_tokens must be >= 1")
    return config
