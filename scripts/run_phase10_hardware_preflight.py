"""Run Phase 10A synthetic hardware-saturation validation.

This script performs two jobs before any confirmatory-cohort LLM call:

1. verify the exact Phase 9 cohort/session SHA256 fingerprints;
2. compare one-request-at-a-time inference with two concurrent synthetic calls.

The benchmark never reads cohort review/profile/candidate text. It uses generated
synthetic prompts only, so hardware scheduling can be selected without inspecting
any new confirmatory outcome.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time
import tomllib
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.analysis.hardware_preflight import (
    evaluate_concurrency_candidate,
    verify_phase9_freeze,
)
from pure_recommender.experiment_handoff import publish_handoff
from pure_recommender.llm import OpenAICompatibleLLMClient, load_local_llm_config


EXPERIMENT = "phase10_hardware_preflight_v1"
CONFIG_PATH = REPO_ROOT / "config" / "phase10_hardware_preflight.toml"
LLM_CONFIG_PATH = REPO_ROOT / "config" / "local_llm.toml"


def _resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def _response_format() -> dict[str, object]:
    candidate_numbers = list(range(1, 21))
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "phase10_synthetic_ranking",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "ranking": {
                        "type": "array",
                        "items": {"type": "integer", "enum": candidate_numbers},
                        "minItems": 20,
                        "maxItems": 20,
                        "uniqueItems": True,
                    }
                },
                "required": ["ranking"],
                "additionalProperties": False,
            },
        },
    }


def _synthetic_prompt(probe_index: int, history_lines: int) -> list[dict[str, str]]:
    """Build a long deterministic prompt unrelated to real experiment users."""

    adjectives = (
        "quiet", "durable", "compact", "responsive", "balanced", "lightweight",
        "precise", "ergonomic", "reliable", "simple", "stable", "efficient",
    )
    history: list[str] = []
    for row_index in range(1, history_lines + 1):
        a = adjectives[(probe_index + row_index) % len(adjectives)]
        b = adjectives[(probe_index * 3 + row_index * 5) % len(adjectives)]
        c = adjectives[(probe_index * 7 + row_index * 2) % len(adjectives)]
        history.append(
            f"Observation {row_index:03d}: synthetic product family {row_index % 17:02d} "
            f"was described as {a}, {b}, and {c}; preference weight {((row_index * 13 + probe_index) % 97) + 1}."
        )

    candidates = []
    for number in range(1, 21):
        a = adjectives[(number + probe_index) % len(adjectives)]
        b = adjectives[(number * 2 + probe_index) % len(adjectives)]
        candidates.append(
            f"{number}. Synthetic Candidate {number:02d} — {a}, {b}, score hint {(number * 37 + probe_index * 11) % 101}."
        )

    user_content = (
        "This is a synthetic throughput probe. Rank all 20 candidates from most to least compatible "
        "with the synthetic preference history. Use every candidate number exactly once.\n\n"
        "Synthetic history:\n"
        + "\n".join(history)
        + "\n\nCandidates:\n"
        + "\n".join(candidates)
        + "\n\nReturn only the structured ranking object."
    )
    return [
        {
            "role": "system",
            "content": "You are running a deterministic synthetic ranking benchmark. Follow the requested JSON schema exactly.",
        },
        {"role": "user", "content": user_content},
    ]


def _validate_probe_content(content: str) -> None:
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("Probe response is not a JSON object")
    ranking = value.get("ranking")
    if not isinstance(ranking, list) or any(type(item) is not int for item in ranking):
        raise ValueError("Probe response ranking is not an integer array")
    if sorted(ranking) != list(range(1, 21)):
        raise ValueError("Probe ranking is not a complete permutation of 1..20")


def _float_or_none(value: str) -> float | None:
    try:
        return float(value.strip())
    except (TypeError, ValueError):
        return None


def _read_gpu_sample() -> dict[str, float] | None:
    """Read one NVIDIA telemetry sample when nvidia-smi is available."""

    command = [
        "nvidia-smi",
        "--query-gpu=memory.used,memory.total,utilization.gpu,power.draw,temperature.gpu",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None

    first_line = completed.stdout.strip().splitlines()[0]
    parts = [part.strip() for part in first_line.split(",")]
    if len(parts) < 5:
        return None
    values = [_float_or_none(part) for part in parts[:5]]
    if values[0] is None or values[1] is None or values[2] is None:
        return None
    result = {
        "memory_used_mib": float(values[0]),
        "memory_total_mib": float(values[1]),
        "gpu_util_percent": float(values[2]),
    }
    if values[3] is not None:
        result["power_watts"] = float(values[3])
    if values[4] is not None:
        result["temperature_c"] = float(values[4])
    return result


class _GpuMonitor:
    def __init__(self, interval_seconds: float = 0.20) -> None:
        self.interval_seconds = interval_seconds
        self.samples: list[dict[str, float]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        def loop() -> None:
            while not self._stop.is_set():
                sample = _read_gpu_sample()
                if sample is not None:
                    self.samples.append(sample)
                self._stop.wait(self.interval_seconds)

        self._thread = threading.Thread(target=loop, name="phase10-gpu-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def summary(self) -> dict[str, object]:
        if not self.samples:
            return {"available": False, "samples": 0}
        memory_total = max(sample["memory_total_mib"] for sample in self.samples)
        return {
            "available": True,
            "samples": len(self.samples),
            "peak_vram_used_mib": max(sample["memory_used_mib"] for sample in self.samples),
            "vram_total_mib": memory_total,
            "peak_gpu_util_percent": max(sample["gpu_util_percent"] for sample in self.samples),
            "mean_gpu_util_percent": statistics.mean(sample["gpu_util_percent"] for sample in self.samples),
            "peak_power_watts": max(
                (sample.get("power_watts", 0.0) for sample in self.samples),
                default=0.0,
            ),
            "peak_temperature_c": max(
                (sample.get("temperature_c", 0.0) for sample in self.samples),
                default=0.0,
            ),
        }


def _run_probe(
    *,
    base_url: str,
    timeout_seconds: float,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    seed: int,
    response_format: dict[str, object],
) -> dict[str, object]:
    client = OpenAICompatibleLLMClient(base_url=base_url, timeout_seconds=timeout_seconds)
    started = time.perf_counter()
    response = client.chat_completion(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        seed=seed,
        response_format=response_format,
    )
    elapsed = time.perf_counter() - started
    _validate_probe_content(response.content)
    return {
        "content": response.content,
        "latency_seconds": elapsed,
        "usage": dict(response.usage) if response.usage else {},
    }


def main() -> int:
    with CONFIG_PATH.open("rb") as handle:
        config = tomllib.load(handle)

    phase9 = config["phase9"]
    benchmark = config["benchmark"]
    generation = config["generation"]
    output_cfg = config["output"]

    output_dir = _resolve(str(output_cfg["directory"]))
    output_dir.mkdir(parents=True, exist_ok=True)

    freeze = verify_phase9_freeze(
        cohort_users_path=_resolve(str(phase9["cohort_users_path"])),
        sessions_path=_resolve(str(phase9["sessions_path"])),
        cohort_summary_path=_resolve(str(phase9["cohort_summary_path"])),
        expected_cohort_sha256=str(phase9["expected_cohort_sha256"]),
        expected_sessions_sha256=str(phase9["expected_sessions_sha256"]),
        expected_users=int(phase9["expected_users"]),
        expected_sessions=int(phase9["expected_sessions"]),
    )

    llm_config = load_local_llm_config(LLM_CONFIG_PATH)
    model_client = OpenAICompatibleLLMClient(
        base_url=llm_config.base_url,
        timeout_seconds=llm_config.timeout_seconds,
    )
    visible_models = model_client.list_models()
    if llm_config.model not in visible_models:
        raise RuntimeError(
            f"Configured model {llm_config.model!r} is not exposed by the local server; visible={visible_models}"
        )

    probe_count = int(benchmark["probe_count"])
    history_lines = int(benchmark["synthetic_history_lines"])
    workers = int(benchmark["concurrent_workers"])
    warmups = int(benchmark["warmup_requests"])
    if workers != 2:
        raise ValueError("Phase 10A v1 intentionally validates exactly two concurrent workers")
    if probe_count < 2:
        raise ValueError("probe_count must be at least 2")

    prompts = [_synthetic_prompt(index, history_lines) for index in range(probe_count)]
    response_format = _response_format()

    print("=" * 108)
    print("PHASE 10A — HARDWARE SATURATION PREFLIGHT")
    print("=" * 108)
    print("Confirmatory LLM calls       : NONE")
    print(f"Phase 9 users verified       : {freeze['users']}")
    print(f"Phase 9 sessions verified    : {freeze['sessions']}")
    print(f"Cohort SHA256                : {freeze['cohort_sha256']}")
    print(f"Sessions SHA256              : {freeze['sessions_sha256']}")
    print(f"Model                        : {llm_config.model}")
    print(f"Synthetic probes             : {probe_count}")
    print(f"Candidate concurrent workers : {workers}")
    print("NOTE                         : LM Studio Max Concurrent Predictions must be 2 for this probe")
    print()

    monitor = _GpuMonitor()
    monitor.start()
    try:
        for warmup_index in range(warmups):
            _run_probe(
                base_url=llm_config.base_url,
                timeout_seconds=llm_config.timeout_seconds,
                model=llm_config.model,
                messages=_synthetic_prompt(10_000 + warmup_index, min(history_lines, 80)),
                temperature=float(generation["temperature"]),
                max_tokens=int(generation["max_tokens"]),
                seed=int(generation["seed"]),
                response_format=response_format,
            )

        sequential_results: list[dict[str, object]] = []
        sequential_started = time.perf_counter()
        for index, messages in enumerate(prompts, start=1):
            result = _run_probe(
                base_url=llm_config.base_url,
                timeout_seconds=llm_config.timeout_seconds,
                model=llm_config.model,
                messages=messages,
                temperature=float(generation["temperature"]),
                max_tokens=int(generation["max_tokens"]),
                seed=int(generation["seed"]),
                response_format=response_format,
            )
            sequential_results.append(result)
            print(f"SEQUENTIAL {index:02d}/{probe_count:02d}: {float(result['latency_seconds']):.3f}s")
        sequential_wall = time.perf_counter() - sequential_started

        concurrent_by_index: dict[int, dict[str, object]] = {}
        concurrent_started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="phase10-probe") as executor:
            futures = {
                executor.submit(
                    _run_probe,
                    base_url=llm_config.base_url,
                    timeout_seconds=llm_config.timeout_seconds,
                    model=llm_config.model,
                    messages=messages,
                    temperature=float(generation["temperature"]),
                    max_tokens=int(generation["max_tokens"]),
                    seed=int(generation["seed"]),
                    response_format=response_format,
                ): index
                for index, messages in enumerate(prompts)
            }
            for future in as_completed(futures):
                index = futures[future]
                result = future.result()
                concurrent_by_index[index] = result
                print(f"CONCURRENT {index + 1:02d}/{probe_count:02d}: {float(result['latency_seconds']):.3f}s")
        concurrent_wall = time.perf_counter() - concurrent_started
        concurrent_results = [concurrent_by_index[index] for index in range(probe_count)]
    finally:
        monitor.stop()

    gpu = monitor.summary()
    peak_vram = float(gpu["peak_vram_used_mib"]) if gpu.get("available") else None
    total_vram = float(gpu["vram_total_mib"]) if gpu.get("available") else None

    decision = evaluate_concurrency_candidate(
        sequential_outputs=[str(row["content"]) for row in sequential_results],
        concurrent_outputs=[str(row["content"]) for row in concurrent_results],
        sequential_wall_seconds=sequential_wall,
        concurrent_wall_seconds=concurrent_wall,
        min_throughput_speedup=float(benchmark["min_throughput_speedup"]),
        peak_vram_used_mib=peak_vram,
        vram_total_mib=total_vram,
        max_vram_fraction=float(benchmark["max_vram_fraction"]),
    )

    sequential_latencies = [float(row["latency_seconds"]) for row in sequential_results]
    concurrent_latencies = [float(row["latency_seconds"]) for row in concurrent_results]
    summary: dict[str, Any] = {
        "experiment": EXPERIMENT,
        "status": "PASS",
        "scientific_scope": "synthetic_runtime_probe_only_no_confirmatory_outcomes",
        "confirmatory_llm_calls": 0,
        "phase9_freeze": freeze,
        "model": llm_config.model,
        "generation": {
            "temperature": float(generation["temperature"]),
            "max_tokens": int(generation["max_tokens"]),
            "seed": int(generation["seed"]),
        },
        "probe": {
            "count": probe_count,
            "synthetic_history_lines": history_lines,
            "candidate_workers": workers,
            "sequential_mean_request_seconds": statistics.mean(sequential_latencies),
            "concurrent_mean_request_seconds": statistics.mean(concurrent_latencies),
        },
        "gpu_monitor": gpu,
        "decision": decision,
    }

    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    report = f"""# Phase 10A — Hardware Saturation Preflight

## Status

**PASS — synthetic benchmark only**

No confirmatory-cohort review, profile, candidate, target, or recommendation output was sent to the model in this stage.

## Phase 9 freeze verification

- users: {freeze['users']}
- sessions: {freeze['sessions']}
- cohort SHA256: `{freeze['cohort_sha256']}`
- sessions SHA256: `{freeze['sessions_sha256']}`

## Two-worker candidate

- exact structured-output matches: {decision['exact_matches']}/{decision['probe_count']}
- sequential wall time: {decision['sequential_wall_seconds']:.3f} s
- two-worker wall time: {decision['concurrent_wall_seconds']:.3f} s
- throughput speedup: {decision['throughput_speedup']:.3f}x
- peak VRAM fraction: {decision['peak_vram_fraction'] if decision['peak_vram_fraction'] is not None else 'N/A'}
- recommendation: **Max Concurrent Predictions = {decision['recommended_max_concurrent_predictions']}**
- accepted two-worker profile: **{decision['accepted']}**

The two-worker profile is accepted only when every canonical structured response matches the sequential reference, speedup is at least {float(benchmark['min_throughput_speedup']):.2f}x, and measured VRAM stays below {float(benchmark['max_vram_fraction']):.0%} when telemetry is available.
"""
    (output_dir / "report.md").write_text(report, encoding="utf-8")

    handoff = {
        "state": "RESULT",
        "experiment": EXPERIMENT,
        "summary": {
            "status": "PASS",
            "confirmatory_llm_calls": 0,
            "phase9_freeze": freeze,
            "model": llm_config.model,
            "decision": decision,
            "gpu_monitor": gpu,
        },
    }
    ok, message = publish_handoff(
        REPO_ROOT,
        handoff,
        commit_message="handoff: phase10 hardware preflight",
        auto_push=True,
    )
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")

    print()
    print("=" * 108)
    print("PHASE 10A SUMMARY")
    print("=" * 108)
    print(f"Exact output matches        : {decision['exact_matches']}/{decision['probe_count']}")
    print(f"Throughput speedup          : {decision['throughput_speedup']:.3f}x")
    if decision["peak_vram_fraction"] is not None:
        print(f"Peak VRAM fraction          : {float(decision['peak_vram_fraction']):.1%}")
    else:
        print("Peak VRAM fraction          : unavailable")
    print(f"Two-worker profile accepted : {decision['accepted']}")
    print(
        "Recommended Max Concurrent : "
        f"{decision['recommended_max_concurrent_predictions']}"
    )
    if decision["rejection_reasons"]:
        print(f"Reasons                     : {decision['rejection_reasons']}")
    print(f"Outputs                     : {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
