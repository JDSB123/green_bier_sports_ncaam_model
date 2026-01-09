"""
Unified secrets management for all environments.

This module provides a single, consistent way to load secrets across:
- Local development (secrets/*.txt files)
- Docker (mounted at /run/secrets/)
- Azure (environment variables)

Usage:
    from secrets_manager import get_secret
    
    api_key = get_secret("THE_ODDS_API_KEY")  # Tries env var, then Docker, then local file
"""

import os
import sys
from pathlib import Path
from typing import Optional


def _get_repo_root() -> Path:
    """Get repository root directory."""
    return Path(__file__).parent.parent.parent


def get_secret(
    env_var_name: str,
    docker_secret_name: Optional[str] = None,
    local_file_name: Optional[str] = None,
    required: bool = True,
) -> str:
    """
    Load a secret from multiple sources with priority order.
    
    Priority (first found wins):
    1. Environment variable
    2. Docker secret file (/run/secrets/{docker_secret_name})
    3. Local secrets file (secrets/{local_file_name}.txt)
    
    Args:
        env_var_name: Environment variable name (e.g., "THE_ODDS_API_KEY")
        docker_secret_name: Docker secret name (defaults to env_var_name in lowercase)
        local_file_name: Local file name without .txt extension (defaults to env_var_name in lowercase)
        required: If True, raises error if secret not found; if False, returns empty string
    
    Returns:
        Secret value (stripped of whitespace)
    
    Raises:
        EnvironmentError: If required=True and secret not found anywhere
    """
    
    # Set defaults based on env_var_name
    docker_secret_name = docker_secret_name or env_var_name.lower()
    local_file_name = local_file_name or env_var_name.lower()
    
    # 1. Try environment variable first (highest priority - supports all platforms)
    value = os.environ.get(env_var_name)
    if value and value.strip():
        return value.strip()
    
    # 2. Try Docker secret file (mounted at /run/secrets/ in containers)
    docker_secret_path = Path(f"/run/secrets/{docker_secret_name}")
    if docker_secret_path.exists():
        try:
            value = docker_secret_path.read_text().strip()
            if value:
                return value
        except Exception as e:
            if required:
                raise EnvironmentError(
                    f"Failed to read Docker secret {docker_secret_path}: {e}"
                )
    
    # 3. Try local secrets file (for local development)
    repo_root = _get_repo_root()
    local_file_path = repo_root / "secrets" / f"{local_file_name}.txt"
    if local_file_path.exists():
        try:
            value = local_file_path.read_text().strip()
            if value:
                return value
        except Exception as e:
            if required:
                raise EnvironmentError(
                    f"Failed to read local secrets file {local_file_path}: {e}"
                )
    
    # 4. If nothing found and required=True, raise error with helpful message
    if required:
        raise EnvironmentError(
            f"\n\n❌ MISSING REQUIRED SECRET: {env_var_name}\n\n"
            f"Please set this secret using ONE of these methods:\n"
            f"\n1️⃣  ENVIRONMENT VARIABLE (recommended for all environments):\n"
            f"   set {env_var_name}=your_secret_value\n"
            f"\n2️⃣  DOCKER SECRET (for Docker containers):\n"
            f"   Mount at /run/secrets/{docker_secret_name}\n"
            f"\n3️⃣  LOCAL FILE (for local development):\n"
            f"   Create file: secrets/{local_file_name}.txt\n"
            f"   With content: your_secret_value\n\n"
        )
    
    return ""


# Convenience functions for common secrets
def get_api_key(api_name: str = "odds") -> str:
    """
    Get API key by name.
    
    Args:
        api_name: "odds", "basketball", or custom API name
    
    Returns:
        API key value
    
    Raises:
        EnvironmentError: If API key not found
    """
    api_configs = {
        "odds": {
            "env_var": "THE_ODDS_API_KEY",
            "docker": "odds_api_key",
            "local": "odds_api_key",
        },
        "basketball": {
            "env_var": "BASKETBALL_API_KEY",
            "docker": "basketball_api_key",
            "local": "basketball_api_key",
        },
    }
    
    if api_name not in api_configs:
        raise ValueError(f"Unknown API: {api_name}. Available: {list(api_configs.keys())}")
    
    config = api_configs[api_name]
    return get_secret(
        env_var_name=config["env_var"],
        docker_secret_name=config["docker"],
        local_file_name=config["local"],
    )


def get_db_password() -> str:
    """Get database password."""
    return get_secret(
        env_var_name="DB_PASSWORD",
        docker_secret_name="db_password",
        local_file_name="db_password",
    )


def get_redis_password() -> str:
    """Get Redis password."""
    return get_secret(
        env_var_name="REDIS_PASSWORD",
        docker_secret_name="redis_password",
        local_file_name="redis_password",
    )
