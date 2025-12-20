#!/usr/bin/env python3
"""
Azure wrapper for run_today.py - uses environment variables instead of Docker secrets
"""
import os
import sys

# Override secret reading to use environment variables
def _read_secret_file(file_path: str, secret_name: str) -> str:
    """Read from environment variable first, then try file."""
    env_var = secret_name.upper().replace("-", "_")
    value = os.getenv(env_var)
    if value:
        return value
    
    # Fallback to file if exists
    try:
        with open(file_path, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Secret not found: {file_path} or environment variable {env_var}"
        )

# Patch the secret reading function before importing run_today
import run_today
run_today._read_secret_file = _read_secret_file

# Now run the main function
if __name__ == "__main__":
    # Set environment variables from Azure container env
    # These should already be set, but ensure they're available
    if not os.getenv("DATABASE_URL"):
        db_password = os.getenv("DB_PASSWORD") or _read_secret_file("/run/secrets/db_password", "db_password")
        db_url = f"postgresql://ncaam:{db_password}@ncaam-postgres:5432/ncaam"
        os.environ["DATABASE_URL"] = db_url
    
    # Run the main function
    run_today.main()
