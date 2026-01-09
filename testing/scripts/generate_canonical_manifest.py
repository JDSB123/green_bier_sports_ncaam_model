#!/usr/bin/env python3
"""
CANONICAL DATA VERSIONING & MANIFEST GENERATION

Creates versioned snapshots of canonical data with a manifest file that tracks:
- Source file hashes (SHA-256) for reproducibility
- Schema version for compatibility checking
- Canonicalization timestamp
- Row counts and coverage statistics
- Team resolver version

This ensures backtest reproducibility - you can always recreate the exact
dataset used for a specific backtest run.

Usage:
    # Generate manifest for current canonical data
    python testing/scripts/generate_canonical_manifest.py
    
    # Create versioned snapshot (copies files + manifest)
    python testing/scripts/generate_canonical_manifest.py --create-snapshot
    
    # Validate existing manifest matches current files
    python testing/scripts/generate_canonical_manifest.py --validate
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add project root
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "testing"))

from testing.data_paths import DATA_PATHS


# ============================================================================
# CONFIGURATION
# ============================================================================

SCHEMA_VERSION = "2.0.0"  # Increment when canonical file format changes

CANONICAL_FILES = {
    # Scores
    "scores_fg": "canonicalized/scores/fg/games_all_canonical.csv",
    "scores_h1": "canonicalized/scores/h1/h1_games_all_canonical.csv",
    # Odds - Spreads
    "odds_spreads_fg": "odds/canonical/spreads/fg/spreads_fg_all.csv",
    "odds_spreads_h1": "odds/canonical/spreads/h1/spreads_h1_all.csv",
    # Odds - Totals
    "odds_totals_fg": "odds/canonical/totals/fg/totals_fg_all.csv",
    "odds_totals_h1": "odds/canonical/totals/h1/totals_h1_all.csv",
    # Ratings
    "ratings_barttorvik": "ratings/canonical/barttorvik_all.csv",
    # Backtest datasets
    "backtest_training": "backtest_datasets/training_data_with_odds.csv",
    "backtest_h1": "backtest_datasets/h1_training_data.csv",
}

# Team aliases file (critical for reproducibility)
TEAM_ALIASES_FILE = ROOT_DIR / "testing" / "production_parity" / "team_aliases.json"


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class FileManifestEntry:
    """Manifest entry for a single file."""
    path: str
    sha256: str
    size_bytes: int
    row_count: int
    columns: List[str]
    last_modified: str


@dataclass
class CanonicalManifest:
    """Complete manifest for canonical data snapshot."""
    version: str
    schema_version: str
    created_at: str
    team_aliases_version: str
    team_aliases_sha256: str
    total_files: int
    total_rows: int
    files: Dict[str, FileManifestEntry] = field(default_factory=dict)
    coverage: Dict[str, any] = field(default_factory=dict)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_csv_info(file_path: Path) -> tuple:
    """Get row count and columns from CSV file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames or []
            row_count = sum(1 for _ in reader)
        return row_count, columns
    except Exception as e:
        print(f"  WARNING: Could not read {file_path}: {e}")
        return 0, []


def get_team_aliases_version() -> tuple:
    """Get version and hash of team aliases file."""
    if not TEAM_ALIASES_FILE.exists():
        return "unknown", "file_not_found"
    
    with open(TEAM_ALIASES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    version = data.get("version", "unknown")
    sha256 = compute_sha256(TEAM_ALIASES_FILE)
    
    return version, sha256


def generate_version_string() -> str:
    """Generate version string based on current date/time."""
    now = datetime.now()
    return now.strftime("%Y.%m.%d.%H%M")


# ============================================================================
# MANIFEST GENERATION
# ============================================================================

def generate_manifest(data_root: Path) -> CanonicalManifest:
    """Generate manifest for all canonical files."""
    print("Generating canonical data manifest...")
    print(f"  Data root: {data_root}")
    print()
    
    # Get team aliases info
    aliases_version, aliases_sha256 = get_team_aliases_version()
    print(f"  Team aliases version: {aliases_version}")
    
    manifest = CanonicalManifest(
        version=generate_version_string(),
        schema_version=SCHEMA_VERSION,
        created_at=datetime.now().isoformat(),
        team_aliases_version=aliases_version,
        team_aliases_sha256=aliases_sha256,
        total_files=0,
        total_rows=0,
    )
    
    # Process each canonical file
    for key, rel_path in CANONICAL_FILES.items():
        file_path = data_root / rel_path
        
        if not file_path.exists():
            print(f"  SKIP: {key} (file not found: {rel_path})")
            continue
        
        print(f"  Processing: {key}...")
        
        # Compute file info
        sha256 = compute_sha256(file_path)
        size_bytes = file_path.stat().st_size
        row_count, columns = get_csv_info(file_path)
        last_modified = datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
        
        entry = FileManifestEntry(
            path=rel_path,
            sha256=sha256,
            size_bytes=size_bytes,
            row_count=row_count,
            columns=columns,
            last_modified=last_modified,
        )
        
        manifest.files[key] = entry
        manifest.total_files += 1
        manifest.total_rows += row_count
        
        print(f"    SHA256: {sha256[:16]}...")
        print(f"    Rows: {row_count:,}")
    
    # Add coverage statistics
    manifest.coverage = compute_coverage_stats(manifest)
    
    print()
    print(f"Manifest generated: {manifest.total_files} files, {manifest.total_rows:,} total rows")
    
    return manifest


def compute_coverage_stats(manifest: CanonicalManifest) -> Dict[str, any]:
    """Compute coverage statistics from manifest."""
    stats = {
        "scores_fg_rows": 0,
        "scores_h1_rows": 0,
        "odds_fg_rows": 0,
        "odds_h1_rows": 0,
        "h1_score_coverage": 0.0,
        "h1_odds_coverage": 0.0,
    }
    
    if "scores_fg" in manifest.files:
        stats["scores_fg_rows"] = manifest.files["scores_fg"].row_count
    
    if "scores_h1" in manifest.files:
        stats["scores_h1_rows"] = manifest.files["scores_h1"].row_count
    
    if "odds_spreads_fg" in manifest.files:
        stats["odds_fg_rows"] = manifest.files["odds_spreads_fg"].row_count
    
    if "odds_spreads_h1" in manifest.files:
        stats["odds_h1_rows"] = manifest.files["odds_spreads_h1"].row_count
    
    # Compute coverage ratios
    if stats["scores_fg_rows"] > 0:
        stats["h1_score_coverage"] = stats["scores_h1_rows"] / stats["scores_fg_rows"]
    
    if stats["odds_fg_rows"] > 0:
        stats["h1_odds_coverage"] = stats["odds_h1_rows"] / stats["odds_fg_rows"]
    
    return stats


def save_manifest(manifest: CanonicalManifest, output_path: Path):
    """Save manifest to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to dict
    data = {
        "version": manifest.version,
        "schema_version": manifest.schema_version,
        "created_at": manifest.created_at,
        "team_aliases_version": manifest.team_aliases_version,
        "team_aliases_sha256": manifest.team_aliases_sha256,
        "total_files": manifest.total_files,
        "total_rows": manifest.total_rows,
        "coverage": manifest.coverage,
        "files": {},
    }
    
    for key, entry in manifest.files.items():
        data["files"][key] = {
            "path": entry.path,
            "sha256": entry.sha256,
            "size_bytes": entry.size_bytes,
            "row_count": entry.row_count,
            "columns": entry.columns,
            "last_modified": entry.last_modified,
        }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    print(f"Manifest saved to: {output_path}")


# ============================================================================
# SNAPSHOT CREATION
# ============================================================================

def create_snapshot(data_root: Path, manifest: CanonicalManifest) -> Path:
    """Create versioned snapshot of canonical data."""
    version = manifest.version
    snapshot_dir = data_root / "snapshots" / f"canonical_v{version}"
    
    print(f"\nCreating snapshot: {snapshot_dir}")
    
    if snapshot_dir.exists():
        print(f"  WARNING: Snapshot already exists, overwriting...")
        shutil.rmtree(snapshot_dir)
    
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy all canonical files
    for key, entry in manifest.files.items():
        src = data_root / entry.path
        if not src.exists():
            continue
        
        # Preserve directory structure
        dst = snapshot_dir / entry.path
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"  Copying: {key}")
        shutil.copy2(src, dst)
    
    # Save manifest in snapshot
    manifest_path = snapshot_dir / "manifest.json"
    save_manifest(manifest, manifest_path)
    
    # Also copy team aliases
    if TEAM_ALIASES_FILE.exists():
        aliases_dst = snapshot_dir / "team_aliases.json"
        shutil.copy2(TEAM_ALIASES_FILE, aliases_dst)
        print(f"  Copied: team_aliases.json")
    
    print(f"\nSnapshot created: {snapshot_dir}")
    return snapshot_dir


# ============================================================================
# VALIDATION
# ============================================================================

def load_manifest(manifest_path: Path) -> Optional[CanonicalManifest]:
    """Load manifest from JSON file."""
    if not manifest_path.exists():
        print(f"ERROR: Manifest not found: {manifest_path}")
        return None
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    manifest = CanonicalManifest(
        version=data["version"],
        schema_version=data["schema_version"],
        created_at=data["created_at"],
        team_aliases_version=data.get("team_aliases_version", "unknown"),
        team_aliases_sha256=data.get("team_aliases_sha256", ""),
        total_files=data["total_files"],
        total_rows=data["total_rows"],
        coverage=data.get("coverage", {}),
    )
    
    for key, entry_data in data["files"].items():
        manifest.files[key] = FileManifestEntry(**entry_data)
    
    return manifest


def validate_manifest(data_root: Path, manifest_path: Path) -> bool:
    """Validate that current files match manifest."""
    print("Validating canonical data against manifest...")
    
    manifest = load_manifest(manifest_path)
    if not manifest:
        return False
    
    print(f"  Manifest version: {manifest.version}")
    print(f"  Schema version: {manifest.schema_version}")
    print()
    
    all_valid = True
    
    for key, entry in manifest.files.items():
        file_path = data_root / entry.path
        
        if not file_path.exists():
            print(f"  ❌ {key}: FILE MISSING")
            all_valid = False
            continue
        
        # Verify hash
        current_sha256 = compute_sha256(file_path)
        
        if current_sha256 != entry.sha256:
            print(f"  ❌ {key}: HASH MISMATCH")
            print(f"      Expected: {entry.sha256[:16]}...")
            print(f"      Current:  {current_sha256[:16]}...")
            all_valid = False
        else:
            print(f"  ✅ {key}: OK")
    
    # Validate team aliases
    current_aliases_version, current_aliases_sha256 = get_team_aliases_version()
    if current_aliases_sha256 != manifest.team_aliases_sha256:
        print(f"  ⚠️  team_aliases.json: VERSION CHANGED")
        print(f"      Manifest: {manifest.team_aliases_version}")
        print(f"      Current:  {current_aliases_version}")
        # This is a warning, not a failure
    else:
        print(f"  ✅ team_aliases.json: OK")
    
    print()
    if all_valid:
        print("✅ VALIDATION PASSED: All files match manifest")
    else:
        print("❌ VALIDATION FAILED: Files have changed since manifest was created")
    
    return all_valid


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Generate canonical data manifest")
    parser.add_argument("--create-snapshot", action="store_true",
                        help="Create versioned snapshot with copied files")
    parser.add_argument("--validate", action="store_true",
                        help="Validate current files against existing manifest")
    parser.add_argument("--manifest", type=str, 
                        default="manifests/canonical_manifest.json",
                        help="Manifest file path (relative to data root)")
    parser.add_argument("--output", type=str,
                        help="Output manifest path (default: same as --manifest)")
    args = parser.parse_args()
    
    data_root = DATA_PATHS.root
    manifest_path = data_root / args.manifest
    
    if args.validate:
        success = validate_manifest(data_root, manifest_path)
        sys.exit(0 if success else 1)
    
    # Generate manifest
    manifest = generate_manifest(data_root)
    
    # Save manifest
    output_path = Path(args.output) if args.output else manifest_path
    if not output_path.is_absolute():
        output_path = data_root / output_path
    save_manifest(manifest, output_path)
    
    # Create snapshot if requested
    if args.create_snapshot:
        create_snapshot(data_root, manifest)
    
    print("\nDone - manifest generated successfully")


if __name__ == "__main__":
    main()
