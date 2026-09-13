# Phase 7 — Final Deterministic Thesis Analysis Results

## Status

**PASS / FROZEN**

Phase 7 is a post-hoc deterministic analysis of the four already-frozen recommendation methods. It makes **zero LLM calls** and does not modify any Phase 3–6 experimental result.

## Alignment checks

- aligned recommendation sessions: **94**
- users: **20**
- all four methods aligned on the same frozen sessions/users: **PASS**
- bootstrap unit: **user**
- bootstrap repetitions: **10,000**
- bootstrap seed: **20260913**

The bootstrap must be interpreted only as uncertainty within the project's frozen 20-user evaluation subset. The selected users are not treated as a population-random sample.

## Frozen final NDCG comparison

| Method | NDCG@1 | NDCG@5 | NDCG@10 | NDCG@20 |
|---|---:|---:|---:|---:|
| Sequential | 0.078333 | 0.191193 | 0.229859 | 0.373286 |
| Recency-Focused | 0.095000 | 0.206505 | 0.252952 | 0.385799 |
| ICL | 0.061667 | 0.184046 | 0.244447 | 0.368731 |
| **PURE** | **0.104251** | **0.243553** | **0.318376** | **0.416023** |

PURE has the highest point estimate at all four cutoffs. Recency-Focused is the strongest baseline at all four cutoffs.

## PURE improvement over the strongest baseline

| Metric | Absolute delta | Relative improvement |
|---|---:|---:|
| NDCG@1 | +0.009251 | +9.74% |
| NDCG@5 | +0.037048 | +17.94% |
| NDCG@10 | +0.065425 | +25.86% |
| NDCG@20 | +0.030223 | +7.83% |

The largest relative advantage over the strongest baseline is observed at **NDCG@10**.

## Paired user-level bootstrap: PURE minus baseline

The analysis resamples users with replacement and preserves the project's equal-user aggregation logic.

### Versus Sequential

| Metric | Delta | 95% bootstrap CI | Bootstrap fraction > 0 |
|---|---:|---:|---:|
| NDCG@1 | +0.025917 | [-0.059475, 0.111324] | 0.7167 |
| NDCG@5 | +0.052360 | [-0.043647, 0.149505] | 0.8548 |
| NDCG@10 | +0.088518 | [-0.013892, 0.188308] | 0.9560 |
| NDCG@20 | +0.042737 | [-0.027272, 0.111651] | 0.8863 |

### Versus Recency-Focused

| Metric | Delta | 95% bootstrap CI | Bootstrap fraction > 0 |
|---|---:|---:|---:|
| NDCG@1 | +0.009251 | [-0.108291, 0.124643] | 0.5612 |
| NDCG@5 | +0.037048 | [-0.081307, 0.151626] | 0.7440 |
| NDCG@10 | +0.065425 | [-0.045023, 0.174396] | 0.8795 |
| NDCG@20 | +0.030223 | [-0.057199, 0.114097] | 0.7540 |

### Versus ICL

| Metric | Delta | 95% bootstrap CI | Bootstrap fraction > 0 |
|---|---:|---:|---:|
| NDCG@1 | +0.042584 | [-0.051584, 0.142110] | 0.7986 |
| NDCG@5 | +0.059507 | [-0.038107, 0.154807] | 0.8817 |
| NDCG@10 | +0.073930 | [-0.021141, 0.166900] | 0.9386 |
| NDCG@20 | +0.047292 | [-0.022910, 0.119578] | 0.9045 |

## Statistical interpretation

All reported 95% paired-bootstrap intervals include zero. Therefore the thesis must **not** claim conventional 95% statistical significance for PURE over any baseline on this frozen 20-user subset.

The defensible conclusion is narrower:

- PURE has higher observed NDCG point estimates than every baseline at all four cutoffs;
- the strongest observed advantage is at NDCG@10;
- the user-level bootstrap often favors a positive PURE delta, especially at NDCG@10, but the uncertainty intervals remain wide because the evaluation contains only 20 users;
- these bootstrap fractions are descriptive resampling quantities, not p-values and not evidence of population-level significance.

## Thesis-ready wording

A suitable interpretation for the results chapter is:

> In the controlled local evaluation, PURE achieved the highest NDCG point estimate at every evaluated cutoff. Relative to the strongest baseline, Recency-Focused, the observed improvements were approximately 9.74%, 17.94%, 25.86%, and 7.83% at NDCG@1, @5, @10, and @20, respectively. However, paired user-level bootstrap confidence intervals based on the 20-user frozen subset included zero for all comparisons. Accordingly, the results support a descriptive performance advantage for PURE in this experiment, but they should not be interpreted as establishing population-level statistical significance.

## Scientific labeling

These results are authoritative only for this project's:

- local derivative `llama-3.2-3b-instruct-uncensored` model;
- frozen 20-user / 94-session subset;
- frozen preprocessing and candidate-sampling policy;
- finalized prompts, structured-output validation, and reproduction engineering choices.

They are **not** an exact reproduction of the paper checkpoint or the paper's full-dataset results.

## Local Phase 7 artifacts

Authoritative local output directory:

`outputs/phase7_final_analysis_v1/`

Important generated files include:

- `analysis_summary.json`
- `analysis_report.md`
- `paired_bootstrap.csv`
- `final_comparison.svg`

These remain local under the ignored `outputs/` directory; the frozen scientific conclusions are recorded in this document.
