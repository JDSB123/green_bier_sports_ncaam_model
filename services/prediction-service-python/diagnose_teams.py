#!/usr/bin/env python3
"""Diagnose team matching issues - run inside container."""
import os
import psycopg2

def main():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    
    print("=" * 60)
    print("TEAM MATCHING DIAGNOSTIC")
    print("=" * 60)
    
    # Check games where home and away resolved to the same team
    cur.execute("""
        SELECT g.id, ht.canonical_name as home, at.canonical_name as away,
               g.home_team_id, g.away_team_id
        FROM games g
        JOIN teams ht ON g.home_team_id = ht.id
        JOIN teams at ON g.away_team_id = at.id
        WHERE DATE(g.commence_time AT TIME ZONE 'America/Chicago') = '2025-12-22'
          AND ht.canonical_name = at.canonical_name
    """)
    bad_games = cur.fetchall()
    
    if bad_games:
        print(f"\n❌ FOUND {len(bad_games)} GAMES WITH SAME HOME/AWAY TEAM:")
        for row in bad_games:
            print(f"  Game {row[0]}: {row[1]} vs {row[2]} (team_ids: {row[3]}, {row[4]})")
    else:
        print("\n✓ No games with same home/away team")
    
    # Check the ODDS_API_KEY
    print("\n" + "=" * 60)
    print("ENVIRONMENT CHECKS")
    print("=" * 60)
    
    odds_key = os.getenv("ODDS_API_KEY")
    the_odds_key = os.getenv("THE_ODDS_API_KEY")
    
    print(f"ODDS_API_KEY: {'SET (' + odds_key[:8] + '...)' if odds_key else 'NOT SET'}")
    print(f"THE_ODDS_API_KEY: {'SET (' + the_odds_key[:8] + '...)' if the_odds_key else 'NOT SET'}")
    
    # Check games table structure
    print("\n" + "=" * 60)
    print("SAMPLE GAME DATA (TODAY)")
    print("=" * 60)
    
    cur.execute("""
        SELECT g.id, ht.canonical_name as home, at.canonical_name as away,
               g.home_team_id, g.away_team_id
        FROM games g
        JOIN teams ht ON g.home_team_id = ht.id
        JOIN teams at ON g.away_team_id = at.id
        WHERE DATE(g.commence_time AT TIME ZONE 'America/Chicago') = '2025-12-22'
        ORDER BY g.commence_time
        LIMIT 10
    """)
    for row in cur.fetchall():
        print(f"  {row[1]} (id={row[3]}) vs {row[2]} (id={row[4]})")
    
    # Check team_aliases for Georgia, South Carolina
    print("\n" + "=" * 60)
    print("TEAM ALIASES CHECK (Georgia, South Carolina)")
    print("=" * 60)
    
    for name in ["Georgia", "South Carolina"]:
        cur.execute("""
            SELECT t.id, t.canonical_name, array_agg(ta.alias)
            FROM teams t
            LEFT JOIN team_aliases ta ON t.id = ta.team_id
            WHERE t.canonical_name ILIKE %s
            GROUP BY t.id, t.canonical_name
        """, (f"%{name}%",))
        for row in cur.fetchall():
            print(f"  Team {row[0]}: {row[1]} -> aliases: {row[2]}")
    
    conn.close()
    print("\n✓ Diagnostic complete")

if __name__ == "__main__":
    main()
