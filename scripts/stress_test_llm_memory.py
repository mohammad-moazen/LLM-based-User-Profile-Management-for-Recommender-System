"""Stress-test local llama-server RAM stability without touching experiment outputs.

This diagnostic repeatedly sends the same small deterministic request to the
configured local OpenAI-compatible model and samples Windows process memory for
all ``llama-server`` processes. It is intentionally separate from recommendation
experiments: it does not read Phase 1 sessions and does not write into any
baseline output directory.

The goal is to distinguish normal one-time warm-up/cache allocation from
continued request-by-request memory growth after the runtime settings have been
changed (for example, parallel predictions reduced from 4 to 1).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.llm import OpenAICompatibleLLMClient, load_local_llm_config


def _sample_llama_server_memory() -> dict[str, Any]:
    """Return aggregate Windows memory for all llama-server processes."""

    powershell = r"""
$rows = @(Get-Process llama-server -ErrorAction SilentlyContinue |
    Select-Object Id, WorkingSet64, PrivateMemorySize64)
if ($rows.Count -eq 0) {
    Write-Output '[]'
} else {
    $rows | ConvertTo-Json -Compress
}
""".strip()

    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", powershell],
        check=True,
        capture_output=True,
        text=True,
    )
    text = completed.stdout.strip()
    if not text:
        raise RuntimeError("PowerShell returned no process-memory data")

    payload = json.loads(text)
    if isinstance(payload, dict):
        rows = [payload]
    elif isinstance(payload, list):
        rows = payload
    else:
        raise RuntimeError("Unexpected PowerShell process-memory payload")

    if not rows:
        raise RuntimeError(
            "No llama-server process was found. Load the model in LM Studio and keep the server running."
        )

    working_set = sum(int(row.get("WorkingSet64", 0) or 0) for row in rows)
    private_bytes = sum(int(row.get("PrivateMemorySize64", 0) or 0) for row in rows)
    return {
        "process_count": len(rows),
        "process_ids": [int(row["Id"]) for row in rows if "Id" in row],
        "working_set_bytes": working_set,
        "private_bytes": private_bytes,
        "working_set_gb": working_set / (1024 ** 3),
        "private_gb": private_bytes / (1024 ** 3),
    }


def _print_sample(label: str, completed_requests: int, sample: dict[str, Any]) -> None:
    print(
        f"{label:<14} requests={completed_requests:>3}  "
        f"working_set={sample['working_set_gb']:.3f} GB  "
        f"private={sample['private_gb']:.3f} GB  "
        f"processes={sample['process_count']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Stress-test llama-server RAM stability")
    parser.add_argument(
        "--llm-config",
        default=str(REPO_ROOT / "config" / "local_llm.toml"),
        help="Path to local LLM TOML config",
    )
    parser.add_argument("--requests", type=int, default=100, help="Measured requests to send")
    parser.add_argument("--warmup", type=int, default=5, help="Warm-up requests before baseline sampling")
    parser.add_argument("--sample-every", type=int, default=10, help="Sample RAM every N measured requests")
    parser.add_argument("--max-tokens", type=int, default=16, help="Max completion tokens per diagnostic request")
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "outputs" / "runtime_memory_test" / "report.json"),
        help="Local JSON report path (outputs/ is gitignored)",
    )
    args = parser.parse_args()

    if args.requests <= 0:
        raise ValueError("--requests must be positive")
    if args.warmup < 0:
        raise ValueError("--warmup must be non-negative")
    if args.sample_every <= 0:
        raise ValueError("--sample-every must be positive")

    llm_config = load_local_llm_config(args.llm_config)
    client = OpenAICompatibleLLMClient(
        base_url=llm_config.base_url,
        timeout_seconds=llm_config.timeout_seconds,
    )

    visible_models = client.list_models()
    if llm_config.model not in visible_models:
        raise RuntimeError(
            f"Configured model {llm_config.model!r} is not exposed by the local server. "
            f"Visible models: {visible_models}"
        )

    messages = [
        {
            "role": "system",
            "content": "You are a deterministic local runtime diagnostic assistant.",
        },
        {
            "role": "user",
            "content": "Reply with exactly the word OK and nothing else.",
        },
    ]

    print("=" * 88)
    print("LOCAL LLM RAM STABILITY TEST")
    print("=" * 88)
    print(f"Model          : {llm_config.model}")
    print(f"Endpoint       : {llm_config.base_url}")
    print(f"Warm-up        : {args.warmup}")
    print(f"Requests       : {args.requests}")
    print(f"Sample every   : {args.sample_every}")
    print(f"Max tokens     : {args.max_tokens}")
    print("Experiment data: NOT USED")
    print()

    initial = _sample_llama_server_memory()
    _print_sample("initial", 0, initial)

    for index in range(1, args.warmup + 1):
        client.chat_completion(
            model=llm_config.model,
            messages=messages,
            temperature=0.0,
            max_tokens=args.max_tokens,
            seed=42,
        )
        if index == args.warmup:
            print(f"Warm-up complete ({args.warmup} requests).")

    baseline = _sample_llama_server_memory()
    _print_sample("post-warmup", 0, baseline)

    samples: list[dict[str, Any]] = []
    started = time.perf_counter()
    for index in range(1, args.requests + 1):
        client.chat_completion(
            model=llm_config.model,
            messages=messages,
            temperature=0.0,
            max_tokens=args.max_tokens,
            seed=42,
        )

        if index % args.sample_every == 0 or index == args.requests:
            sample = _sample_llama_server_memory()
            sample["completed_requests"] = index
            samples.append(sample)
            _print_sample("sample", index, sample)

    elapsed = time.perf_counter() - started
    final = samples[-1] if samples else _sample_llama_server_memory()
    private_delta_gb = float(final["private_gb"]) - float(baseline["private_gb"])
    working_delta_gb = float(final["working_set_gb"]) - float(baseline["working_set_gb"])

    report = {
        "model": llm_config.model,
        "endpoint": llm_config.base_url,
        "warmup_requests": args.warmup,
        "measured_requests": args.requests,
        "sample_every": args.sample_every,
        "max_tokens": args.max_tokens,
        "temperature": 0.0,
        "seed": 42,
        "initial": initial,
        "post_warmup_baseline": baseline,
        "samples": samples,
        "final_private_delta_gb_vs_post_warmup": private_delta_gb,
        "final_working_set_delta_gb_vs_post_warmup": working_delta_gb,
        "elapsed_seconds": elapsed,
        "mean_seconds_per_request": elapsed / args.requests,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

    print()
    print("=" * 88)
    print("RAM STABILITY SUMMARY")
    print("=" * 88)
    print(f"post-warmup private RAM : {baseline['private_gb']:.3f} GB")
    print(f"final private RAM       : {final['private_gb']:.3f} GB")
    print(f"private RAM delta       : {private_delta_gb:+.3f} GB")
    print(f"working-set delta       : {working_delta_gb:+.3f} GB")
    print(f"mean request latency    : {report['mean_seconds_per_request']:.3f} sec")
    print(f"report                  : {output_path}")
    print()
    print("Interpretation rule: focus on the trend AFTER warm-up. A small early allocation followed by")
    print("a plateau is normal; a sustained near-linear rise in private RAM across samples needs follow-up.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
