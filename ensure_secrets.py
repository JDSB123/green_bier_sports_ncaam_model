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
    secrets/teams_webhook_url.txt - (Optional) Microsoft Teams incoming webhook URL

NOTE: The Odds API key must be provided. Get it from https://the-odds-api.com/
      The script will prompt for it if secrets/odds_api_key.txt doesn't exist.
      
      Key storage locations:
      - Docker Compose: secrets/odds_api_key.txt → /run/secrets/odds_api_key
      - Azure: Environment variable THE_ODDS_API_KEY
"""

import os
import secrets
import sys
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
    try:
        filepath.chmod(0o600)  # Owner read/write only
    except Exception:
        pass # Windows might ignore this
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
        print(f"  [MISSING] odds_api_key.txt")
        print()
        print("  Please enter your The Odds API key (or press Enter to skip):")
        user_key = input("  > ").strip()
        
        if user_key:
            create_secret_file(odds_api_key_file, user_key, "Odds API Key")
            created.append("odds_api_key.txt")
        else:
            print("  [SKIPPED] No key entered.")
    else:
        # Validate content
        content = odds_api_key_file.read_text().strip()
        if not content or "change_me" in content.lower() or content.lower().startswith("sample"):
             print(f"  [WARNING] odds_api_key.txt exists but appears to be a placeholder!")
             print(f"            Current content: {content[:10]}...")
             print("  Do you want to overwrite it? (y/N)")
             if input("  > ").lower().startswith('y'):
                 print("  Enter new API key:")
                 user_key = input("  > ").strip()
                 if user_key:
                     odds_api_key_file.write_text(user_key)
                     print("  [UPDATED] odds_api_key.txt")
        else:
            print(f"  [OK] odds_api_key.txt exists")

    print()
    print("=" * 50)
    print("Summary:")
    if created:
        print(f"  Created: {', '.join(created)}")
    if skipped:
        print(f"  Skipped (already exist): {', '.join(skipped)}")

    # Final check
    has_file = odds_api_key_file.exists() and len(odds_api_key_file.read_text().strip()) > 10
    
    if not has_file:
        print()
        print("ACTION REQUIRED: You must create secrets/odds_api_key.txt")
        return 1

    # Optional: Teams webhook for posting picks (manual-only, user-triggered).
    # We create a placeholder file so local Docker Compose can mount it when configured,
    # without forcing Teams usage.
    teams_webhook_file = secrets_dir / "teams_webhook_url.txt"
    if not teams_webhook_file.exists():
        create_secret_file(teams_webhook_file, "CHANGE_ME", "Teams webhook URL (optional)")
        created.append("teams_webhook_url.txt")
        print("  [INFO] Teams webhook is optional. Update secrets/teams_webhook_url.txt to enable --teams.")
    else:
        content = teams_webhook_file.read_text().strip()
        if not content or "change_me" in content.lower() or "your_" in content.lower():
            print("  [INFO] teams_webhook_url.txt exists but is not configured (placeholder).")
        else:
            print("  [OK] teams_webhook_url.txt exists")

    # Optional: Teams webhook secret for validating outgoing webhook messages
    teams_webhook_secret_file = secrets_dir / "teams_webhook_secret.txt"
    if not teams_webhook_secret_file.exists():
        create_secret_file(teams_webhook_secret_file, generate_secure_password(32), "Teams webhook secret (optional)")
        created.append("teams_webhook_secret.txt")
        print("  [INFO] Teams webhook secret is optional. Used for validating outgoing webhook messages.")
    else:
        content = teams_webhook_secret_file.read_text().strip()
        if not content or "change_me" in content.lower():
            print("  [INFO] teams_webhook_secret.txt exists but is not configured (placeholder).")
        else:
            print("  [OK] teams_webhook_secret.txt exists")

    print()
    print("All secrets configured. Ready to run: docker compose up -d")
    return 0


if __name__ == "__main__":
    sys.exit(main())
