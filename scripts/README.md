# Scripts guide

Only keep operational helpers here; legacy one-offs live in scripts/archive/.

## Active
- check_azure_connectivity.sh
- check_deployment_health.py
- check_team_aliases_db_drift.py
- codespaces/ensure_codespace_ready.py
- codespaces/ensure_all_access.py
- dev/gh_secret_sync.py
- export_team_registry.py
- import_team_aliases_db_json.py
- validate_team_aliases.py
- verify-all.sh (delegates to codespaces readiness)

## Archived
Legacy or one-time utilities moved to scripts/archive/:
- apply_migration_023.py
- audit_historical_data_full.py
- backup_db.ps1
- cleanup_docker.ps1
- restore_db.ps1
- extract_r_package_mappings.R

If you need to resurrect one, move it back and document the use case.
