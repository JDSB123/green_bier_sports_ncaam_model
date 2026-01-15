import pandas as pd
def deploy_canonical_master():
    """Upload canonical_training_data_master.csv to Azure canonical blob storage."""
    print("\n" + "="*80)
    print("DEPLOYING CANONICAL MASTER TO AZURE")
    print("="*80)
    local_path = Path(__file__).resolve().parent / "manifests" / "canonical_training_data_master.csv"
    if not local_path.exists():
        print(f"  ✗ NOT FOUND: {local_path}")
        return 0
    try:
        df = pd.read_csv(local_path)
        from testing.azure_io import write_csv
        azure_path = "canonical/canonical_training_data_master.csv"
        write_csv(azure_path, df)
        print(f"  ✓ {local_path} → {azure_path}")
        return 1
    except Exception as e:
        print(f"  ✗ {local_path}: {e}")
        return 0
#!/usr/bin/env python3
"""
DEPLOY TO AZURE: Sync governance files and cleanup artifacts

Syncs to Azure blob storage:
1. Governance documentation
2. Audit trails
3. Cleanup scripts
4. Infrastructure documentation
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

try:
    from testing.azure_io import upload_text, write_csv
    from testing.azure_data_reader import AzureDataReader
except ImportError as e:
    print(f"[ERROR] Azure utilities not available: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

def deploy_governance_files():
    """Deploy governance files to Azure."""
    print("\n" + "="*80)
    print("DEPLOYING GOVERNANCE FILES TO AZURE")
    print("="*80)
    
    # Files to deploy
    governance_files = [
        "DOCUMENTATION_GOVERNANCE_MANIFEST.json",
        "DOCUMENTATION_CLEANUP_PLAN.md",
        "HOW_WE_KNOW_ALL_STALE_DOCS_ARE_DELETED.md",
        "DOCUMENTATION_GOVERNANCE_INFRASTRUCTURE.md",
        "CLEANUP_COMPLETION_SUMMARY.md",
        "EXECUTION_REPORT.txt",
    ]
    
    deployed = 0
    for filename in governance_files:
        filepath = ROOT / filename
        if not filepath.exists():
            print(f"  ✗ NOT FOUND: {filename}")
            continue
        
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            
            # Upload to Azure governance folder
            azure_path = f"governance/{filename}"
            upload_text(azure_path, content)
            print(f"  ✓ {filename} → {azure_path}")
            deployed += 1
        except Exception as e:
            print(f"  ✗ {filename}: {e}")
    
    return deployed

def deploy_audit_trails():
    """Deploy audit trail files to Azure."""
    print("\n" + "="*80)
    print("DEPLOYING AUDIT TRAILS TO AZURE")
    print("="*80)
    
    audit_files = [
        "manifests/comprehensive_ingestion_audit.json",
    ]
    
    deployed = 0
    for filename in audit_files:
        filepath = ROOT / filename
        if not filepath.exists():
            print(f"  ✗ NOT FOUND: {filename}")
            continue
        
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            
            # Upload audit trail
            azure_path = f"governance/audits/{filename.split('/')[-1]}"
            upload_text(azure_path, content)
            print(f"  ✓ {filename} → {azure_path}")
            deployed += 1
        except Exception as e:
            print(f"  ✗ {filename}: {e}")
    
    return deployed

def verify_azure_deployment():
    """Verify files in Azure."""
    print("\n" + "="*80)
    print("VERIFYING AZURE DEPLOYMENT")
    print("="*80)
    
    try:
        reader = AzureDataReader()
        
        # List governance files
        governance_files = reader.list_files("governance/")
        print(f"  ✓ Governance files in Azure: {len(governance_files)}")
        for f in governance_files[:5]:
            print(f"    - {f}")
        if len(governance_files) > 5:
            print(f"    ... and {len(governance_files) - 5} more")
        
        return True
    except Exception as e:
        print(f"  ✗ Verification failed: {e}")
        return False

def main():
    """Execute deployment."""
    # Deploy canonical master
    canonical_count = deploy_canonical_master()
    print("\nDEPLOYMENT TO AZURE: Governance & Cleanup Artifacts")
    
    # Deploy governance files
    governance_count = deploy_governance_files()
    
    # Deploy audit trails
    audit_count = deploy_audit_trails()
    
    # Verify
    verified = verify_azure_deployment()
    
    # Summary
    print("\n" + "="*80)
    print("DEPLOYMENT SUMMARY")
    print("="*80)
    print(f"  Canonical master deployed: {canonical_count}")
    print(f"  Governance files deployed: {governance_count}")
    print(f"  Audit trails deployed: {audit_count}")
    print(f"  Verification: {'✓ PASSED' if verified else '✗ FAILED'}")
    print(f"  Total deployed: {canonical_count + governance_count + audit_count}")
    print("\n  Location: Azure blob storage (ncaam-historical-data/canonical/)")
    print("  Authority: manifests/canonical_training_data_master.csv")
    
    if verified and canonical_count:
        print("\n✓ DEPLOYMENT COMPLETE - CANONICAL MASTER & GOVERNANCE BACKED UP TO AZURE")
        return 0
    else:
        print("\n✗ DEPLOYMENT INCOMPLETE - SOME FILES NOT VERIFIED OR CANONICAL MASTER NOT UPLOADED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
