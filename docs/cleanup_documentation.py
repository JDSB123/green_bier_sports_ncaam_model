#!/usr/bin/env python3
"""
DOCUMENTATION CLEANUP WITH AUDIT TRAIL

Deletes stale/conflicting/redundant documents and maintains
complete audit trail of what was deleted, when, and why.

All deletions are logged to DOCUMENTATION_DELETION_AUDIT.json
which serves as the definitive record of documentation changes.
"""

import argparse
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs"
AUDIT_FILE = ROOT / "DOCUMENTATION_DELETION_AUDIT.json"

# DEFINITIVE DELETION LIST
# These are docs that will be deleted with full audit trail
DELETIONS = {
    "HIGH_PRIORITY": [
        {
            "file": "DATA_ENDPOINT_STATUS.md",
            "reason": "Superseded by DATA_SOURCES.md (single source of truth)",
            "severity": "high",
            "replacement": "DATA_SOURCES.md"
        },
        {
            "file": "ODDS_API_USAGE.md",
            "reason": "Superseded by DATA_SOURCES.md and INGESTION_ARCHITECTURE.md",
            "severity": "high",
            "replacement": "DATA_SOURCES.md + INGESTION_ARCHITECTURE.md"
        },
        {
            "file": "HISTORICAL_DATA_GAPS.md",
            "reason": "Superseded by HISTORICAL_DATA_AVAILABILITY.md",
            "severity": "high",
            "replacement": "HISTORICAL_DATA_AVAILABILITY.md"
        },
        {
            "file": "HISTORICAL_DATA_SYNC.md",
            "reason": "Superseded by HISTORICAL_DATA_AVAILABILITY.md and INGESTION_ARCHITECTURE.md",
            "severity": "high",
            "replacement": "HISTORICAL_DATA_AVAILABILITY.md + INGESTION_ARCHITECTURE.md"
        },
        {
            "file": "MODEL_IMPROVEMENT_ANALYSIS.md",
            "reason": "One-off analysis document; use MODEL_IMPROVEMENT_ROADMAP.md for forward planning",
            "severity": "high",
            "replacement": "MODEL_IMPROVEMENT_ROADMAP.md"
        },
        {
            "file": "DEPLOYMENT_STATUS_v34.1.0.md",
            "reason": "Version-specific status document (outdated); use PRODUCTION_RUNBOOK.md",
            "severity": "high",
            "replacement": "PRODUCTION_RUNBOOK.md"
        },
    ],
    "REVIEW_REQUIRED": [
        {
            "file": "AZURE_BLOB_STORAGE_ARCHITECTURE.md",
            "reason": "Check if superseded by SINGLE_SOURCE_OF_TRUTH.md before deleting",
            "severity": "medium",
            "replacement": "SINGLE_SOURCE_OF_TRUTH.md"
        },
        {
            "file": "AZURE_RESOURCE_CLEANUP.md",
            "reason": "One-off resource cleanup - verify not needed before deletion",
            "severity": "medium",
            "replacement": "None (archive if needed)"
        },
        {
            "file": "EARLY_SEASON_BETTING_GUIDANCE.md",
            "reason": "2024 specific - verify not needed for current season",
            "severity": "medium",
            "replacement": "None (archive if needed)"
        },
        {
            "file": "FILES_SUMMARY.md",
            "reason": "Directory listing becomes stale - verify no external references",
            "severity": "medium",
            "replacement": "Current file tree in README"
        },
    ]
}

# AUTHORITATIVE DOCS TO KEEP (reference)
KEEP_DOCS = [
    "DATA_SOURCES.md",
    "INGESTION_ARCHITECTURE.md",
    "SINGLE_SOURCE_OF_TRUTH.md",
    "HISTORICAL_DATA_AVAILABILITY.md",
    "TEAM_NAME_CONVENTIONS.md",
    "PRODUCTION_RUNBOOK.md",
    "DEVELOPMENT_WORKFLOW.md",
    "MODEL_IMPROVEMENT_ROADMAP.md",
    "STANDARDIZED_TEAM_MAPPINGS.md",
    "BACKTESTING_METHODOLOGY.md",
    "NAMING_STANDARDS.md",
]


class DocumentationCleaner:
    """Clean documentation with full audit trail."""
    
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.deletion_log = {
            "timestamp": datetime.now().isoformat(),
            "execution_mode": "dry-run" if dry_run else "execute",
            "high_priority_deletions": [],
            "reviewed_deletions": [],
            "kept_documents": KEEP_DOCS,
        }
    
    def print_header(self, title):
        """Print formatted header."""
        print(f"\n{'='*80}")
        print(f"  {title}")
        print('='*80)
    
    def execute_high_priority_deletions(self):
        """Execute HIGH priority deletions (no user input needed)."""
        self.print_header("HIGH PRIORITY DELETIONS")
        
        for deletion in DELETIONS["HIGH_PRIORITY"]:
            file_path = DOCS_DIR / deletion["file"]
            
            if not file_path.exists():
                print(f"  ✗ NOT FOUND: {deletion['file']} (skipping)")
                continue
            
            print(f"\n  {deletion['file']}")
            print(f"    Reason: {deletion['reason']}")
            print(f"    Replacement: {deletion['replacement']}")
            
            if self.dry_run:
                print(f"    [DRY-RUN] Would delete")
            else:
                file_path.unlink()
                print(f"    ✓ DELETED")
                self.deletion_log["high_priority_deletions"].append({
                    "file": deletion["file"],
                    "deleted_at": datetime.now().isoformat(),
                    **deletion
                })
    
    def review_medium_priority(self):
        """Show MEDIUM priority deletions for review."""
        self.print_header("MEDIUM PRIORITY - REQUIRES REVIEW")
        
        for review in DELETIONS["REVIEW_REQUIRED"]:
            file_path = DOCS_DIR / review["file"]
            
            print(f"\n  {review['file']}")
            print(f"    Status: {review['reason']}")
            print(f"    Replacement: {review['replacement']}")
            
            if file_path.exists():
                print(f"    Action: ⚠️  MANUAL REVIEW NEEDED")
                self.deletion_log["reviewed_deletions"].append({
                    "file": review["file"],
                    "status": "pending_review",
                    **review
                })
            else:
                print(f"    Status: Already deleted")
    
    def verify_authoritative_docs(self):
        """Verify all authoritative docs exist."""
        self.print_header("VERIFYING AUTHORITATIVE DOCUMENTS")
        
        missing = []
        for doc in KEEP_DOCS:
            doc_path = DOCS_DIR / doc
            if not doc_path.exists():
                print(f"  ✗ MISSING: {doc}")
                missing.append(doc)
            else:
                print(f"  ✓ {doc}")
        
        if missing:
            print(f"\n  ⚠️  {len(missing)} authoritative docs are MISSING")
            return False
        else:
            print(f"\n  ✅ All {len(KEEP_DOCS)} authoritative docs present")
            return True
    
    def save_audit_trail(self):
        """Save deletion audit trail to JSON."""
        audit_path = ROOT / "DOCUMENTATION_DELETION_AUDIT.json"
        
        # Load existing audit or create new
        if audit_path.exists():
            with open(audit_path, 'r') as f:
                existing = json.load(f)
                if isinstance(existing, list):
                    existing.append(self.deletion_log)
                    audit = existing
                else:
                    audit = [existing, self.deletion_log]
        else:
            audit = [self.deletion_log]
        
        # Write audit trail
        with open(audit_path, 'w') as f:
            json.dump(audit, f, indent=2)
        
        print(f"\n✓ Audit trail saved to: {audit_path}")
    
    def run(self):
        """Execute documentation cleanup."""
        self.print_header("DOCUMENTATION CLEANUP")
        print(f"Mode: {'DRY-RUN (no changes)' if self.dry_run else 'EXECUTING (real cleanup)'}")
        
        # Verify authoritative docs first
        if not self.verify_authoritative_docs():
            print("\n❌ CRITICAL: Some authoritative docs are missing!")
            print("   Run without --execute until all are present")
            return False
        
        # Execute high priority deletions
        self.execute_high_priority_deletions()
        
        # Review medium priority
        self.review_medium_priority()
        
        # Save audit trail
        self.save_audit_trail()
        
        # Summary
        self.print_summary()
        
        return True
    
    def print_summary(self):
        """Print cleanup summary."""
        self.print_header("DOCUMENTATION CLEANUP SUMMARY")
        
        hp_count = len([d for d in DELETIONS["HIGH_PRIORITY"] 
                       if (DOCS_DIR / d["file"]).exists()])
        mp_count = len(DELETIONS["REVIEW_REQUIRED"])
        
        print(f"\n  High Priority Deletions: {hp_count}")
        print(f"  Medium Priority Reviews: {mp_count}")
        print(f"  Authoritative Docs:      {len(KEEP_DOCS)}")
        
        if not self.dry_run:
            print(f"\n  ✅ Deletions executed and logged")
        else:
            print(f"\n  To execute: python docs/cleanup_documentation.py --execute")
        
        print(f"\n  Audit trail: DOCUMENTATION_DELETION_AUDIT.json")


def main():
    parser = argparse.ArgumentParser(description="Documentation cleanup with audit trail")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview what will be deleted (default)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete files (careful!)"
    )
    
    args = parser.parse_args()
    
    if args.execute and args.dry_run:
        args.dry_run = False
    
    cleaner = DocumentationCleaner(dry_run=args.dry_run)
    cleaner.run()


if __name__ == "__main__":
    main()
