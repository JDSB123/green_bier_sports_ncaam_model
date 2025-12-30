# NCAAM Prediction Model - Versioning Strategy

## Version format

```text
v{MAJOR}.{MINOR}.{PATCH}
```

## Single source of truth

- **Repository root `VERSION`** is the only source of the running version (example: `33.6.5`).
- **Runtime** loads it via `services/prediction-service-python/app/__init__.py` and surfaces it via `/health`.
- **Deploy tooling** (`azure/deploy.ps1`) prefixes it with `v` and uses it as the container image tag.

## “One model only” policy (anti-confusion)

This repo is intentionally run in a “single active release” mode:

- **Git**: only one release tag is kept (`v33.6.5`).
- **ACR**: only one image tag is kept per repository (`v33.6.5`).
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
ncaamstablegbsvacr.azurecr.io/ncaam-prediction:v<VERSION>
ncaamstablegbsvacr.azurecr.io/gbsv-web:v<VERSION>
ncaamstablegbsvacr.azurecr.io/ncaam-ratings-sync:v<VERSION>
ncaamstablegbsvacr.azurecr.io/ncaam-odds-ingestion:v<VERSION>
```

## `/health` version

The `/health` endpoint returns the current version from `VERSION`:

```json
{
  "service": "prediction-service",
  "version": "33.6.5",
  "status": "ok"
}
```
