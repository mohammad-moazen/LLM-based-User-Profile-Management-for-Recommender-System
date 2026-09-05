# LLM-based User Profile Management for Recommender System

This repository is a step-by-step Python reproduction of the PURE framework from the paper **"LLM-based User Profile Management for Recommender System"**.

## Development approach

We will build the reproduction incrementally so each phase can be pulled and tested locally in VS Code before moving to the next phase.

## Roadmap

### Phase 1 — Minimal end-to-end reproduction

- Data loading and preprocessing
- Chronological user interaction histories
- Candidate sampling
- Review Extractor
- LLM-based Recommender
- NDCG evaluation

### Phase 2 — Continuous sequential recommendation

- Evaluate predictions across multiple timesteps per user
- Maintain evolving user histories

### Phase 3 — Profile Updater

- Merge newly extracted preferences with previous profiles
- Remove redundant or conflicting information
- Track profile/token growth

### Phase 4 — Baselines

- Sequential
- Recency-focused
- In-context learning (ICL)

### Phase 5 — Larger-scale reproduction

- Amazon Video Games
- Amazon Movies & TV
- Ablation experiments
- Token/performance trade-off analysis

## Workflow

1. Changes are implemented on the `feature/pure-phase1` branch.
2. Pull the latest branch locally in VS Code.
3. Run and test locally.
4. Report outputs or errors.
5. We iterate until Phase 1 is stable, then expand toward the full PURE reproduction.

More setup and run instructions will be added as the implementation progresses.
