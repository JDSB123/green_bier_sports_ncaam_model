#!/usr/bin/env python3
"""
GitHub Secret Sync Script

Fetches all repository secrets via GitHub CLI and writes them to a .env file for local/dev or Codespaces use.

Requirements:
- gh CLI (https://cli.github.com/) must be installed and authenticated (gh auth login)
- User must have access to the repository's secrets

Usage:
    python scripts/dev/gh_secret_sync.py [--output .env]
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = "JDSB123/green_bier_sports_ncaam_model"
DEFAULT_OUTPUT = ".env"

def fetch_github_secrets(repo):
    """Fetch all secrets for the given repo using gh CLI."""
    try:
        result = subprocess.run([
            "gh", "api", f"repos/{repo}/actions/secrets",
            "--jq", ".secrets[] | {name: .name, value: null}"
        ], capture_output=True, text=True, check=True)
        secrets = [json.loads(line) for line in result.stdout.strip().splitlines() if line.strip()]
        return [s["name"] for s in secrets]
    except Exception as e:
        print(f"Error fetching secrets: {e}")
        sys.exit(1)

def fetch_secret_value(repo, name):
    """Fetch the value of a secret (requires user input)."""
    # GitHub does not allow reading secret values via API for security reasons
    # Prompt user to enter the value for each secret
    value = os.environ.get(name)
    if value:
        return value
    try:
        return input(f"Enter value for secret {name}: ")
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)

def write_env_file(secrets, repo, output_file):
    """Write all secrets to the output .env file."""
    with Path(output_file).open("w", encoding="utf-8") as f:
        f.write(f"# Synced from GitHub secrets for {repo}\n")
        for name in secrets:
            value = fetch_secret_value(repo, name)
            f.write(f"{name}={value}\n")
    print(f"✓ Wrote {len(secrets)} secrets to {output_file}")

def main():
    output_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUTPUT
    secrets = fetch_github_secrets(REPO)
    if not secrets:
        print("No secrets found.")
        sys.exit(1)
    print(f"Found {len(secrets)} secrets in {REPO}.")
    write_env_file(secrets, REPO, output_file)

if __name__ == "__main__":
    main()
