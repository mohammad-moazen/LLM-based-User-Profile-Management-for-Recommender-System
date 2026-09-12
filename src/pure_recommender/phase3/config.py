"""Typed configuration for Phase 3 PURE Review Extractor experiments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True, slots=True)
class Phase3InputConfig:
    interactions_path: Path
    sessions_path: Path


@dataclass(frozen=True, slots=True)
class Phase3ExperimentConfig:
    max_extractions: int = 3
    resume: bool = True
    fail_fast: bool = True


@dataclass(frozen=True, slots=True)
class Phase3GenerationConfig:
    temperature: float = 0.0
    max_tokens: int = 512
    seed: int = 42


@dataclass(frozen=True, slots=True)
class Phase3OutputConfig:
    directory: Path = Path("outputs/phase3_review_extractor")


@dataclass(frozen=True, slots=True)
class Phase3Config:
    input: Phase3InputConfig
    experiment: Phase3ExperimentConfig
    generation: Phase3GenerationConfig
    output: Phase3OutputConfig


def _resolve(repo_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (repo_root / path).resolve()


def load_phase3_config(config_path: str | Path) -> Phase3Config:
    """Load Review Extractor TOML settings and resolve repo-relative paths."""

    path = Path(config_path).resolve()
    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    repo_root = path.parent.parent
    input_raw = raw.get("input", {})
    experiment_raw = raw.get("experiment", {})
    generation_raw = raw.get("generation", {})
    output_raw = raw.get("output", {})

    config = Phase3Config(
        input=Phase3InputConfig(
            interactions_path=_resolve(repo_root, str(input_raw["interactions_path"])),
            sessions_path=_resolve(repo_root, str(input_raw["sessions_path"])),
        ),
        experiment=Phase3ExperimentConfig(
            max_extractions=int(experiment_raw.get("max_extractions", 3)),
            resume=bool(experiment_raw.get("resume", True)),
            fail_fast=bool(experiment_raw.get("fail_fast", True)),
        ),
        generation=Phase3GenerationConfig(
            temperature=float(generation_raw.get("temperature", 0.0)),
            max_tokens=int(generation_raw.get("max_tokens", 512)),
            seed=int(generation_raw.get("seed", 42)),
        ),
        output=Phase3OutputConfig(
            directory=_resolve(
                repo_root,
                str(output_raw.get("directory", "outputs/phase3_review_extractor")),
            )
        ),
    )

    if config.experiment.max_extractions < 0:
        raise ValueError("max_extractions must be >= 0; use 0 for every required extraction")
    if config.generation.max_tokens < 1:
        raise ValueError("generation.max_tokens must be >= 1")
    if config.generation.temperature < 0:
        raise ValueError("generation.temperature must be >= 0")

    return config
