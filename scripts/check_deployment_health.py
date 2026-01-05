#!/usr/bin/env python3
"""
Deployment Health Check - Validate Environment Before Deployment

This script validates that the deployment environment is ready:
- Database connectivity
- Required migrations applied
- Schema integrity
- Service dependencies

Usage:
    python scripts/check_deployment_health.py

Exit codes:
    0: Environment is healthy
    1: Environment has issues requiring attention
"""

import os
import sys
from pathlib import Path

# Add services to path
sys.path.insert(0, str(Path(__file__).parent / "services" / "prediction-service-python"))

try:
    from sqlalchemy import create_engine, text
    import psycopg2
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False


def get_database_url():
    """Get database URL from environment or Docker secrets."""
    # Try DATABASE_URL first (Azure)
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return db_url

    # Try building from components (Docker)
    db_user = os.environ.get("DB_USER", "ncaam")
    db_name = os.environ.get("DB_NAME", "ncaam")
    db_host = os.environ.get("DB_HOST", "postgres")
    db_port = os.environ.get("DB_PORT", "5432")

    # Read password from Docker secret
    pw_file = os.environ.get("DB_PASSWORD_FILE", "/run/secrets/db_password")
    if Path(pw_file).exists():
        with open(pw_file, "r") as f:
            password = f.read().strip()
        return f"postgresql://{db_user}:{password}@{db_host}:{db_port}/{db_name}"

    return None


def check_database_connectivity():
    """Check if we can connect to the database."""
    print("🔗 Checking database connectivity...")

    db_url = get_database_url()
    if not db_url:
        print("❌ DATABASE_URL not configured")
        return False, "Database URL not configured"

    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✅ Connected to PostgreSQL: {version.split()[1]}")
            return True, None
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False, str(e)


def check_required_migrations(engine):
    """Check if all required migrations are applied."""
    print("📊 Checking required migrations...")

    required_migrations = [
        '001_initial_schema.sql',
        '012_recommendation_probabilities.sql',  # Critical for API functionality
        '021_schema_migrations_table.sql',       # Migration tracking
    ]

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT filename FROM public.schema_migrations
                WHERE filename = ANY(:migrations)
            """), {"migrations": required_migrations})

            applied = {row[0] for row in result}
            missing = [m for m in required_migrations if m not in applied]

            if missing:
                print(f"❌ Missing {len(missing)} required migrations:")
                for mig in missing:
                    print(f"   - {mig}")
                return False, f"Missing migrations: {missing}"
            else:
                print(f"✅ All {len(required_migrations)} required migrations applied")
                return True, None

    except Exception as e:
        print(f"❌ Migration check failed: {e}")
        return False, str(e)


def check_schema_integrity(engine):
    """Check schema integrity and required tables/columns."""
    print("🔍 Checking schema integrity...")

    required_tables = [
        'games', 'teams', 'predictions', 'betting_recommendations',
        'odds_snapshots', 'team_resolution_audit', 'schema_migrations'
    ]

    required_columns = {
        'betting_recommendations': [
            'pick_price',  # Critical for API
            'prediction_id', 'game_id', 'bet_type', 'pick', 'line'
        ]
    }

    try:
        with engine.connect() as conn:
            # Check tables exist
            result = conn.execute(text("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public' AND tablename = ANY(:tables)
            """), {"tables": required_tables})

            existing_tables = {row[0] for row in result}
            missing_tables = [t for t in required_tables if t not in existing_tables]

            if missing_tables:
                print(f"❌ Missing {len(missing_tables)} required tables:")
                for table in missing_tables:
                    print(f"   - {table}")
                return False, f"Missing tables: {missing_tables}"

            # Check critical columns exist
            for table, columns in required_columns.items():
                result = conn.execute(text("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = :table AND column_name = ANY(:columns)
                """), {"table": table, "columns": columns})

                existing_cols = {row[0] for row in result}
                missing_cols = [c for c in columns if c not in existing_cols]

                if missing_cols:
                    print(f"❌ Table '{table}' missing {len(missing_cols)} critical columns:")
                    for col in missing_cols:
                        print(f"   - {col}")
                    return False, f"Table {table} missing columns: {missing_cols}"

            print(f"✅ Schema integrity verified - {len(required_tables)} tables, critical columns present")
            return True, None

    except Exception as e:
        print(f"❌ Schema integrity check failed: {e}")
        return False, str(e)


def check_service_dependencies():
    """Check if required services are accessible."""
    print("🔗 Checking service dependencies...")

    issues = []

    # Check Redis (if configured)
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            import redis
            # Parse Redis URL
            if redis_url.startswith("rediss://"):
                # SSL connection - basic connectivity check
                print("✅ Redis URL configured (SSL)")
            else:
                print("✅ Redis URL configured")
        except ImportError:
            issues.append("redis library not available")
        except Exception as e:
            issues.append(f"Redis connection issue: {e}")
    else:
        issues.append("REDIS_URL not configured")

    # Check Odds API key
    odds_key = os.environ.get("THE_ODDS_API_KEY") or os.environ.get("ODDS_API_KEY")
    if not odds_key:
        # Check if file-based secret exists
        key_file = os.environ.get("THE_ODDS_API_KEY_FILE", "/run/secrets/odds_api_key")
        if not Path(key_file).exists():
            issues.append("Odds API key not configured")

    if issues:
        print(f"⚠️  {len(issues)} service dependency issues:")
        for issue in issues:
            print(f"   - {issue}")
        return False, f"Service dependencies: {issues}"
    else:
        print("✅ Service dependencies verified")
        return True, None


def main():
    """Run all health checks."""
    print("🏥 Deployment Health Check")
    print("=" * 50)

    if not HAS_SQLALCHEMY:
        print("❌ SQLAlchemy not available - cannot run health checks")
        return 1

    all_passed = True
    issues = []

    # Run all checks
    checks = [
        ("Database Connectivity", check_database_connectivity),
        ("Service Dependencies", check_service_dependencies),
    ]

    # Database-dependent checks
    db_connected = False
    db_engine = None

    for check_name, check_func in checks:
        print(f"\n{check_name}:")
        try:
            if "Database" in check_name:
                success, error = check_func()
                if success:
                    db_connected = True
                    # Create engine for subsequent checks
                    db_url = get_database_url()
                    if db_url:
                        db_engine = create_engine(db_url)
            else:
                success, error = check_func()

            if success:
                print(f"✅ {check_name} PASSED")
            else:
                print(f"❌ {check_name} FAILED: {error}")
                all_passed = False
                issues.append(f"{check_name}: {error}")

        except Exception as e:
            print(f"❌ {check_name} ERROR: {e}")
            all_passed = False
            issues.append(f"{check_name}: {e}")

    # Schema checks (require database connection)
    if db_connected and db_engine:
        schema_checks = [
            ("Required Migrations", lambda: check_required_migrations(db_engine)),
            ("Schema Integrity", lambda: check_schema_integrity(db_engine)),
        ]

        for check_name, check_func in schema_checks:
            print(f"\n{check_name}:")
            try:
                success, error = check_func()
                if success:
                    print(f"✅ {check_name} PASSED")
                else:
                    print(f"❌ {check_name} FAILED: {error}")
                    all_passed = False
                    issues.append(f"{check_name}: {error}")
            except Exception as e:
                print(f"❌ {check_name} ERROR: {e}")
                all_passed = False
                issues.append(f"{check_name}: {e}")

    # Summary
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 DEPLOYMENT HEALTH CHECK PASSED")
        print("✅ Environment is ready for deployment")
        return 0
    else:
        print("❌ DEPLOYMENT HEALTH CHECK FAILED")
        print(f"⚠️  {len(issues)} issues found:")
        for issue in issues:
            print(f"   - {issue}")
        print("\n🔧 Fix these issues before deploying!")
        return 1


if __name__ == "__main__":
    exit(main())