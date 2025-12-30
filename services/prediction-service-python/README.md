# NCAAM Prediction Service

This directory hosts the self-contained prediction service. For users who cannot start
the full Docker/Postgres stack, there is a lightweight helper CLI:

```bash
python scripts/manual_matchup.py --home "Utah" --away "Washington"
```

You can override the spread/total or the implied American prices via
`--spread`, `--total`, `--spread-home-price`, `--over-price`, etc. The helper only
covers the Utah/Washington presets right now, but the fixture dictionary at the top
of `scripts/manual_matchup.py` can be extended with additional teams as needed.
