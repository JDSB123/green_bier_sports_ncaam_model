#!/usr/bin/env python3
"""
Inspect raw Action Network API response for debugging.

Usage:
    $env:PYTHONPATH = "."; python scripts/inspect_action_network_data.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.betting_splits import ActionNetworkClient, ActionNetworkError


def main():
    print("=" * 60)
    print("Action Network Raw Data Inspector")
    print("=" * 60)
    
    try:
        client = ActionNetworkClient()
        
        # Authenticate if possible
        if client._username:
            print(f"\n🔐 Attempting authentication...")
            if client._authenticate():
                print(f"   ✓ Authenticated (premium access)")
            else:
                print(f"   ⚠️ Authentication failed (using public endpoint)")
        else:
            print(f"\n📢 No credentials found (using public endpoint)")
        
        # Fetch raw data
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        if client._is_premium:
            endpoint = "/web/v1/games/ncaab"
        else:
            endpoint = "/web/v1/scoreboard/ncaab"
        
        print(f"\n📡 Fetching from: {endpoint}")
        print(f"   Date: {date_str}")
        
        data = client._request(endpoint, {"date": date_str}, use_cache=False)
        
        # Save raw response
        output_file = Path("action_network_raw_response.json")
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2, default=str)
        
        print(f"\n✓ Raw response saved to: {output_file}")
        
        # Analyze structure
        print("\n" + "-" * 60)
        print("Response Structure:")
        print("-" * 60)
        
        def describe_structure(obj, indent=0):
            prefix = "  " * indent
            if isinstance(obj, dict):
                print(f"{prefix}{{")
                for key, value in list(obj.items())[:10]:
                    if isinstance(value, (dict, list)):
                        print(f"{prefix}  '{key}': ", end="")
                        describe_structure(value, indent + 2)
                    else:
                        print(f"{prefix}  '{key}': {type(value).__name__} = {str(value)[:50]}")
                if len(obj) > 10:
                    print(f"{prefix}  ... and {len(obj) - 10} more keys")
                print(f"{prefix}}}")
            elif isinstance(obj, list):
                print(f"[{len(obj)} items]")
                if obj:
                    print(f"{prefix}  First item:")
                    describe_structure(obj[0], indent + 2)
            else:
                print(f"{type(obj).__name__}")
        
        describe_structure(data)
        
        # Show first game details
        games = data.get("games") or data.get("events") or []
        if games:
            print("\n" + "-" * 60)
            print("First Game Full Details:")
            print("-" * 60)
            print(json.dumps(games[0], indent=2, default=str))
        
        print("\n✅ Inspection complete!")
        
    except ActionNetworkError as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
