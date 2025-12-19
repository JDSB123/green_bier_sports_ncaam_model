#!/usr/bin/env python3
"""
Ensure required secrets exist in secrets/ directory.
Generates secure random passwords for db/redis if missing.
API key must be provided manually - NO fallbacks.
This prevents container startup failures due to missing mounted secrets.
"""

import os
import sys
import io
import secrets
from pathlib import Path

# Force UTF-8 output for Windows consoles
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Define the secrets directory
PROJECT_ROOT = Path(__file__).parent.absolute()
SECRETS_DIR = PROJECT_ROOT / "secrets"

# Required secrets and their corresponding .env keys
REQUIRED_SECRETS = {
    "db_password.txt": "DB_PASSWORD",
    "redis_password.txt": "REDIS_PASSWORD",
    "odds_api_key.txt": "THE_ODDS_API_KEY",
}

def ensure_secrets_dir():
    if not SECRETS_DIR.exists():
        print(f"📁 Creating secrets directory: {SECRETS_DIR}")
        SECRETS_DIR.mkdir(parents=True, exist_ok=True)

def generate_secure_password(length=24):
    return secrets.token_hex(length // 2)

def main():
    # NO .env file loading - all secrets must be in secrets/ directory
    
    ensure_secrets_dir()
    
    changes_made = False
    
    print("🔐 Verifying secrets configuration...")
    print("   (All secrets must be in secrets/ directory - NO .env fallbacks)")
    
    for filename, env_var in REQUIRED_SECRETS.items():
        file_path = SECRETS_DIR / filename
        
        # Check if file exists
        if file_path.exists():
            # Verify it's not empty
            with open(file_path, 'r') as f:
                content = f.read().strip()
                if content:
                    continue
                else:
                    print(f"⚠️  Secret file {filename} exists but is empty")
        
        print(f"⚠️  Missing secret file: {filename}")
        
        if "api_key" in filename:
            print(f"   ❌ CRITICAL: {filename} is required but missing.")
            print(f"      Please create {file_path} manually with your API key.")
            print(f"      This file is REQUIRED - container will fail without it.")
            sys.exit(1)
        else:
            print(f"   ✓ Generating new secure random value for {filename}...")
            content = generate_secure_password()
                
        # Write the file
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            changes_made = True
            print(f"   ✓ Created {filename}")
        except Exception as e:
            print(f"   ❌ Failed to write {filename}: {e}")
            sys.exit(1)
    
    if changes_made:
        print("\n✅ Secrets generated successfully.")
        print("   NOTE: odds_api_key.txt must be created manually with your API key.")
    else:
        print("\n✅ All secrets verified.")

if __name__ == "__main__":
    main()
