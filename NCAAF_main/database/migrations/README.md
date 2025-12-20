# Database Migrations

This directory contains database migrations for the NCAAF v5.0 system using [golang-migrate](https://github.com/golang-migrate/migrate).

## Prerequisites

Install golang-migrate CLI:

```bash
# macOS
brew install golang-migrate

# Linux
curl -L https://github.com/golang-migrate/migrate/releases/download/v4.17.0/migrate.linux-amd64.tar.gz | tar xvz
sudo mv migrate /usr/local/bin/

# Windows (using Scoop)
scoop install migrate

# Or download from: https://github.com/golang-migrate/migrate/releases
```

## Running Migrations

### Apply All Migrations (Up)
```bash
cd ingestion
make migrate-up

# Or manually:
migrate -path ../database/migrations -database "postgres://ncaaf_user:ncaaf_password@localhost:5432/ncaaf_v5?sslmode=disable" up
```

### Rollback Last Migration (Down)
```bash
make migrate-down

# Or manually:
migrate -path ../database/migrations -database "postgres://..." down 1
```

### Check Migration Status
```bash
migrate -path ../database/migrations -database "postgres://..." version
```

### Force Migration Version (if stuck)
```bash
make migrate-force version=1
```

## Creating New Migrations

```bash
make migrate-create name=add_analytics_table

# This creates:
# - database/migrations/000002_add_analytics_table.up.sql
# - database/migrations/000002_add_analytics_table.down.sql
```

## Migration Files

### 000001_initial_schema
- **Up**: Creates all base tables (teams, games, odds, predictions, etc.)
- **Down**: Drops all tables

## Migration Best Practices

1. **Always create both UP and DOWN migrations**
   - UP: Apply the change
   - DOWN: Revert the change

2. **Never modify existing migrations**
   - Once applied in production, migrations are immutable
   - Create new migration to fix issues

3. **Test migrations before deployment**
   ```bash
   # Test up migration
   make migrate-up

   # Test down migration
   make migrate-down

   # Reapply
   make migrate-up
   ```

4. **Use transactions** (PostgreSQL supports DDL in transactions)
   - Wrap complex migrations in `BEGIN`/`COMMIT`
   - If any step fails, entire migration rolls back

5. **Keep migrations small and focused**
   - One logical change per migration
   - Easier to debug and rollback

## Docker Compose Integration

Migrations run automatically on container startup via Docker Compose:

```yaml
ingestion:
  ...
  command: |
    sh -c "
      migrate -path /app/migrations -database \$DATABASE_URL up &&
      /app/worker
    "
```

## Troubleshooting

### Dirty State
If migration fails midway:
```bash
# Check version and dirty state
migrate -path ../database/migrations -database "postgres://..." version

# Force to last good version
make migrate-force version=1

# Fix the migration file
# Then rerun
make migrate-up
```

### Connection Issues
```bash
# Test database connection
psql "postgres://ncaaf_user:ncaaf_password@localhost:5432/ncaaf_v5"

# If connection fails, check:
# 1. PostgreSQL is running
# 2. Credentials are correct
# 3. Database exists
# 4. Network/firewall allows connection
```

### Migration Order
Migrations run in numerical order:
- `000001_*.sql` runs first
- `000002_*.sql` runs second
- etc.

## Environment Variables

Set `DATABASE_URL` for custom database connection:

```bash
export DATABASE_URL="postgres://user:pass@host:port/dbname?sslmode=disable"
make migrate-up
```

Or use `.env` file:
```bash
DATABASE_URL=postgres://ncaaf_user:ncaaf_password@localhost:5432/ncaaf_v5?sslmode=disable
```
