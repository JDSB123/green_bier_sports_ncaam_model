#!/usr/bin/env python3
"""
Force Apply Missing Migrations - Sustainable Database Schema Fix

This script addresses the issue where deployed databases may be missing
recent migrations due to the migration system's safety-first approach.

Usage:
    # Force apply all missing migrations (safe for production)
    python scripts/force_migration_fix.py

    # Check what migrations are missing without applying
    python scripts/force_migration_fix.py --dry-run

    # Apply specific migrations only
    python scripts/force_migration_fix.py --migrations 012_recommendation_probabilities.sql
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Set

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
import psycopg2


def get_database_url() -> str:
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

    raise RuntimeError("DATABASE_URL not set and DB_PASSWORD_FILE not found")


def get_ordered_migration_files() -> List[Path]:
    """Get all numbered migration files in order."""
    migrations_dir = Path(__file__).parent.parent / "migrations"
    return sorted(migrations_dir.glob("[0-9][0-9][0-9]_*.sql"))


def get_applied_migrations(engine) -> Set[str]:
    """Get set of applied migration filenames."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT filename FROM public.schema_migrations
            """))
            return {row[0] for row in result}
    except Exception:
        # Schema migrations table might not exist yet
        return set()


def apply_migration_file(engine, file_path: Path) -> None:
    """Apply a single migration file."""
    print(f"📄 Applying {file_path.name}...")

    with open(file_path, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Split into statements and execute
    statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]

    with engine.connect() as conn:
        for stmt in statements:
            if stmt:
                conn.execute(text(stmt))
                conn.commit()

    # Mark as applied
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO public.schema_migrations (filename, applied_at)
            VALUES (:filename, NOW())
            ON CONFLICT (filename) DO NOTHING
        """), {"filename": file_path.name})
        conn.commit()

    print(f"✅ Applied {file_path.name}")


def main():
    parser = argparse.ArgumentParser(description="Force apply missing database migrations")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what migrations are missing without applying them"
    )
    parser.add_argument(
        "--migrations",
        nargs="*",
        help="Specific migration filenames to apply (e.g., 012_recommendation_probabilities.sql)"
    )

    args = parser.parse_args()

    print("🔧 Database Migration Fix Tool")
    print("=" * 50)

    try:
        db_url = get_database_url()
        print(f"🔗 Connecting to database...")

        engine = create_engine(db_url)

        # Get all migration files and applied migrations
        all_migrations = get_ordered_migration_files()
        applied_migrations = get_applied_migrations(engine)

        print(f"📊 Found {len(all_migrations)} migration files")
        print(f"✅ {len(applied_migrations)} migrations already applied")

        # Determine which migrations to apply
        if args.migrations:
            # Apply only specified migrations
            to_apply = []
            for mig_name in args.migrations:
                for mig_file in all_migrations:
                    if mig_file.name == mig_name:
                        to_apply.append(mig_file)
                        break
            print(f"🎯 Applying {len(to_apply)} specified migrations")
        else:
            # Apply all missing migrations
            to_apply = [f for f in all_migrations if f.name not in applied_migrations]
            print(f"🔄 Applying {len(to_apply)} missing migrations")

        if not to_apply:
            print("✨ No migrations to apply - schema is up to date!")
            return 0

        # Show what will be applied
        print("\n📋 Migrations to apply:")
        for mig_file in to_apply:
            status = "🔄 MISSING" if mig_file.name not in applied_migrations else "✅ APPLIED"
            print(f"   {status}: {mig_file.name}")

        if args.dry_run:
            print("\n🔍 DRY RUN - No changes made")
            return 0

        # Confirm before applying
        if not args.dry_run:
            confirm = input(f"\n⚠️  Apply {len(to_apply)} migrations? (y/N): ").lower().strip()
            if confirm not in ("y", "yes"):
                print("❌ Aborted by user")
                return 1

        # Apply migrations
        print("\n🚀 Applying migrations...")
        for mig_file in to_apply:
            try:
                apply_migration_file(engine, mig_file)
            except Exception as e:
                print(f"❌ Failed to apply {mig_file.name}: {e}")
                return 1

        print("
🎉 All migrations applied successfully!"        print("🔍 Verifying schema...")

        # Final verification
        final_applied = get_applied_migrations(engine)
        print(f"✅ {len(final_applied)} migrations now applied")

        # Check for critical missing migrations
        critical_migrations = {
            '012_recommendation_probabilities.sql': 'pick_price column',
            '021_schema_migrations_table.sql': 'migration tracking'
        }

        missing_critical = []
        for mig, desc in critical_migrations.items():
            if mig not in final_applied:
                missing_critical.append(f"{mig} ({desc})")

        if missing_critical:
            print("
⚠️  WARNING: Critical migrations still missing:"            for mig in missing_critical:
                print(f"   ❌ {mig}")
            return 1
        else:
            print("✅ All critical migrations applied")
            return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())