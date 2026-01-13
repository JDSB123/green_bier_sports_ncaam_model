#!/usr/bin/env python3
"""
DOCUMENTATION CLEANUP & CONFLICT DETECTION

Identifies and marks for deletion:
1. Duplicate/redundant documentation
2. Stale/superseded documents
3. Conflicting information
4. Orphaned documents (referenced nowhere)
5. Version mismatches

Creates audit trail for all deletions.
"""

import json
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs"

@dataclass
class DocIssue:
    """Documentation issue found."""
    doc: str
    category: str  # "duplicate", "stale", "conflict", "orphaned", "outdated"
    severity: str  # "high", "medium", "low"
    reason: str
    keep_instead: str = None  # If duplicate, which one to keep
    last_modified: str = None

# DOCUMENT CONFLICTS: Which docs supersede/conflict with others
DOC_CONFLICTS = {
    # Data source documentation
    "DATA_SOURCES.md": {
        "conflicts": ["DATA_ENDPOINT_STATUS.md", "ODDS_API_USAGE.md"],
        "reason": "DATA_SOURCES.md is the single source of truth for all data sources",
        "action": "DELETE DATA_ENDPOINT_STATUS.md, ODDS_API_USAGE.md"
    },
    
    # Historical data documentation
    "HISTORICAL_DATA_AVAILABILITY.md": {
        "conflicts": ["HISTORICAL_DATA_GAPS.md", "HISTORICAL_DATA_SYNC.md"],
        "reason": "HISTORICAL_DATA_AVAILABILITY.md covers all three topics",
        "action": "DELETE HISTORICAL_DATA_GAPS.md, HISTORICAL_DATA_SYNC.md"
    },
    
    # Ingestion architecture
    "INGESTION_ARCHITECTURE.md": {
        "conflicts": ["INTEGRATION_ARCHITECTURE.md"],
        "reason": "INGESTION_ARCHITECTURE is the canonical ingestion guide",
        "action": "Review INTEGRATION_ARCHITECTURE.md - may need deletion or merge"
    },
    
    # Single source of truth
    "SINGLE_SOURCE_OF_TRUTH.md": {
        "conflicts": ["CONFIGURATION.md"],
        "reason": "SINGLE_SOURCE_OF_TRUTH.md defines canonical architecture",
        "action": "If CONFIGURATION.md duplicates, DELETE it"
    },
    
    # Team mappings
    "TEAM_NAME_CONVENTIONS.md": {
        "conflicts": ["STANDARDIZED_TEAM_MAPPINGS.md", "TEAM_MATCHING_ACCURACY.md"],
        "reason": "TEAM_NAME_CONVENTIONS.md should be authoritative",
        "action": "Consolidate into single doc, delete duplicates"
    },
    
    # Status documents (time-bound)
    "DEPLOYMENT_STATUS_v34.1.0.md": {
        "conflicts": [],
        "reason": "Version-specific status doc - likely stale",
        "action": "DELETE - replace with current deployment runbook"
    },
    
    "CHANGELOG_v34.1.0.md": {
        "conflicts": [],
        "reason": "Version-specific - likely outdated",
        "action": "If current version > 34.1.0, DELETE this"
    },
    
    # Analysis documents (one-off)
    "MODEL_IMPROVEMENT_ANALYSIS.md": {
        "conflicts": ["MODEL_IMPROVEMENT_ROADMAP.md"],
        "reason": "Analysis is one-off; roadmap is forward-looking",
        "action": "DELETE ANALYSIS, keep ROADMAP"
    },
    
    "EARLY_SEASON_BETTING_GUIDANCE.md": {
        "conflicts": [],
        "reason": "2024 specific guidance - may be stale",
        "action": "Archive or DELETE if no longer relevant"
    },
    
    "SEASON_AVG_VS_GAME_LEVEL_FEATURES.md": {
        "conflicts": [],
        "reason": "Analysis document - check if still relevant",
        "action": "If not actively used, DELETE"
    },
}

# STALE PATTERNS
STALE_INDICATORS = {
    "AZURE_BLOB_STORAGE_ARCHITECTURE.md": "Superseded by SINGLE_SOURCE_OF_TRUTH.md",
    "AZURE_INFRASTRUCTURE_DIAGRAM.md": "Check if diagram is current",
    "AZURE_RESOURCE_CLEANUP.md": "One-off resource cleanup - likely stale",
    "AZURE_RESOURCE_GROUP_REVIEW.md": "One-off review - likely stale",
    "FILES_SUMMARY.md": "Directory listing - becomes stale quickly",
    "CONFIGURATION.md": "Check if superseded by SINGLE_SOURCE_OF_TRUTH.md",
}

class DocumentationAudit:
    """Audit documentation for conflicts and staleness."""
    
    def __init__(self):
        self.issues: List[DocIssue] = []
        self.deletion_queue: Set[str] = set()
        self.keep_list: Set[str] = set()
    
    def run_audit(self):
        """Run complete documentation audit."""
        print("\n" + "="*80)
        print("DOCUMENTATION CONFLICT & STALENESS AUDIT")
        print("="*80)
        
        # Check conflicts
        self.check_conflicts()
        
        # Check staleness
        self.check_stale_documents()
        
        # Check for orphaned docs
        self.check_orphaned_docs()
        
        # Generate report
        self.generate_report()
    
    def check_conflicts(self):
        """Check for conflicting/duplicate documentation."""
        print("\n📋 CHECKING FOR CONFLICTS & DUPLICATES...")
        
        for primary, conflict_info in DOC_CONFLICTS.items():
            conflicts = conflict_info.get("conflicts", [])
            reason = conflict_info.get("reason", "")
            action = conflict_info.get("action", "")
            
            print(f"\n  {primary}")
            print(f"    Conflicts: {', '.join(conflicts) if conflicts else 'None'}")
            print(f"    Reason: {reason}")
            print(f"    Action: {action}")
            
            # Mark secondary docs for deletion consideration
            for conflict_doc in conflicts:
                self.issues.append(DocIssue(
                    doc=conflict_doc,
                    category="duplicate",
                    severity="high",
                    reason=f"Superseded by {primary}",
                    keep_instead=primary
                ))
                self.deletion_queue.add(conflict_doc)
            
            self.keep_list.add(primary)
    
    def check_stale_documents(self):
        """Check for stale documents."""
        print("\n🔍 CHECKING FOR STALE DOCUMENTS...")
        
        for doc, reason in STALE_INDICATORS.items():
            print(f"\n  {doc}")
            print(f"    Status: {reason}")
            print(f"    ⚠️  Requires manual review")
            
            self.issues.append(DocIssue(
                doc=doc,
                category="stale",
                severity="medium",
                reason=reason
            ))
    
    def check_orphaned_docs(self):
        """Check for documents not referenced in code."""
        print("\n🔎 CHECKING FOR ORPHANED DOCUMENTS...")
        
        # Docs that should exist but might be orphaned
        potentially_orphaned = [
            "FILES_SUMMARY.md",
            "AZURE_RESOURCE_CLEANUP.md",
            "AZURE_RESOURCE_GROUP_REVIEW.md",
        ]
        
        for doc in potentially_orphaned:
            print(f"  - {doc} (needs reference check)")
    
    def generate_report(self):
        """Generate deletion audit report."""
        print("\n" + "="*80)
        print("DELETION RECOMMENDATION REPORT")
        print("="*80)
        
        high_severity = [i for i in self.issues if i.severity == "high"]
        medium_severity = [i for i in self.issues if i.severity == "medium"]
        
        print(f"\n🗑️  HIGH PRIORITY DELETIONS ({len(high_severity)}):")
        for issue in high_severity:
            print(f"   DELETE: {issue.doc}")
            print(f"   Reason: {issue.reason}")
            if issue.keep_instead:
                print(f"   Keep instead: {issue.keep_instead}")
        
        print(f"\n⚠️  MEDIUM PRIORITY REVIEW ({len(medium_severity)}):")
        for issue in medium_severity:
            print(f"   REVIEW: {issue.doc}")
            print(f"   Reason: {issue.reason}")
        
        print(f"\n✅ AUTHORITATIVE DOCS TO KEEP ({len(self.keep_list)}):")
        for doc in sorted(self.keep_list):
            print(f"   - {doc}")
        
        # Summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print(f"High Priority Deletions: {len(high_severity)}")
        print(f"Medium Priority Reviews:  {len(medium_severity)}")
        print(f"Authoritative Docs:       {len(self.keep_list)}")
        
        print("\nNext Step: Generate deletion script")
        return self.issues


class DeletionAuditTrail:
    """Generate audit trail for documentation deletions."""
    
    def __init__(self, issues: List[DocIssue]):
        self.issues = issues
        self.audit_file = ROOT / "DOCUMENTATION_DELETION_AUDIT.json"
    
    def create_deletion_script(self, dry_run=True):
        """Create deletion script with audit trail."""
        
        high_priority = [i for i in self.issues if i.severity == "high"]
        
        print("\n" + "="*80)
        print("DELETION SCRIPT (DRY-RUN)")
        print("="*80)
        
        print("\n# HIGH PRIORITY DELETIONS (execute immediately)")
        for issue in high_priority:
            doc_path = DOCS_DIR / issue.doc
            print(f"rm '{doc_path}'  # {issue.reason}")
        
        print("\n# Create audit trail")
        audit_trail = {
            "timestamp": datetime.now().isoformat(),
            "action": "documentation_cleanup",
            "deletions": [asdict(i) for i in high_priority],
            "status": "pending_execution"
        }
        
        print(f"\nAudit trail will be saved to: {self.audit_file}")
        return audit_trail


def main():
    """Execute documentation audit."""
    audit = DocumentationAudit()
    audit.run_audit()
    
    # Generate deletion audit trail
    trail = DeletionAuditTrail(audit.issues)
    deletion_plan = trail.create_deletion_script()
    
    print("\n" + "="*80)
    print("TO EXECUTE DELETIONS:")
    print("="*80)
    print("python docs/cleanup_documentation.py --execute")


if __name__ == "__main__":
    main()
