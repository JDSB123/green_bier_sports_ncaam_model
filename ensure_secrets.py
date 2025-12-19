#!/usr/bin/env python3
"""
Ensure required secrets exist in secrets/ directory.
Syncs from .env if available, otherwise generates defaults.
This prevents container startup failures due to missing mounted secrets.
"""

import os
import sys
import io
import secrets
from pathlib import Path
from dotenv import load_dotenv

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
    # Load .env file
    load_dotenv(PROJECT_ROOT / ".env")
    
    ensure_secrets_dir()
    
    changes_made = False
    
    print("🔐 Verifying secrets configuration...")
    
    for filename, env_var in REQUIRED_SECRETS.items():
        file_path = SECRETS_DIR / filename
        
        # Check if file exists
        if file_path.exists():
            # Optional: verify content matches .env if strictly desired, 
            # but for now just existence is enough to satisfy docker mounts.
            continue
            
        print(f"⚠️  Missing secret file: {filename}")
        
        # Try to get from environment
        env_value = os.getenv(env_var)
        
        if env_value:
            print(f"   ✓ Found {env_var} in .env, restoring file...")
            content = env_value
        else:
            if "api_key" in filename:
                print(f"   ❌ Missing {env_var} in .env - cannot auto-generate API key.")
                print(f"      Please create {filename} manually or set {env_var} in .env")
                continue
            else:
                print(f"   ✓ Generating new secure value for {filename}...")
                content = generate_secure_password()
                
        # Write the file
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            changes_made = True
        except Exception as e:
            print(f"   ❌ Failed to write {filename}: {e}")
            sys.exit(1)

    if changes_made:
        print("✅ Secrets restored successfully.")
    else:
        print("✅ All secrets verified.")

if __name__ == "__main__":
    main()
