"""Configuration loading for the reproducible Phase 1 pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True, slots=True)
class DataConfig:
    reviews_path: Path
    metadata_path: Path


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    min_history: int = 3
    candidate_size: int = 20
    candidate_seed: int = 42
    user_selection_seed: int = 20260905
    max_users: int = 20


@dataclass(frozen=True, slots=True)
class OutputConfig:
    directory: Path = Path("outputs/phase1")
    write_interactions: bool = True
    write_items: bool = True
    write_sessions: bool = True


@dataclass(frozen=True, slots=True)
class Phase1Config:
    data: DataConfig
    experiment: ExperimentConfig
    output: OutputConfig


def _resolve(base_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base_dir / path).resolve()


def load_phase1_config(config_path: str | Path) -> Phase1Config:
    """Load TOML config and resolve relative paths from the repository root."""

    config_path = Path(config_path).resolve()
    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)

    repo_root = config_path.parent.parent
    data_raw = raw.get("data", {})
    exp_raw = raw.get("experiment", {})
    output_raw = raw.get("output", {})

    data = DataConfig(
        reviews_path=_resolve(repo_root, data_raw["reviews_path"]),
        metadata_path=_resolve(repo_root, data_raw["metadata_path"]),
    )
    experiment = ExperimentConfig(
        min_history=int(exp_raw.get("min_history", 3)),
        candidate_size=int(exp_raw.get("candidate_size", 20)),
        candidate_seed=int(exp_raw.get("candidate_seed", 42)),
        user_selection_seed=int(exp_raw.get("user_selection_seed", 20260905)),
        max_users=int(exp_raw.get("max_users", 20)),
    )
    output = OutputConfig(
        directory=_resolve(repo_root, output_raw.get("directory", "outputs/phase1")),
        write_interactions=bool(output_raw.get("write_interactions", True)),
        write_items=bool(output_raw.get("write_items", True)),
        write_sessions=bool(output_raw.get("write_sessions", True)),
    )

    if experiment.min_history < 1:
        raise ValueError("min_history must be >= 1")
    if experiment.candidate_size < 2:
        raise ValueError("candidate_size must be >= 2")
    if experiment.max_users < 0:
        raise ValueError("max_users must be >= 0; use 0 for all eligible users")

    return Phase1Config(data=data, experiment=experiment, output=output)
