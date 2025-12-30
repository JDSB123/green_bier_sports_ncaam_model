# 🧠 NCAAM Analysis Configuration (Repo-Aligned)

This document is a **clean, repo-aligned** version of an “analysis configuration / LLM prompt spec”.

**Security note:** do **not** put API keys, usernames, or passwords in this file (or anywhere in git). Use Docker secrets under `secrets/` and `/run/secrets/*` mounts instead.

## What the current repo actually supports (today)

**Segments supported:**
- Full Game (FG)
- First Half (1H)

**Markets supported (today):**
- Spread (FG)
- Total (FG)
- Spread (1H)
- Total (1H)

**Not implemented in the current pipeline (would require new code + schema work):**
- Moneyline (ML) recommendations
- Team totals (over/under)
- Parlay construction + correlation rules
- Action Network integration (splits/steam/“PRO signals”)
- API-Basketball ingestion for advanced team stats
- Any XGBoost/SHAP-based reweighting logic

## Data sources (current vs aspirational)

**Current runtime pipeline uses:**
- Bart Torvik ratings (via the Go sync service)
- The Odds API odds snapshots (via the Rust ingestion service)

**Aspirational / future sources mentioned in the spec:**
- API-Basketball (would need an ingestion module and a stable join strategy)
- Action Network (would need an integration module; scraping introduces fragility and policy risk)

## Market context signals (what exists today)

The prediction engine already supports **market context adjustments** when data is available in stored odds:
- Line move (open → current)
- Steam thresholding (big, fast moves)
- Reverse line movement (requires public bet % fields to be populated)

These signals currently adjust **confidence** (not the base model line) and then flow into:
- EV calculation
- Kelly sizing
- Recommendation gating via minimum confidence + minimum edge

## Output expectations (what exists today)

The system is designed to emit **one row per recommendation** with:
- Game identifiers, teams, start time
- Bet type (spread/total; FG/1H)
- Pick side (home/away or over/under)
- Market line + model line
- Edge, confidence
- EV % and Kelly fraction
- Optional sharp alignment fields and open-line comparisons (when stored)

If you want the exact “CSV schema” from the aspirational prompt (bets %, money %, timestamp windows, etc.), treat that as a **new contract** and implement it explicitly (schema + ingestion + report generation).

## Secrets and credentials (how to do it safely)

- Use `secrets/odds_api_key.txt` (mounted to `/run/secrets/odds_api_key`) for The Odds API.
- Do not store credentials in documentation, prompts, `.env`, or source.
- If you add new providers (API-Basketball, Action Network), wire them the same way:
  - `secrets/<provider>_api_key.txt` → `/run/secrets/<provider>_api_key`

## If you want the “full spec” behavior

To reach the spec you pasted (10 picks per game, dynamic weighting, correlation checks), the repo would need:
- New market support (ML + team totals) end-to-end: ingestion → odds storage → model probability → EV → rec generation → reporting
- A robust data source integration plan (and clear source-of-truth decisions)
- A correlation model + parlay construction module (and explicit guardrails)

Until that exists, treat the spec as **strategy guidance**, not as a description of the current production behavior.
