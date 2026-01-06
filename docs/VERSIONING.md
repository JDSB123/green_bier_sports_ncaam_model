# NCAAM Prediction Model - Versioning Strategy

## Version format

```text
v{MAJOR}.{MINOR}.{PATCH}
```

## Single source of truth

- **Repository root `VERSION`** is the only source of the running version (example: `33.10.0`).
- **Runtime** loads it via `services/prediction-service-python/app/__init__.py` and surfaces it via `/health`.
- **Deploy tooling** (`azure/deploy.ps1`) prefixes it with `v` and uses it as the container image tag.

## “One model only” policy (anti-confusion)

This repo is intentionally run in a “single active release” mode:

- **Git**: only one release tag is kept (`v33.10.0`).
- **ACR**: old image tags are pruned after a healthy deploy (default: keep 1 tag per repo).
- **No `:latest` tags** are used for ACR images.

## Release bump process

1. Update `VERSION`
2. Run tests (`pytest services/prediction-service-python/tests/ -q`)
3. Commit on `main`
4. Tag and push:

```bash
git tag v<VERSION>
git push origin main --tags
```

5. Deploy:

```powershell
cd azure
.\deploy.ps1 -QuickDeploy -Environment stable
```

## Container image tags

```text
ncaamstablegbsvacr.azurecr.io/ncaam-prediction:v<VERSION>  # Includes embedded Go/Rust binaries
ncaamstablegbsvacr.azurecr.io/gbsv-web:v<VERSION>
```

> **Note (v33.12.0):** Standalone `ncaam-ratings-sync` and `ncaam-odds-ingestion` images
> were removed. The Go (ratings-sync) and Rust (odds-ingestion) binaries are now embedded
> in the `ncaam-prediction` image via multi-stage Docker build.

## `/health` version

The `/health` endpoint returns the current version from `VERSION`:

```json
{
  "service": "prediction-service",
  "version": "33.10.0",
  "git_sha": "unknown",
  "build_date": "",
  "status": "ok"
}
```
