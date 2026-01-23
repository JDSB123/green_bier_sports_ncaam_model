#!/usr/bin/env python3
"""
Universal Environment & Credentials Manager
Ensures all environment variables, credentials, and access tokens are always available
Works across different environments (codespaces, local, CI/CD, etc.)

Usage:
    python scripts/codespaces/ensure_all_access.py                    # Check all systems
    python scripts/codespaces/ensure_all_access.py --fix              # Auto-fix issues
    python scripts/codespaces/ensure_all_access.py --keys             # Show all required keys
    python scripts/codespaces/ensure_all_access.py --status           # Detailed status report
"""

import json
import os
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

PROJECT_ROOT = Path("/workspaces/green_bier_sports_ncaam_model")
ENV_FILES = {
    "local": PROJECT_ROOT / ".env.local",
    "staging": PROJECT_ROOT / ".env.staging",
    "production": PROJECT_ROOT / ".env.production",
}

# Color codes
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
NC = "\033[0m"


class EnvironmentType(Enum):
    """Supported environments"""

    CODESPACES = "codespaces"
    LOCAL = "local"
    CI_CD = "ci-cd"
    PRODUCTION = "production"


@dataclass
class RequiredVar:
    """Represents a required environment variable"""

    name: str
    required: bool = True
    sensitive: bool = False  # If True, don't show value in logs
    description: str = ""
    fallback: str | None = None
    validator: callable | None = None  # Function to validate value


# Define all required environment variables
REQUIRED_VARS = {
    # ===== DATABASE =====
    "DATABASE_URL": RequiredVar(
        "DATABASE_URL",
        required=True,
        description="PostgreSQL connection string",
        fallback="postgresql://postgres:postgres@localhost:5432/ncaam_local",
    ),
    "REDIS_URL": RequiredVar(
        "REDIS_URL",
        required=True,
        description="Redis connection string",
        fallback="redis://localhost:6379/0",
    ),
    # ===== API KEYS (SENSITIVE) =====
    "ODDS_API_KEY": RequiredVar(
        "ODDS_API_KEY",
        required=True,
        sensitive=True,
        description="The Odds API key (get from https://the-odds-api.com/api-keys)",
    ),
    # ===== AZURE CREDENTIALS =====
    "AZURE_SUBSCRIPTION_ID": RequiredVar(
        "AZURE_SUBSCRIPTION_ID",
        required=False,
        sensitive=True,
        description="Azure subscription ID",
    ),
    "AZURE_RESOURCE_GROUP": RequiredVar(
        "AZURE_RESOURCE_GROUP",
        required=False,
        description="Azure resource group name",
    ),
    "AZURE_STORAGE_ACCOUNT": RequiredVar(
        "AZURE_STORAGE_ACCOUNT",
        required=False,
        description="Azure storage account name",
    ),
    "AZURE_STORAGE_KEY": RequiredVar(
        "AZURE_STORAGE_KEY",
        required=False,
        sensitive=True,
        description="Azure storage account key",
    ),
    "AZURE_COSMOS_DB_ENDPOINT": RequiredVar(
        "AZURE_COSMOS_DB_ENDPOINT",
        required=False,
        description="Cosmos DB endpoint URL",
    ),
    "AZURE_COSMOS_DB_KEY": RequiredVar(
        "AZURE_COSMOS_DB_KEY",
        required=False,
        sensitive=True,
        description="Cosmos DB primary key",
    ),
    # ===== GITHUB =====
    "GITHUB_TOKEN": RequiredVar(
        "GITHUB_TOKEN",
        required=False,
        sensitive=True,
        description="GitHub personal access token",
    ),
    # ===== WEBHOOKS =====
    "TEAMS_WEBHOOK_SECRET": RequiredVar(
        "TEAMS_WEBHOOK_SECRET",
        required=False,
        sensitive=True,
        description="Microsoft Teams webhook URL",
    ),
    # ===== APPLICATION =====
    "ENVIRONMENT": RequiredVar(
        "ENVIRONMENT",
        required=True,
        description="Environment name (codespaces, local, staging, production)",
        fallback="codespaces",
    ),
    "DEBUG": RequiredVar(
        "DEBUG",
        required=False,
        description="Debug mode (true/false)",
        fallback="true",
    ),
    "LOG_LEVEL": RequiredVar(
        "LOG_LEVEL",
        required=False,
        description="Log level (DEBUG, INFO, WARNING, ERROR)",
        fallback="DEBUG",
    ),
    "API_PORT": RequiredVar(
        "API_PORT",
        required=False,
        description="API server port",
        fallback="8000",
    ),
    "PYTHONUNBUFFERED": RequiredVar(
        "PYTHONUNBUFFERED",
        required=False,
        description="Python unbuffered output",
        fallback="1",
    ),
}


def print_success(msg: str) -> None:
    """Print success message."""
    print(f"{GREEN}✓{NC} {msg}")


def print_warning(msg: str) -> None:
    """Print warning message."""
    print(f"{YELLOW}⚠{NC} {msg}")


def print_error(msg: str) -> None:
    """Print error message."""
    print(f"{RED}✗{NC} {msg}")


def print_info(msg: str) -> None:
    """Print info message."""
    print(f"{BLUE}ℹ{NC} {msg}")


def print_section(title: str) -> None:
    """Print section header."""
    print(f"\n{BLUE}{'━' * 70}{NC}")
    print(f"{BLUE}{title}{NC}")
    print(f"{BLUE}{'━' * 70}{NC}")


def get_environment_type() -> EnvironmentType:
    """Detect which environment we're running in."""
    if os.getenv("CODESPACES"):
        return EnvironmentType.CODESPACES
    if os.getenv("CI"):
        return EnvironmentType.CI_CD
    if os.getenv("ENVIRONMENT") == "production":
        return EnvironmentType.PRODUCTION
    return EnvironmentType.LOCAL


def load_env_file(env_file: Path) -> dict[str, str]:
    """Load environment variables from a file."""
    env_vars = {}
    if not env_file.exists():
        return env_vars

    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" in line:
            key, value = line.split("=", 1)
            env_vars[key.strip()] = value.strip()

    return env_vars


def save_env_file(env_file: Path, env_vars: dict[str, str]) -> None:
    """Save environment variables to a file."""
    lines = [
        "# Auto-generated environment configuration",
        "# This file may be overwritten. Edit with caution.",
        "",
    ]

    for key, value in sorted(env_vars.items()):
        if key.startswith("#"):
            lines.append("")
            lines.append(value)
        else:
            lines.append(f"{key}={value}")

    env_file.write_text("\n".join(lines) + "\n")


def check_env_var(var_name: str, var_config: RequiredVar) -> tuple[bool, str]:
    """Check if an environment variable is properly set."""
    value = os.getenv(var_name)

    if not value:
        # Try to load from env files
        for env_file in ENV_FILES.values():
            env_vars = load_env_file(env_file)
            if var_name in env_vars:
                value = env_vars[var_name]
                break

    if not value:
        if var_config.fallback:
            return True, f"(using fallback: {var_config.fallback})"
        if var_config.required:
            return False, "MISSING (REQUIRED)"
        return True, "Not set (optional)"

    if var_config.sensitive:
        return True, f"{'*' * len(value)} (set)"

    return True, "✓ Set"


def check_all_env_vars() -> tuple[int, int]:
    """Check all environment variables. Returns (ok_count, missing_count)."""
    print_section("🔐 Environment Variables Status")

    ok_count = 0
    missing_count = 0

    for var_name, var_config in sorted(REQUIRED_VARS.items()):
        status, message = check_env_var(var_name, var_config)

        if status:
            print_success(f"{var_name}: {message}")
            ok_count += 1
        else:
            print_error(f"{var_name}: {message}")
            print_info(f"  → {var_config.description}")
            missing_count += 1

    return ok_count, missing_count


def check_azure_access() -> bool:
    """Check Azure CLI access and login status."""
    print_section("☁️  Azure Access Status")

    # Check if Azure CLI is installed
    result = subprocess.run(["az", "--version"], capture_output=True, text=True)
    if result.returncode != 0:
        print_warning("Azure CLI not installed")
        return False

    print_success(f"Azure CLI installed: {result.stdout.splitlines()[0]}")

    # Check if logged in
    result = subprocess.run(["az", "account", "show"], capture_output=True, text=True)
    if result.returncode == 0:
        account = json.loads(result.stdout)
        print_success(f"Azure logged in as: {account.get('user', {}).get('name', 'Unknown')}")
        print_success(f"Subscription: {account.get('name', 'Unknown')}")
        return True
    print_warning("Azure CLI not logged in")
    print_info("Run: az login")
    return False


def check_github_access() -> bool:
    """Check GitHub CLI access and login status."""
    print_section("🐙 GitHub Access Status")

    # Check if GitHub CLI is installed
    result = subprocess.run(["gh", "--version"], capture_output=True, text=True)
    if result.returncode != 0:
        print_warning("GitHub CLI not installed")
        return False

    print_success(f"GitHub CLI installed: {result.stdout.splitlines()[0]}")

    # Check if logged in
    result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if result.returncode == 0:
        print_success("GitHub CLI logged in")
        return True
    print_warning("GitHub CLI not logged in")
    print_info("Run: gh auth login")
    return False


def check_vscode_extensions() -> tuple[int, int]:
    """Check VS Code extensions. Returns (installed_count, missing_count)."""
    print_section("🧩 VS Code Extensions Status")

    required_extensions = [
        "charliermarsh.ruff",
        "ms-python.python",
        "ms-python.vscode-pylance",
        "ms-azuretools.vscode-docker",
        "ms-azuretools.vscode-bicep",
        "ms-vscode.azure-account",
        "ms-vscode.azurecli",
        "ms-azuretools.vscode-cosmosdb",
        "golang.go",
        "rust-lang.rust-analyzer",
        "ckolkman.vscode-postgres",
        "redhat.vscode-yaml",
        "github.vscode-github-actions",
        "editorconfig.editorconfig",
        "mikestead.dotenv",
    ]

    # Check if VS Code command is available
    result = subprocess.run(["code", "--list-extensions"], capture_output=True, text=True)
    if result.returncode != 0:
        print_warning("VS Code CLI not available (expected in remote environments)")
        return 0, 0

    installed = set(result.stdout.strip().split("\n"))
    installed_count = 0
    missing_count = 0

    for ext in required_extensions:
        if ext in installed:
            print_success(f"{ext}")
            installed_count += 1
        else:
            print_warning(f"{ext} (not installed)")
            missing_count += 1

    return installed_count, missing_count


def check_ssh_keys() -> bool:
    """Check SSH key availability."""
    print_section("🔑 SSH Keys Status")

    ssh_dir = Path.home() / ".ssh"

    if not ssh_dir.exists():
        print_warning("~/.ssh directory not found")
        return False

    keys = list(ssh_dir.glob("id_*")) + list(ssh_dir.glob("*.pem"))

    if keys:
        print_success(f"SSH keys found ({len(keys)} files)")
        for key in keys[:5]:  # Show first 5
            print_info(f"  - {key.name}")
        return True
    print_warning("No SSH keys found")
    return False


def check_git_config() -> bool:
    """Check Git configuration."""
    print_section("🔧 Git Configuration")

    result = subprocess.run(
        ["git", "config", "--global", "user.name"], capture_output=True, text=True
    )
    if result.returncode == 0:
        print_success(f"Git user: {result.stdout.strip()}")
    else:
        print_warning("Git user not configured")
        return False

    result = subprocess.run(
        ["git", "config", "--global", "user.email"], capture_output=True, text=True
    )
    if result.returncode == 0:
        print_success(f"Git email: {result.stdout.strip()}")
    else:
        print_warning("Git email not configured")
        return False

    return True


def auto_fix_env_vars() -> None:
    """Attempt to auto-fix missing environment variables."""
    print_section("🔧 Auto-Fixing Environment Variables")

    env_file = ENV_FILES["local"]
    env_vars = load_env_file(env_file)

    for var_name, var_config in REQUIRED_VARS.items():
        if not os.getenv(var_name) and var_name not in env_vars:
            if var_config.fallback:
                print_success(f"Adding {var_name} with fallback value")
                env_vars[var_name] = var_config.fallback
            elif not var_config.required and not var_config.sensitive:
                print_info(f"Skipping optional variable {var_name}")

    save_env_file(env_file, env_vars)
    print_success(f"Environment file updated: {env_file}")


def show_required_keys() -> None:
    """Show all required keys and where to get them."""
    print_section("🔑 Required API Keys & Credentials")

    keys_info = {
        "ODDS_API_KEY": {
            "url": "https://the-odds-api.com/api-keys",
            "description": "Sports odds data API",
            "free_tier": True,
            "instructions": "Sign up → Get free API key → Add to .env.local",
        },
        "GITHUB_TOKEN": {
            "url": "https://github.com/settings/tokens",
            "description": "GitHub API access",
            "free_tier": True,
            "instructions": "Create personal access token → Copy to .env.local",
        },
        "AZURE_SUBSCRIPTION_ID": {
            "url": "https://portal.azure.com",
            "description": "Azure subscription identifier",
            "free_tier": False,
            "instructions": "Get from Azure portal → Add to .env.local",
        },
    }

    for key_name, key_info in keys_info.items():
        print(f"\n{BLUE}{key_name}{NC}")
        print(f"  Description: {key_info['description']}")
        print(f"  Get from: {key_info['url']}")
        print(f"  Free tier: {'Yes' if key_info['free_tier'] else 'No'}")
        print(f"  Steps: {key_info['instructions']}")


def generate_status_report() -> None:
    """Generate detailed status report."""
    print(f"\n{BLUE}{'╔' + '═' * 68 + '╗'}{NC}")
    print(f"{BLUE}║{NC}{'COMPREHENSIVE ACCESS & ENVIRONMENT STATUS REPORT':^68}{BLUE}║{NC}")
    print(f"{BLUE}{'╚' + '═' * 68 + '╝'}{NC}\n")

    environment = get_environment_type()
    print(f"Current Environment: {BLUE}{environment.value}{NC}")
    print(f"Project Root: {PROJECT_ROOT}")
    print()

    # Check all systems
    ok_vars, missing_vars = check_all_env_vars()
    check_azure_access()
    check_github_access()
    installed_exts, missing_exts = check_vscode_extensions()
    check_ssh_keys()
    check_git_config()

    # Summary
    print_section("📊 Summary")
    print(f"Environment Variables: {GREEN}{ok_vars} OK{NC}, {RED}{missing_vars} Missing{NC}")
    print(
        f"VS Code Extensions: {GREEN}{installed_exts} Installed{NC}, {YELLOW}{missing_exts} Missing{NC}"
    )

    if missing_vars > 0:
        print(f"\n{RED}⚠ Action Required:{NC}")
        print("  1. Check missing environment variables above")
        print("  2. Run: python ensure_all_access.py --keys")
        print("  3. Add credentials to .env.local")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Universal Environment & Credentials Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ensure_all_access.py              # Check all systems
  python ensure_all_access.py --fix        # Auto-fix issues
  python ensure_all_access.py --keys       # Show required keys
  python ensure_all_access.py --status     # Detailed report
        """,
    )
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues")
    parser.add_argument("--keys", action="store_true", help="Show required keys")
    parser.add_argument("--status", action="store_true", help="Detailed status report")

    args = parser.parse_args()

    if args.keys:
        show_required_keys()
    elif args.status:
        generate_status_report()
    elif args.fix:
        auto_fix_env_vars()
        generate_status_report()
    else:
        generate_status_report()


if __name__ == "__main__":
    main()
