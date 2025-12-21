#!/usr/bin/env python3
"""
NCAA Model - Secret File Setup Script

Creates required secret files with secure random values for Docker Compose deployment.
Run this ONCE before first `docker compose up`.

Usage:
    python ensure_secrets.py

Creates:
    secrets/db_password.txt     - PostgreSQL password (32 hex chars)
    secrets/redis_password.txt  - Redis password (32 hex chars)

NOTE: You must manually create secrets/odds_api_key.txt with your The Odds API key.
"""

import os
import secrets
from pathlib import Path


def generate_secure_password(length: int = 32) -> str:
    """Generate a cryptographically secure hex password."""
    return secrets.token_hex(length // 2)


def create_secret_file(filepath: Path, value: str, description: str) -> bool:
    """Create a secret file if it doesn't exist."""
    if filepath.exists():
        print(f"  [SKIP] {filepath.name} already exists")
        return False

    filepath.write_text(value)
    filepath.chmod(0o600)  # Owner read/write only
    print(f"  [CREATE] {filepath.name} - {description}")
    return True


def main():
    print("NCAA Model - Secret File Setup")
    print("=" * 50)
    print()

    # Ensure secrets directory exists
    secrets_dir = Path(__file__).parent / "secrets"
    secrets_dir.mkdir(exist_ok=True)
    print(f"Secrets directory: {secrets_dir}")
    print()

    # Track what was created
    created = []
    skipped = []

    # Create db_password.txt
    db_password_file = secrets_dir / "db_password.txt"
    if create_secret_file(db_password_file, generate_secure_password(32), "PostgreSQL password"):
        created.append("db_password.txt")
    else:
        skipped.append("db_password.txt")

    # Create redis_password.txt
    redis_password_file = secrets_dir / "redis_password.txt"
    if create_secret_file(redis_password_file, generate_secure_password(32), "Redis password"):
        created.append("redis_password.txt")
    else:
        skipped.append("redis_password.txt")

    # Check for odds_api_key.txt
    odds_api_key_file = secrets_dir / "odds_api_key.txt"
    if not odds_api_key_file.exists():
        print(f"  [MISSING] odds_api_key.txt - YOU MUST CREATE THIS MANUALLY")
        print()
        print("  To create odds_api_key.txt:")
        print("    1. Get your API key from https://the-odds-api.com/")
        print("    2. Create the file: secrets/odds_api_key.txt")
        print("    3. Paste your API key (just the key, no quotes)")
        print()
    else:
        print(f"  [OK] odds_api_key.txt exists")

    print()
    print("=" * 50)
    print("Summary:")
    if created:
        print(f"  Created: {', '.join(created)}")
    if skipped:
        print(f"  Skipped (already exist): {', '.join(skipped)}")

    if not odds_api_key_file.exists():
        print()
        print("ACTION REQUIRED: Create secrets/odds_api_key.txt with your API key!")
        return 1

    print()
    print("All secrets configured. Ready to run: docker compose up -d")
    return 0


if __name__ == "__main__":
    exit(main())
