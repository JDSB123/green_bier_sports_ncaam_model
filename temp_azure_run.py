#!/usr/bin/env python3
"""Temporary wrapper for Azure container - uses environment variables"""
import os
import sys

# Override secret reading to use environment variables
def _read_secret_file(file_path: str, secret_name: str) -> str:
    """Read from environment variable first, then try file."""
    env_var = secret_name.upper().replace("-", "_")
    value = os.getenv(env_var)
    if value:
        return value
    
    # Try common env var names
    if "db_password" in file_path:
        value = os.getenv("DB_PASSWORD")
        if value:
            return value
    elif "redis_password" in file_path:
        value = os.getenv("REDIS_PASSWORD")
        if value:
            return value
    elif "odds_api_key" in file_path:
        value = os.getenv("THE_ODDS_API_KEY")
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
sys.path.insert(0, '/app')
import run_today
run_today._read_secret_file = _read_secret_file

# Now run the main function
if __name__ == "__main__":
    # Set environment variables from Azure container env
    # These should already be set, but ensure they're available
    if not os.getenv("DATABASE_URL"):
        db_password = os.getenv("DB_PASSWORD")
        if db_password:
            # Extract host from DATABASE_URL if it exists, or use default
            db_host = os.getenv("DB_HOST", "ncaam-postgres")
            db_url = f"postgresql://ncaam:{db_password}@{db_host}:5432/ncaam"
            os.environ["DATABASE_URL"] = db_url
    
    # Run the main function
    run_today.main()
