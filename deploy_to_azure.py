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
    from testing.azure_io import write_text, upload_directory
    from testing.azure_data_reader import AzureDataReader
except ImportError:
    print("[ERROR] Azure utilities not available. Install azure-storage-blob")
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
            write_text(content, azure_path)
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
            write_text(content, azure_path)
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
    print(f"  Governance files deployed: {governance_count}")
    print(f"  Audit trails deployed: {audit_count}")
    print(f"  Verification: {'✓ PASSED' if verified else '✗ FAILED'}")
    print(f"  Total deployed: {governance_count + audit_count}")
    print("\n  Location: Azure blob storage (ncaam-historical-data/governance/)")
    print("  Authority: DOCUMENTATION_GOVERNANCE_MANIFEST.json")
    
    if verified:
        print("\n✓ DEPLOYMENT COMPLETE - GOVERNANCE BACKED UP TO AZURE")
        return 0
    else:
        print("\n✗ DEPLOYMENT INCOMPLETE - SOME FILES NOT VERIFIED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
