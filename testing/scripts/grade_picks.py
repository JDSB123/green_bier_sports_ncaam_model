#!/usr/bin/env python3
"""
Grade betting picks against actual game results using ESPN API.
"""
from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"


@dataclass
class GameResult:
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    home_h1_score: int
    away_h1_score: int
    total: int
    h1_total: int
    spread_result: int  # positive = home won by X
    h1_spread_result: int
    status: str


def fetch_scoreboard(date: str) -> list[dict]:
    """Fetch all games for a specific date (YYYYMMDD format)."""
    url = f"{ESPN_BASE}/scoreboard?dates={date}&groups=50&limit=400"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.load(resp)
            return data.get("events", [])
    except Exception as e:
        print(f"  [WARN] Failed to fetch {date}: {e}")
        return []


def parse_game(event: dict) -> Optional[GameResult]:
    """Extract game result including halftime scores."""
    try:
        comp = event.get("competitions", [{}])[0]
        competitors = comp.get("competitors", [])

        if len(competitors) != 2:
            return None

        home_team = away_team = ""
        home_score = away_score = 0
        home_h1 = away_h1 = 0

        for c in competitors:
            team_data = c.get("team", {})
            team_name = team_data.get("shortDisplayName") or team_data.get("displayName", "")
            score = int(c.get("score", 0) or 0)

            # Get linescores for halftime
            linescores = c.get("linescores", [])
            h1_score = int(linescores[0].get("value", 0)) if linescores else 0

            if c.get("homeAway") == "home":
                home_team = team_name
                home_score = score
                home_h1 = h1_score
            else:
                away_team = team_name
                away_score = score
                away_h1 = h1_score

        status = event.get("status", {}).get("type", {}).get("name", "")

        return GameResult(
            home_team=home_team,
            away_team=away_team,
            home_score=home_score,
            away_score=away_score,
            home_h1_score=home_h1,
            away_h1_score=away_h1,
            total=home_score + away_score,
            h1_total=home_h1 + away_h1,
            spread_result=home_score - away_score,
            h1_spread_result=home_h1 - away_h1,
            status=status,
        )
    except Exception as e:
        return None


def normalize_team(name: str) -> str:
    """Normalize team name for matching."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    # Common aliases
    aliases = {
        "uconn": "connecticut",
        "csu bakersfield": "bakersfield",
        "cal st bakersfield": "bakersfield",
        "cal state bakersfield": "bakersfield",
        "csub": "bakersfield",
        "pepperdine": "pepperdine",
        "umkc": "kansas city",
        "etsu": "east tennessee",
        "east tennessee state": "east tennessee",
        "acu": "abilene christian",
        "abilene chrstn": "abilene christian",
        "fsu": "florida state",
        "nc a&t": "north carolina a t",
        "nc at": "north carolina a t",
        "oral rob": "oral roberts",
        "ucr": "uc riverside",
        "unlv": "unlv",
        "byu": "byu",
        "ucla": "ucla",
        "lsu": "lsu",
        "smu": "smu",
        "gt": "georgia tech",
        "mo st": "missouri state",
        "sd state": "san diego state",
        "s dakota st": "south dakota state",
        "tennessee st": "tennessee state",
        "tennessee state": "tennessee st",
        "mississippi st": "mississippi state",
        "north dakota st": "north dakota state",
        "n dakota st": "north dakota state",
        "boise st": "boise state",
        "boise": "boise state",
    }
    return aliases.get(s, s)


def find_game(results: list[GameResult], team1: str, team2: str) -> Optional[GameResult]:
    """Find game matching two teams."""
    t1 = normalize_team(team1)
    t2 = normalize_team(team2)

    for game in results:
        home = normalize_team(game.home_team)
        away = normalize_team(game.away_team)

        # Check if both teams match
        teams = {home, away}
        if (t1 in home or home in t1 or t1 in away or away in t1) and \
           (t2 in home or home in t2 or t2 in away or away in t2):
            return game

        # Fuzzy match
        for search in [t1, t2]:
            if any(search in t for t in teams) or any(t in search for t in teams):
                other = t2 if search == t1 else t1
                if any(other in t for t in teams) or any(t in other for t in teams):
                    return game

    return None


# Picks from the image - extracted manually
PICKS = [
    # Date, Matchup, Segment, Pick, Spread/Total
    ("2025-12-10", "Wisconsin @ Nebraska", "FG", "Wisconsin +2", 2),
    ("2025-12-10", "Wisconsin @ Nebraska", "1H", "Wisconsin +1", 1),
    ("2025-12-10", "Wisconsin @ Nebraska", "FG", "Under 158.5", 158.5),
    ("2025-12-10", "Duquesne @ Boise State", "FG", "Under 150.5", 150.5),
    ("2025-12-10", "Duquesne @ Boise State", "1H", "Duquesne +8", 8),
    ("2025-12-10", "Duquesne @ Boise State", "FG", "Duquesne +14", 14),
    ("2025-12-11", "Iowa @ Iowa State", "1H", "Over 66.5", 66.5),
    ("2025-12-11", "Iowa @ Iowa State", "FG", "Over 141", 141),
    ("2025-12-11", "Iowa @ Iowa State", "FG", "Iowa +11.5", 11.5),
    ("2025-12-11", "North Dakota State @ CSU Bakersfield", "2H", "CSU Bakersfield +2 (pk)", 2),
    ("2025-12-11", "North Dakota State @ CSU Bakersfield", "2H", "Under 81.5 (pk)", 81.5),
    ("2025-12-11", "North Dakota State @ CSU Bakersfield", "FG", "Under 149.5", 149.5),
    ("2025-12-11", "North Dakota State @ CSU Bakersfield", "FG", "CSU Bakersfield +6.5", 6.5),
    ("2025-12-11", "St. Joseph's @ Syracuse", "2H", "Under 77", 77),
    ("2025-12-12", "Texas @ UConn", "FG", "Over 146.5", 146.5),
    ("2025-12-12", "Texas @ UConn", "FG", "Texas +12", 12),
    ("2025-12-12", "Texas @ UConn", "1H", "Texas +6.5", 6.5),
    ("2025-12-12", "Texas @ UConn", "1H", "Over 69.5", 69.5),
    ("2025-12-12", "California Baptist @ Eastern Washington", "FG", "Cal Baptist -3.5", -3.5),
    ("2025-12-12", "California Baptist @ Eastern Washington", "FG", "Over 154.5", 154.5),
    ("2025-12-12", "California Baptist @ Eastern Washington", "1H", "Cal Baptist -2", -2),
    ("2025-12-12", "California Baptist @ Eastern Washington", "1H", "Over 72.5", 72.5),
    ("2025-12-13", "Memphis @ Louisville", "FG", "Memphis +17", 17),
    ("2025-12-13", "Memphis @ Louisville", "1H", "Memphis +10", 10),
    ("2025-12-13", "Memphis @ Louisville", "1H", "O77 1H", 77),
    ("2025-12-13", "SMU @ LSU", "FG", "SMU o158.5", 158.5),
    ("2025-12-13", "SMU @ LSU", "1H", "SMU o75", 75),
    ("2025-12-13", "SMU @ LSU", "2H", "LSU u83", 83),
    ("2025-12-13", "UC Riverside @ BYU", "FG", "UC Riverside +34", 34),
    ("2025-12-13", "UC Riverside @ BYU", "FG", "UC Riverside o155", 155),
    ("2025-12-13", "Alabama vs Arizona (neutral)", "FG", "Alabama -3", -3),
    ("2025-12-13", "Alabama vs Arizona (neutral)", "FG", "Alabama ML", None),
    ("2025-12-13", "Alabama vs Arizona (neutral)", "FG", "Alabama +1.5 1H", 1.5),
    ("2025-12-13", "Alabama vs Arizona (neutral)", "2H", "Alabama +3 2H", 3),
    ("2025-12-13", "Alabama vs Arizona (neutral)", "2H", "Arizona/Alabama u92.5 2H", 92.5),
    ("2025-12-13", "Gonzaga vs UCLA (neutral)", "2H", "Gonzaga -5 2H", -5),
    ("2025-12-13", "Gonzaga vs UCLA (neutral)", "2H", "Gonzaga/UCLA o79 2H", 79),
    ("2025-12-13", "Mississippi State @ Utah", "FG", "Over 153.5", 153.5),
    ("2025-12-13", "Mississippi State @ Utah", "1H", "Over 72", 72),
    ("2025-12-13", "Pepperdine @ Cal State Bakersfield", "FG", "Over 148", 148),
    ("2025-12-13", "Pepperdine @ Cal State Bakersfield", "1H", "Over 69.5", 69.5),
    ("2025-12-13", "Tennessee State @ UNLV", "FG", "Over 161", 161),
    ("2025-12-13", "Tennessee State @ UNLV", "1H", "Over 76", 76),
    ("2025-12-13", "Alabama vs Arizona (neutral)", "2H", "Under 92.5", 92.5),
    ("2025-12-13", "Alabama vs Arizona (neutral)", "2H", "Alabama +3", 3),
    ("2025-12-13", "Memphis @ Louisville", "FG", "Memphis +17", 17),
    ("2025-12-13", "Memphis @ Louisville", "1H", "Memphis +10", 10),
    ("2025-12-13", "Memphis @ Louisville", "1H", "Over 77", 77),
    ("2025-12-13", "West Virginia vs Ohio State (Neutral)", "FG", "Ohio State -3.5", -3.5),
    ("2025-12-13", "West Virginia vs Ohio State (Neutral)", "FG", "Over 145", 145),
    ("2025-12-13", "West Virginia vs Ohio State (Neutral)", "1H", "Over 68.5", 68.5),
    ("2025-12-13", "SMU vs LSU (Neutral)", "FG", "Over 158.5", 158.5),
    ("2025-12-13", "SMU vs LSU (Neutral)", "1H", "Over 75", 75),
    ("2025-12-13", "SMU vs LSU (Neutral)", "2H", "Under 83", 83),
    ("2025-12-13", "UC Riverside @ BYU", "FG", "UC Riverside +34", 34),
    ("2025-12-13", "UC Riverside @ BYU", "FG", "Over 155", 155),
    ("2025-12-13", "Mississippi State @ Utah", "FG", "Over 153.5", 153.5),
    ("2025-12-13", "Mississippi State @ Utah", "1H", "Over 72", 72),
    ("2025-12-13", "Arizona vs Alabama", "FG", "Alabama -3", -3),
    ("2025-12-13", "Arizona vs Alabama", "FG", "Alabama ML", None),
    ("2025-12-13", "Arizona vs Alabama", "1H", "Alabama +1.5", 1.5),
    ("2025-12-13", "Pepperdine vs CSU Bakersfield", "FG", "Over 148", 148),
    ("2025-12-13", "Pepperdine vs CSU Bakersfield", "1H", "Over 69.5", 69.5),
    ("2025-12-13", "Tennessee State vs UNLV (Neutral)", "FG", "Over 161", 161),
    ("2025-12-13", "Tennessee State vs UNLV (Neutral)", "1H", "Over 76", 76),
    ("2025-12-13", "Memphis @ Louisville", "1H", "O77", 77),
    ("2025-12-14", "Charlotte @ Charleston", "FG", "O140.5", 140.5),
    ("2025-12-14", "Charlotte @ Charleston", "1H", "O66", 66),
    ("2025-12-14", "Charlotte @ Charleston", "FG", "Charlotte +6", 6),
    ("2025-12-14", "Charlotte @ Charleston", "1H", "Charlotte +3.5", 3.5),
    ("2025-12-15", "SD State @ Opponent", "FG", "SD State +4.5", 4.5),
    ("2025-12-15", "SD State @ Opponent", "1H", "SD State +2", 2),
    ("2025-12-15", "SD State @ Opponent", "1H ML", "SD State ML", None),
    ("2025-12-15", "Niagara @ Opponent", "FG", "Niagara +31", 31),
    ("2025-12-15", "Niagara @ Opponent", "1H", "Niagara +18", 18),
    ("2025-12-16", "FSU @ Dayton", "FG", "Under 161.5", 161.5),
    ("2025-12-16", "Marist @ GT", "FG", "Under 140.5", 140.5),
    ("2025-12-16", "SC @ Clemson", "1H", "Over 67", 67),
    ("2025-12-16", "NC A&T @ UNCG", "FG", "Over 147", 147),
    ("2025-12-16", "UMKC @ Oklahoma", "FG", "UMKC +29", 29),
    ("2025-12-16", "UMKC @ Oklahoma", "1H", "UMKC +16.5", 16.5),
    ("2025-12-16", "Oral Rob @ MO St", "1H", "Over 69", 69),
    ("2025-12-16", "ETSU @ UNC", "FG", "Under 151", 151),
    ("2025-12-16", "Butler @ UConn", "FG", "Over 145.5", 145.5),
    ("2025-12-16", "Butler @ UConn", "1H", "Over 70", 70),
    ("2025-12-16", "Butler @ UConn", "2H", "Over 75", 75),
    ("2025-12-16", "Towson @ Kansas", "FG", "Kansas -16", -16),
    ("2025-12-16", "Pacific @ BYU", "FG", "Pacific +23", 23),
    ("2025-12-16", "ACU @ Arizona", "FG", "ACU +33.5", 33.5),
    ("2025-12-16", "ACU @ Arizona", "1H", "ACU +19.5", 19.5),
    ("2025-12-16", "Montana St @ Cal Poly", "FG", "Under 159", 159),
    ("2025-12-17", "Arizona State @ UCLA", "FG", "Over 143", 143),
    ("2025-12-17", "Arizona State @ UCLA", "1H", "Over 68", 68),
    ("2025-12-17", "Portland @ Oregon", "FG", "Portland +19.5", 19.5),
    ("2025-12-17", "Portland @ Oregon", "1H", "Portland +11.5", 11.5),
    ("2025-12-17", "Stanford @ Opponent", "2H", "Stanford -3", -3),
    ("2025-12-18", "Pepperdine @ Long Beach St", "FG", "Pepperdine -4", -4),
    ("2025-12-18", "Pepperdine @ Long Beach St", "FG", "Pepperdine ML", None),
    ("2025-12-18", "Pepperdine @ Long Beach St", "FG", "Over 141", 141),
    ("2025-12-21", "North Dakota @ Nebraska", "FG", "ND +29.5", 29.5),
    ("2025-12-21", "North Dakota @ Nebraska", "FG", "Over 152.5", 152.5),
    ("2025-12-21", "North Dakota @ Nebraska", "1H", "ND +17.5", 17.5),
    ("2025-12-21", "North Dakota @ Nebraska", "1H", "Under 73.5", 73.5),
    ("2025-12-21", "North Dakota @ Nebraska", "2H", "Over 77.5", 77.5),
    ("2025-12-21", "Norfolk @ UTEP", "1H", "Norfolk ML", None),
    ("2025-12-21", "Norfolk @ UTEP", "1H", "Under 62.5", 62.5),
    ("2025-12-21", "Norfolk @ UTEP", "FG", "Norfolk ML", None),
    ("2025-12-23", "Villanova @ Seton Hall", "FG", "Over 136", 136),
    ("2025-12-23", "Villanova @ Seton Hall", "FG", "Seton Hall -1", -1),
    ("2025-12-23", "Villanova @ Seton Hall", "FG", "Seton Hall ML", None),
    ("2025-12-23", "Villanova @ Seton Hall", "1H", "Over 62.5", 62.5),
    ("2025-12-23", "Villanova @ Seton Hall", "1H", "Seton Hall PK", 0),
]


def grade_pick(pick: tuple, game: GameResult) -> tuple[str, str]:
    """Grade a single pick. Returns (result, explanation)."""
    date, matchup, segment, pick_str, line = pick

    if game.status != "STATUS_FINAL":
        return "PENDING", f"Game not final (status: {game.status})"

    pick_lower = pick_str.lower()

    # Determine which scores to use based on segment
    if segment == "1H":
        total = game.h1_total
        spread = game.h1_spread_result
        home_score = game.home_h1_score
        away_score = game.away_h1_score
    elif segment == "2H":
        total = game.total - game.h1_total
        spread = game.spread_result - game.h1_spread_result
        home_score = game.home_score - game.home_h1_score
        away_score = game.away_score - game.away_h1_score
    else:  # FG
        total = game.total
        spread = game.spread_result
        home_score = game.home_score
        away_score = game.away_score

    # Parse the pick
    if "over" in pick_lower:
        if line and total > line:
            return "WIN", f"Total {total} > {line}"
        elif line and total < line:
            return "LOSS", f"Total {total} < {line}"
        else:
            return "PUSH", f"Total {total} = {line}"

    elif "under" in pick_lower:
        if line and total < line:
            return "WIN", f"Total {total} < {line}"
        elif line and total > line:
            return "LOSS", f"Total {total} > {line}"
        else:
            return "PUSH", f"Total {total} = {line}"

    elif "ml" in pick_lower or line is None:
        # Moneyline bet - need to figure out which team
        for team in [game.home_team.lower(), game.away_team.lower()]:
            if any(t in pick_lower for t in team.split()):
                is_home = team in game.home_team.lower()
                if is_home:
                    if home_score > away_score:
                        return "WIN", f"{game.home_team} won {home_score}-{away_score}"
                    else:
                        return "LOSS", f"{game.home_team} lost {home_score}-{away_score}"
                else:
                    if away_score > home_score:
                        return "WIN", f"{game.away_team} won {away_score}-{home_score}"
                    else:
                        return "LOSS", f"{game.away_team} lost {away_score}-{home_score}"
        return "UNKNOWN", "Could not determine ML team"

    else:
        # Spread bet
        # Extract team from pick
        for team_name in [game.home_team, game.away_team]:
            if any(t.lower() in pick_lower for t in team_name.split()):
                is_home = team_name == game.home_team

                if is_home:
                    # Home team spread: positive line means they're underdog
                    adjusted = spread + line if line else spread
                else:
                    # Away team spread: need to flip
                    adjusted = -spread + line if line else -spread

                if adjusted > 0:
                    return "WIN", f"Covered by {abs(adjusted):.1f} pts ({game.away_team} {away_score} @ {game.home_team} {home_score})"
                elif adjusted < 0:
                    return "LOSS", f"Lost by {abs(adjusted):.1f} pts ({game.away_team} {away_score} @ {game.home_team} {home_score})"
                else:
                    return "PUSH", f"Push ({game.away_team} {away_score} @ {game.home_team} {home_score})"

        return "UNKNOWN", f"Could not parse spread pick: {pick_str}"


def main():
    print("=" * 80)
    print(" NCAAM PICKS GRADER - ESPN API")
    print("=" * 80)

    # Get unique dates from picks
    dates = sorted(set(p[0] for p in PICKS))

    # Fetch results for each date
    all_results: dict[str, list[GameResult]] = {}

    for date in dates:
        date_fmt = date.replace("-", "")
        print(f"\nFetching results for {date}...")
        events = fetch_scoreboard(date_fmt)
        results = []
        for event in events:
            game = parse_game(event)
            if game:
                results.append(game)
                print(f"  {game.away_team} {game.away_score} @ {game.home_team} {game.home_score} ({game.status})")
        all_results[date] = results

    # Grade each pick
    print("\n" + "=" * 80)
    print(" GRADING RESULTS")
    print("=" * 80)

    wins = losses = pushes = pending = unknown = 0

    for pick in PICKS:
        date, matchup, segment, pick_str, line = pick

        # Parse teams from matchup
        matchup_clean = re.sub(r"\s*\(.*?\)\s*", " ", matchup)
        if " @ " in matchup_clean:
            teams = matchup_clean.split(" @ ")
        elif " vs " in matchup_clean:
            teams = matchup_clean.split(" vs ")
        else:
            teams = [matchup_clean, ""]

        game = find_game(all_results.get(date, []), teams[0].strip(), teams[1].strip())

        if not game:
            print(f"[NOT FOUND] {date} {matchup} | {segment} {pick_str}")
            unknown += 1
            continue

        result, explanation = grade_pick(pick, game)

        if result == "WIN":
            wins += 1
            symbol = "[W]"
        elif result == "LOSS":
            losses += 1
            symbol = "[L]"
        elif result == "PUSH":
            pushes += 1
            symbol = "[P]"
        elif result == "PENDING":
            pending += 1
            symbol = "[?]"
        else:
            unknown += 1
            symbol = "[?]"

        print(f"{symbol} {result:8s} {date} {matchup} | {segment} {pick_str}")
        print(f"         -> {explanation}")

    # Summary
    print("\n" + "=" * 80)
    print(" SUMMARY")
    print("=" * 80)
    total_graded = wins + losses + pushes
    win_pct = (wins / total_graded * 100) if total_graded > 0 else 0

    print(f"  Wins:     {wins}")
    print(f"  Losses:   {losses}")
    print(f"  Pushes:   {pushes}")
    print(f"  Pending:  {pending}")
    print(f"  Unknown:  {unknown}")
    print(f"  -----------------")
    print(f"  Win Rate: {win_pct:.1f}% ({wins}/{total_graded})")

    # ROI calculation (assuming -110 odds standard)
    if total_graded > 0:
        # At -110, you risk $110 to win $100
        # Simplified: risk $1 to win $0.91
        profit = (wins * 0.91) - losses
        roi = profit / total_graded * 100
        print(f"  Est. ROI: {roi:+.1f}% (assuming -110 standard juice)")


if __name__ == "__main__":
    main()
