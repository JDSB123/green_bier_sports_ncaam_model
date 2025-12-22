# NCAA Basketball v6.3 - Azure First

Azure Container Apps in **greenbier-enterprise-rg** is the source of truth for production. Local Docker Compose is for development only.

## Primary workflow (Azure)

```powershell
cd azure
./deploy.ps1 -Environment prod -EnterpriseMode -OddsApiKey "YOUR_ACTUAL_KEY"
```

What happens:
- Builds and pushes the prediction image to ACR (ncaamprodgbeacr)
- Deploys container app `ncaam-prod-prediction` in greenbier-enterprise-rg
- Provisions PostgreSQL Flexible Server + Redis + Log Analytics
- Injects secrets (db/redis passwords, odds API key, optional Teams webhook)

To check health/logs:

```powershell
az containerapp logs show -n ncaam-prod-prediction -g greenbier-enterprise-rg --follow
curl https://ncaam-prod-prediction.azurecontainerapps.io/health
```

## Local dev (optional)

If you need to iterate locally:

```powershell
python ensure_secrets.py            # generates db/redis secrets
echo "YOUR_API_KEY" > secrets/odds_api_key.txt
docker compose build
./predict.bat
```

## Model parameters

- Home Court Advantage (Spread): 3.2 pts
- Home Court Advantage (Total): 0.0 pts
- Minimum Spread Edge: 2.5 pts
- Minimum Total Edge: 3.0 pts

## Data sources

- Bart Torvik API (ratings, Four Factors) — see [docs/BARTTORVIK_FIELDS.md](docs/BARTTORVIK_FIELDS.md)
- The Odds API (market odds)

## Notes

- Picks are manual: run `run_today.py` locally or exec into the Azure container to run with `--teams`.
- CI/CD recommended: build/push from `main` to ACR and deploy to greenbier-enterprise-rg.

