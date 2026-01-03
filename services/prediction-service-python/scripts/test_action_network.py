#!/usr/bin/env python3
"""
Test Action Network betting splits integration.

Usage:
    $env:PYTHONPATH = "."; python scripts/test_action_network.py
"""

import sys
from datetime import datetime
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.betting_splits import ActionNetworkClient, ActionNetworkError


def main():
    print("=" * 60)
    print("Action Network Betting Splits Test")
    print("=" * 60)
    
    try:
        client = ActionNetworkClient()
        print(f"\n✓ Client initialized")
        print(f"  - Has credentials: {bool(client._username)}")
        
        # Fetch today's games
        print(f"\n📊 Fetching NCAAB betting splits...")
        splits = client.get_betting_splits()
        
        print(f"\n✓ Found {len(splits)} games with betting data")
        print(f"  - Premium access: {client._is_premium}")
        
        if not splits:
            print("\n⚠️  No games found. This could mean:")
            print("    - No NCAAB games scheduled today")
            print("    - API returned empty response")
            print("    - Off-season")
            return
        
        # Display sample games
        print("\n" + "-" * 60)
        print("Sample Games:")
        print("-" * 60)
        
        for i, game in enumerate(splits[:5]):
            print(f"\n{i+1}. {game.away_team} @ {game.home_team}")
            if game.game_time:
                print(f"   Time: {game.game_time.strftime('%H:%M ET')}")
            
            if game.has_spread_splits:
                print(f"\n   SPREAD ({game.spread_line or 'N/A'}):")
                print(f"     Home: {game.spread_home_public:.1f}% tickets, {game.spread_home_money:.1f}% money")
                print(f"     Away: {game.spread_away_public:.1f}% tickets, {game.spread_away_money:.1f}% money")
                
                if game.is_sharp_spread_home:
                    print(f"     ⚡ SHARP on HOME (fewer tickets, more money)")
                elif game.is_sharp_spread_away:
                    print(f"     ⚡ SHARP on AWAY (fewer tickets, more money)")
            else:
                print(f"\n   SPREAD: No data available")
            
            if game.has_total_splits:
                print(f"\n   TOTAL ({game.total_line or 'N/A'}):")
                print(f"     Over:  {game.total_over_public:.1f}% tickets, {game.total_over_money:.1f}% money")
                print(f"     Under: {game.total_under_public:.1f}% tickets, {game.total_under_money:.1f}% money")
                
                if game.is_sharp_over:
                    print(f"     ⚡ SHARP on OVER (fewer tickets, more money)")
                elif game.is_sharp_under:
                    print(f"     ⚡ SHARP on UNDER (fewer tickets, more money)")
            else:
                print(f"\n   TOTAL: No data available")
        
        # Summary stats
        print("\n" + "=" * 60)
        print("Summary:")
        print("=" * 60)
        
        with_spread = sum(1 for g in splits if g.has_spread_splits)
        with_total = sum(1 for g in splits if g.has_total_splits)
        sharp_home = sum(1 for g in splits if g.is_sharp_spread_home)
        sharp_away = sum(1 for g in splits if g.is_sharp_spread_away)
        sharp_over = sum(1 for g in splits if g.is_sharp_over)
        sharp_under = sum(1 for g in splits if g.is_sharp_under)
        
        print(f"\nGames with spread splits: {with_spread}/{len(splits)}")
        print(f"Games with total splits:  {with_total}/{len(splits)}")
        print(f"\nSharp indicators:")
        print(f"  - Sharp on home spread: {sharp_home}")
        print(f"  - Sharp on away spread: {sharp_away}")
        print(f"  - Sharp on over:        {sharp_over}")
        print(f"  - Sharp on under:       {sharp_under}")
        
        print("\n✅ Test completed successfully!")
        
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
