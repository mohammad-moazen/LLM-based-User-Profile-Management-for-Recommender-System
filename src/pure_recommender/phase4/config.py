"""Typed configuration for PURE Phase 4 Profile Updater experiments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True, slots=True)
class Phase4InputConfig:
    extractions_path: Path


@dataclass(frozen=True, slots=True)
class Phase4ExperimentConfig:
    max_users: int = 1
    max_updates_per_user: int = 3
    fail_fast: bool = True


@dataclass(frozen=True, slots=True)
class Phase4GenerationConfig:
    temperature: float = 0.0
    max_tokens: int = 1024
    seed: int = 42


@dataclass(frozen=True, slots=True)
class Phase4OutputConfig:
    directory: Path = Path("outputs/phase4_profile_updater_pilot_v1")


@dataclass(frozen=True, slots=True)
class Phase4Config:
    input: Phase4InputConfig
    experiment: Phase4ExperimentConfig
    generation: Phase4GenerationConfig
    output: Phase4OutputConfig


def _resolve(repo_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (repo_root / path).resolve()


def load_phase4_config(config_path: str | Path) -> Phase4Config:
    path = Path(config_path).resolve()
    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    repo_root = path.parent.parent
    input_raw = raw.get("input", {})
    experiment_raw = raw.get("experiment", {})
    generation_raw = raw.get("generation", {})
    output_raw = raw.get("output", {})

    config = Phase4Config(
        input=Phase4InputConfig(
            extractions_path=_resolve(repo_root, str(input_raw["extractions_path"])),
        ),
        experiment=Phase4ExperimentConfig(
            max_users=int(experiment_raw.get("max_users", 1)),
            max_updates_per_user=int(experiment_raw.get("max_updates_per_user", 3)),
            fail_fast=bool(experiment_raw.get("fail_fast", True)),
        ),
        generation=Phase4GenerationConfig(
            temperature=float(generation_raw.get("temperature", 0.0)),
            max_tokens=int(generation_raw.get("max_tokens", 1024)),
            seed=int(generation_raw.get("seed", 42)),
        ),
        output=Phase4OutputConfig(
            directory=_resolve(
                repo_root,
                str(output_raw.get("directory", "outputs/phase4_profile_updater_pilot_v1")),
            )
        ),
    )

    if config.experiment.max_users < 1:
        raise ValueError("max_users must be >= 1")
    if config.experiment.max_updates_per_user < 1:
        raise ValueError("max_updates_per_user must be >= 1")
    if config.generation.max_tokens < 1:
        raise ValueError("generation.max_tokens must be >= 1")
    if config.generation.temperature < 0:
        raise ValueError("generation.temperature must be >= 0")

    return config
