# Prospect realism (generated draft prospects and how they grow)

_Work in progress. Branch `claude/prospect-realism` (worktree agent-a0c5699cab451eb42)._

## Objective
Make generated draft classes look and develop like real ones: entry level by pick range, spread, archetype mix,
physical tools vs skills, age effects, star/starter/bust rates by year 4, strong and weak years. Evidence: real
draftees in the canonical league (drafted 2019-2026), Basketball Index growth history (2015-16 to 2025-26), and a
Basketball-Reference draft list 2013-2023 (local only, `output/prospect-realism/real_drafts_2013_2023.csv`).

## Boundaries
Generator: `src/nba_gm_data/draft.py` (generate_draft_class_records and conversion), `talent.py`; growth:
`health.py` (prospect learning runway only). Measurement: `scripts/research/prospect_realism*.py`. Tests:
`tests/test_prospect_realism.py`. Keep all 94 inputs; no clipping at 100; no Basketball Index rows committed.

## Resume state
- Data symlinked from main checkout (bbi tools/normalized, canonical inputs, sqlite). Branch renamed.
- `scripts/research/prospect_realism.py real|generated` written; next: run, build report tables, diagnose.
