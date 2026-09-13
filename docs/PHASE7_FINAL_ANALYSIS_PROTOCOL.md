# Phase 7 — Final Thesis Analysis Protocol

## Purpose

Phase 7 performs deterministic post-hoc analysis on the already-frozen final recommendation results. It does **not** call the LLM and it does **not** modify any Phase 1–6 experiment artifact.

Inputs:

- `outputs/phase6_sequential_hybrid_final_v1/`
- `outputs/phase6_recency_hybrid_final_v1/`
- `outputs/phase6_icl_hybrid_final_v1/`
- `outputs/phase5_pure_recommender_hybrid_final_v4/`

Each directory must contain the local frozen `summary.json` and `results.jsonl` produced by the accepted final run.

## Validation before analysis

The runner must fail loudly unless:

- every method contains exactly 94 result rows;
- every row has `status="ok"`;
- all methods contain the exact same 94 session IDs;
- all methods aggregate to the same 20-user set;
- every target rank is within 1..20;
- recomputed user-level NDCG matches each frozen `summary.json` to numerical tolerance.

This prevents accidental analysis of historical Phase 2 artifacts or a partial run.

## Statistical unit

The final project evaluation averages session-level NDCG within each user and then averages users equally. Phase 7 therefore uses the **user** as the paired bootstrap unit.

For each baseline and each cutoff K in {1, 5, 10, 20}:

1. compute each user's mean PURE NDCG@K;
2. compute the same user's mean baseline NDCG@K;
3. form the paired difference PURE − baseline;
4. resample users with replacement;
5. calculate the mean paired difference for each bootstrap replicate;
6. report the observed mean difference and percentile 95% interval.

Default settings:

- repetitions: 10,000
- deterministic bootstrap seed: 20260913

The bootstrap interval is an uncertainty description for the frozen 20-user subset. It must not be presented as proof that these 20 users are a random sample from the full Amazon population.

## Generated local artifacts

Output directory: `outputs/phase7_final_analysis_v1/`

Generated files:

- `final_comparison.csv`
- `pure_improvements.csv`
- `paired_bootstrap.csv`
- `pure_user_win_tie_loss.csv`
- `per_user_ndcg.csv`
- `rank_summary.csv`
- `usage_latency.csv`
- `final_comparison.svg`
- `analysis_report.md`
- `analysis_summary.json`

The `outputs/` directory remains gitignored. These files are local analysis artifacts and should not be committed wholesale.

## Handoff

The runner publishes a compact summary to `handoff/latest.json` using the existing safe handoff mechanism. The handoff contains final NDCG, PURE improvements, paired-bootstrap intervals, and the local output paths. Only the handoff file is staged and committed automatically; unrelated local work, including README changes, is not touched.

If detailed manual review is required after the run, upload only these local files to the chat:

- `outputs/phase7_final_analysis_v1/analysis_report.md`
- `outputs/phase7_final_analysis_v1/paired_bootstrap.csv`
- `outputs/phase7_final_analysis_v1/analysis_summary.json`

Normally this is unnecessary because the automatic handoff is sufficient for the next step.
