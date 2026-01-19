#!/usr/bin/env python3
"""
Team Matching & Home/Away Verification Script
Validates absolute accuracy across all ingestion sources.

Run inside Docker:
    docker exec ncaam_v33_model_prediction python /app/database/seeds/verify_team_matching.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, '/app')
from sqlalchemy import create_engine, text


def get_db_password():
    """Read password from Docker secret file or environment variable."""
    try:
        with Path("/run/secrets/db_password").open(encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        password = os.getenv('DB_PASSWORD')
        if not password:
            raise RuntimeError(
                "DB_PASSWORD not found. Set DB_PASSWORD environment variable "
                "or ensure /run/secrets/db_password exists."
            )
        return password

DB_PASSWORD = get_db_password()
DATABASE_URL = f"postgresql://ncaam:{DB_PASSWORD}@postgres:5432/ncaam"


def verify_all_games(engine) -> dict:
    """Verify all games for team matching accuracy."""
    results = {
        'total_games': 0,
        'valid_games': 0,
        'invalid_games': [],
        'missing_ratings': [],
        'duplicate_teams': []
    }

    with engine.connect() as conn:
        # Get all scheduled games
        games = conn.execute(text("""
            SELECT
                g.id,
                g.external_id,
                ht.canonical_name as home_team,
                at.canonical_name as away_team,
                g.commence_time,
                g.status
            FROM games g
            JOIN teams ht ON g.home_team_id = ht.id
            JOIN teams at ON g.away_team_id = at.id
            WHERE g.status = 'scheduled'
            ORDER BY g.commence_time
        """)).fetchall()

        results['total_games'] = len(games)

        for game in games:
            game_id, external_id, home_team, away_team, commence_time, status = game

            # Validate using database function
            validation = conn.execute(
                text("SELECT * FROM validate_game_teams(:home, :away)"),
                {"home": home_team, "away": away_team}
            ).fetchone()

            if not validation.is_valid:
                results['invalid_games'].append({
                    'game_id': str(game_id),
                    'external_id': external_id,
                    'home': home_team,
                    'away': away_team,
                    'errors': validation.validation_errors
                })
            elif not validation.home_has_ratings or not validation.away_has_ratings:
                results['missing_ratings'].append({
                    'game_id': str(game_id),
                    'home': home_team,
                    'away': away_team,
                    'home_has_ratings': validation.home_has_ratings,
                    'away_has_ratings': validation.away_has_ratings
                })
            else:
                results['valid_games'] += 1

    return results


def verify_team_resolution(engine) -> dict:
    """Verify team name resolution accuracy."""
    results = {
        'total_aliases': 0,
        'aliases_with_ratings': 0,
        'aliases_without_ratings': 0,
        'unresolved_teams': []
    }

    with engine.connect() as conn:
        # Check alias coverage
        alias_stats = conn.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(DISTINCT ta.team_id) as unique_teams,
                COUNT(DISTINCT CASE WHEN tr.team_id IS NOT NULL THEN ta.team_id END) as teams_with_ratings
            FROM team_aliases ta
            LEFT JOIN team_ratings tr ON ta.team_id = tr.team_id
        """)).fetchone()

        results['total_aliases'] = alias_stats.total
        results['aliases_with_ratings'] = alias_stats.teams_with_ratings

        # Find teams in games without ratings
        missing = conn.execute(text("""
            SELECT DISTINCT t.canonical_name
            FROM games g
            JOIN teams t ON g.home_team_id = t.id OR g.away_team_id = t.id
            LEFT JOIN team_ratings tr ON t.id = tr.team_id
            WHERE g.status = 'scheduled'
              AND tr.team_id IS NULL
            ORDER BY t.canonical_name
        """)).fetchall()

        results['unresolved_teams'] = [row[0] for row in missing]

    return results


def main():
    print("=" * 80)
    print("TEAM MATCHING & HOME/AWAY VERIFICATION")
    print("=" * 80)
    print()

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

    # Verify games
    print("📊 Verifying Games...")
    game_results = verify_all_games(engine)

    print(f"  Total games: {game_results['total_games']}")
    print(f"  ✅ Valid games: {game_results['valid_games']}")
    print(f"  ⚠️  Invalid games: {len(game_results['invalid_games'])}")
    print(f"  ⚠️  Missing ratings: {len(game_results['missing_ratings'])}")

    if game_results['invalid_games']:
        print("\n  ❌ Invalid Games:")
        for game in game_results['invalid_games'][:10]:  # Show first 10
            print(f"    - {game['away']} @ {game['home']}")
            for error in game['errors']:
                print(f"      ERROR: {error}")

    if game_results['missing_ratings']:
        print("\n  ⚠️  Games Missing Ratings:")
        for game in game_results['missing_ratings'][:10]:  # Show first 10
            print(f"    - {game['away']} @ {game['home']}")
            if not game['home_has_ratings']:
                print(f"      Missing: {game['home']} ratings")
            if not game['away_has_ratings']:
                print(f"      Missing: {game['away']} ratings")

    print()

    # Verify team resolution
    print("📋 Verifying Team Resolution...")
    resolution_results = verify_team_resolution(engine)

    print(f"  Total aliases: {resolution_results['total_aliases']}")
    print(f"  Teams with ratings: {resolution_results['aliases_with_ratings']}")

    if resolution_results['unresolved_teams']:
        print(f"\n  ⚠️  Teams in games without ratings ({len(resolution_results['unresolved_teams'])}):")
        for team in resolution_results['unresolved_teams'][:20]:  # Show first 20
            print(f"    - {team}")

    print()

    # Summary
    accuracy_pct = (game_results['valid_games'] / game_results['total_games'] * 100) if game_results['total_games'] > 0 else 0
    print("=" * 80)
    print(f"SUMMARY: {accuracy_pct:.1f}% of games are fully valid")
    print("=" * 80)

    if game_results['valid_games'] == game_results['total_games']:
        print("✅ ALL GAMES VALID - Team matching is 100% accurate!")
    else:
        print(f"⚠️  {game_results['total_games'] - game_results['valid_games']} games need attention")


if __name__ == "__main__":
    main()
