#!/usr/bin/env python3
"""
Dynamic Port Allocation System for Green Bier Sport Ventures
============================================================

Provides automatic port sparsing to ensure no conflicts between:
- Multiple sports (NCAAM, NFL, NBA, MLB, etc.)
- Local development environments
- Azure Container Apps deployments

Features:
- Automatic port conflict detection
- Sport-specific port ranges
- Network subnet allocation
- Configuration file generation
"""

import os
import sys
import socket
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class SportAllocation:
    """Port and network allocation for a single sport."""
    sport: str
    postgres_port: int
    redis_port: int
    prediction_port: int
    backend_subnet: str
    data_subnet: str
    db_user: str
    db_name: str
    compose_project: str


# Base port ranges - each sport gets a unique offset
SPORT_OFFSETS: Dict[str, int] = {
    "ncaam": 0,
    "nfl": 1,
    "nba": 2,
    "mlb": 3,
    "nhl": 4,
    "soccer": 5,
    "wnba": 6,
    "cfb": 7,   # College Football
    "cbb": 8,   # College Basketball (alternative)
}

# Base ports (sport offset is added)
BASE_POSTGRES_PORT = 5450
BASE_REDIS_PORT = 6390
BASE_PREDICTION_PORT = 8092

# Network base (third octet increments per sport)
NETWORK_BASE = "10.5{sport_offset}"


def get_sport_allocation(sport: str) -> SportAllocation:
    """Generate allocation for a specific sport."""
    sport_lower = sport.lower()

    if sport_lower not in SPORT_OFFSETS:
        # Dynamic allocation for unknown sports
        # Use hash of sport name to generate consistent offset
        offset = abs(hash(sport_lower)) % 100 + 10  # 10-109 range for custom
    else:
        offset = SPORT_OFFSETS[sport_lower]

    return SportAllocation(
        sport=sport_lower,
        postgres_port=BASE_POSTGRES_PORT + offset,
        redis_port=BASE_REDIS_PORT + offset,
        prediction_port=BASE_PREDICTION_PORT + offset,
        backend_subnet=f"10.5{offset}.2.0/24",
        data_subnet=f"10.5{offset}.3.0/24",
        db_user=sport_lower,
        db_name=sport_lower,
        compose_project=f"{sport_lower}_v6_model"
    )


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is currently in use."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            return result == 0
    except Exception:
        return False


def check_docker_ports() -> Dict[int, str]:
    """Get all ports currently used by Docker containers."""
    used_ports = {}
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}:{{.Ports}}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if ":" in line and "->" in line:
                    parts = line.split(":")
                    container_name = parts[0]
                    # Parse port mappings like "0.0.0.0:5450->5432/tcp"
                    for port_map in line.split(","):
                        if "->" in port_map:
                            try:
                                host_port = int(port_map.split("->")[0].split(":")[-1])
                                used_ports[host_port] = container_name
                            except (ValueError, IndexError):
                                continue
    except Exception as e:
        print(f"Warning: Could not check Docker ports: {e}", file=sys.stderr)

    return used_ports


def find_available_port(base_port: int, max_attempts: int = 100) -> int:
    """Find an available port starting from base_port."""
    docker_ports = check_docker_ports()

    for offset in range(max_attempts):
        port = base_port + offset
        if port not in docker_ports and not is_port_in_use(port):
            return port

    raise RuntimeError(f"Could not find available port starting from {base_port}")


def validate_allocation(allocation: SportAllocation) -> Tuple[bool, List[str]]:
    """Validate that allocated ports are available."""
    issues = []
    docker_ports = check_docker_ports()

    # Check each port
    ports_to_check = [
        ("PostgreSQL", allocation.postgres_port),
        ("Redis", allocation.redis_port),
        ("Prediction API", allocation.prediction_port),
    ]

    for service, port in ports_to_check:
        if port in docker_ports:
            container = docker_ports[port]
            # Check if it's our own container
            if allocation.sport not in container.lower():
                issues.append(f"{service} port {port} in use by: {container}")
        elif is_port_in_use(port):
            issues.append(f"{service} port {port} in use by system process")

    return len(issues) == 0, issues


def generate_env_file(allocation: SportAllocation, output_path: Optional[Path] = None) -> str:
    """Generate .env file content for a sport allocation."""
    content = f"""# Green Bier Sport Ventures - {allocation.sport.upper()} Configuration
# Generated: {datetime.now().isoformat()}
# DO NOT COMMIT THIS FILE - Use .env.example as template

# Sport Identification
SPORT={allocation.sport}
COMPOSE_PROJECT_NAME={allocation.compose_project}

# Database Configuration
DB_USER={allocation.db_user}
DB_NAME={allocation.db_name}

# Port Allocation (automatically assigned to avoid conflicts)
POSTGRES_HOST_PORT={allocation.postgres_port}
REDIS_HOST_PORT={allocation.redis_port}
PREDICTION_HOST_PORT={allocation.prediction_port}

# Network Configuration
NETWORK_BACKEND_SUBNET={allocation.backend_subnet}
NETWORK_DATA_SUBNET={allocation.data_subnet}

# Secrets - LOAD FROM Docker secrets or Azure Key Vault
# THE_ODDS_API_KEY=<from secrets>
# DB_PASSWORD=<from secrets>
# REDIS_PASSWORD=<from secrets>
"""

    if output_path:
        output_path.write_text(content)
        print(f"Generated: {output_path}")

    return content


def generate_allocation_registry(sports: List[str], output_path: Optional[Path] = None) -> str:
    """Generate a complete allocation registry for multiple sports."""
    allocations = [get_sport_allocation(sport) for sport in sports]

    lines = [
        "# Green Bier Sport Ventures - Port Allocation Registry",
        f"# Generated: {datetime.now().isoformat()}",
        "#",
        "# This file documents port allocations to prevent conflicts.",
        "# Update this when adding new sports.",
        "",
        "## Allocated Ports",
        "",
        "| Sport | PostgreSQL | Redis | Prediction | Backend Subnet | Data Subnet |",
        "|-------|------------|-------|------------|----------------|-------------|",
    ]

    for alloc in allocations:
        lines.append(
            f"| {alloc.sport.upper()} | {alloc.postgres_port} | {alloc.redis_port} | "
            f"{alloc.prediction_port} | {alloc.backend_subnet} | {alloc.data_subnet} |"
        )

    lines.extend([
        "",
        "## Environment Variables",
        "",
    ])

    for alloc in allocations:
        lines.extend([
            f"### {alloc.sport.upper()}",
            "```bash",
            f"export SPORT={alloc.sport}",
            f"export COMPOSE_PROJECT_NAME={alloc.compose_project}",
            f"export POSTGRES_HOST_PORT={alloc.postgres_port}",
            f"export REDIS_HOST_PORT={alloc.redis_port}",
            f"export PREDICTION_HOST_PORT={alloc.prediction_port}",
            f"export NETWORK_BACKEND_SUBNET={alloc.backend_subnet}",
            f"export NETWORK_DATA_SUBNET={alloc.data_subnet}",
            f"export DB_USER={alloc.db_user}",
            f"export DB_NAME={alloc.db_name}",
            "```",
            "",
        ])

    content = "\n".join(lines)

    if output_path:
        output_path.write_text(content)
        print(f"Generated: {output_path}")

    return content


def check_all_conflicts(sports: List[str]) -> Dict[str, List[str]]:
    """Check for conflicts across all sports."""
    conflicts = {}

    for sport in sports:
        allocation = get_sport_allocation(sport)
        valid, issues = validate_allocation(allocation)
        if not valid:
            conflicts[sport] = issues

    return conflicts


def auto_resolve_conflicts(sport: str) -> SportAllocation:
    """Automatically find available ports for a sport."""
    base_allocation = get_sport_allocation(sport)

    # Try to find available ports
    postgres_port = find_available_port(base_allocation.postgres_port)
    redis_port = find_available_port(base_allocation.redis_port)
    prediction_port = find_available_port(base_allocation.prediction_port)

    return SportAllocation(
        sport=base_allocation.sport,
        postgres_port=postgres_port,
        redis_port=redis_port,
        prediction_port=prediction_port,
        backend_subnet=base_allocation.backend_subnet,
        data_subnet=base_allocation.data_subnet,
        db_user=base_allocation.db_user,
        db_name=base_allocation.db_name,
        compose_project=base_allocation.compose_project
    )


def main():
    """CLI interface for port allocation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Dynamic Port Allocation for Green Bier Sport Ventures"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Allocate command
    alloc_parser = subparsers.add_parser("allocate", help="Get allocation for a sport")
    alloc_parser.add_argument("sport", help="Sport name (ncaam, nfl, nba, etc.)")
    alloc_parser.add_argument("--json", action="store_true", help="Output as JSON")
    alloc_parser.add_argument("--env", type=str, help="Generate .env file at path")
    alloc_parser.add_argument("--auto-resolve", action="store_true",
                              help="Auto-resolve port conflicts")

    # Check command
    check_parser = subparsers.add_parser("check", help="Check for port conflicts")
    check_parser.add_argument("--sports", nargs="+",
                              default=["ncaam", "nfl", "nba", "mlb"],
                              help="Sports to check")

    # Registry command
    reg_parser = subparsers.add_parser("registry", help="Generate allocation registry")
    reg_parser.add_argument("--sports", nargs="+",
                            default=["ncaam", "nfl", "nba", "mlb", "nhl"],
                            help="Sports to include")
    reg_parser.add_argument("--output", type=str, help="Output file path")

    # Status command
    subparsers.add_parser("status", help="Show current Docker port usage")

    args = parser.parse_args()

    if args.command == "allocate":
        if args.auto_resolve:
            allocation = auto_resolve_conflicts(args.sport)
        else:
            allocation = get_sport_allocation(args.sport)

        valid, issues = validate_allocation(allocation)

        if args.json:
            output = asdict(allocation)
            output["valid"] = valid
            output["issues"] = issues
            print(json.dumps(output, indent=2))
        elif args.env:
            generate_env_file(allocation, Path(args.env))
        else:
            print(f"\n{allocation.sport.upper()} Port Allocation:")
            print(f"  PostgreSQL:    {allocation.postgres_port}")
            print(f"  Redis:         {allocation.redis_port}")
            print(f"  Prediction:    {allocation.prediction_port}")
            print(f"  Backend Net:   {allocation.backend_subnet}")
            print(f"  Data Net:      {allocation.data_subnet}")
            print(f"  DB User/Name:  {allocation.db_user}/{allocation.db_name}")
            print(f"  Project Name:  {allocation.compose_project}")
            print()
            if valid:
                print("  Status: ✅ All ports available")
            else:
                print("  Status: ⚠️  Conflicts detected:")
                for issue in issues:
                    print(f"    - {issue}")

    elif args.command == "check":
        print("Checking port conflicts...")
        conflicts = check_all_conflicts(args.sports)

        if not conflicts:
            print("\n✅ No conflicts detected across all sports")
        else:
            print("\n⚠️  Conflicts detected:")
            for sport, issues in conflicts.items():
                print(f"\n  {sport.upper()}:")
                for issue in issues:
                    print(f"    - {issue}")

    elif args.command == "registry":
        output_path = Path(args.output) if args.output else None
        content = generate_allocation_registry(args.sports, output_path)
        if not output_path:
            print(content)

    elif args.command == "status":
        print("Current Docker port usage:")
        docker_ports = check_docker_ports()

        if not docker_ports:
            print("  No Docker containers with port mappings found")
        else:
            for port, container in sorted(docker_ports.items()):
                print(f"  Port {port}: {container}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
