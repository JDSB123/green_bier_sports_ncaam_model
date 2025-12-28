"""
Python-based odds sync for Azure deployments.

This module replicates the Rust odds-ingestion service functionality using pure Python.
It fetches odds from The Odds API and stores them in the odds_snapshots table,
using the same schema as the Rust service for compatibility.

Use this when the Rust binary is not available (e.g., in Azure Container Apps).
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import execute_batch, register_uuid

from .odds_api_client import OddsApiClient, OddsApiError

# Register UUID type adapter for psycopg2
register_uuid()

# Default team name mappings for common mismatches
# These are applied BEFORE database lookup as a fast path
# The database resolve_team_name() function handles 950+ aliases
TEAM_NAME_ALIASES = {
    # Connecticut variants
    "UConn": "Connecticut",
    "UConn Huskies": "Connecticut",
    "UCONN": "Connecticut",
    "Connecticut Huskies": "Connecticut",
    # Florida variants - CRITICAL
    "Florida A&M Rattlers": "Florida A&M",
    "FAMU": "Florida A&M",
    "Fla A&M": "Florida A&M",
    "Florida AM": "Florida A&M",
    "FIU Panthers": "FIU",
    "Florida International": "FIU",
    "Florida International Panthers": "FIU",
    "FAU Owls": "FAU",
    "Florida Atlantic Owls": "FAU",
    "Florida Atlantic": "FAU",
    # Oregon variants - CRITICAL
    "Oregon Ducks": "Oregon",
    "Oregon State Beavers": "Oregon St.",
    "Oregon State": "Oregon St.",
    "OSU Beavers": "Oregon St.",
    # Common Power 5 aliases
    "Duke Blue Devils": "Duke",
    "North Carolina Tar Heels": "North Carolina",
    "UNC": "North Carolina",
    "NC State Wolfpack": "NC State",
    "Kentucky Wildcats": "Kentucky",
    "Kansas Jayhawks": "Kansas",
    "Gonzaga Bulldogs": "Gonzaga",
    "Alabama Crimson Tide": "Alabama",
    "Auburn Tigers": "Auburn",
    "Tennessee Volunteers": "Tennessee",
    "Texas Longhorns": "Texas",
    "Texas A&M Aggies": "Texas A&M",
    "Michigan Wolverines": "Michigan",
    "Ohio State Buckeyes": "Ohio St.",
    "Purdue Boilermakers": "Purdue",
    "Houston Cougars": "Houston",
    # State abbreviations
    "Florida St. Seminoles": "Florida St.",
    "Florida State Seminoles": "Florida St.",
    "Florida State": "Florida St.",
    "Michigan State Spartans": "Michigan St.",
    "Michigan State": "Michigan St.",
    "Penn State Nittany Lions": "Penn St.",
    "Penn State": "Penn St.",
    "Ohio State": "Ohio St.",
    "Kansas State Wildcats": "Kansas St.",
    "Kansas State": "Kansas St.",
    "Iowa State Cyclones": "Iowa St.",
    "Iowa State": "Iowa St.",
    "Oklahoma State Cowboys": "Oklahoma St.",
    "Oklahoma State": "Oklahoma St.",
    # HBCU teams
    "Grambling State Tigers": "Grambling St.",
    "Grambling State": "Grambling St.",
    "Jackson State Tigers": "Jackson St.",
    "Jackson State": "Jackson St.",
    "Norfolk State Spartans": "Norfolk St.",
    "Norfolk State": "Norfolk St.",
    "Morgan State Bears": "Morgan St.",
    "Morgan State": "Morgan St.",
    "Coppin State Eagles": "Coppin St.",
    "Coppin State": "Coppin St.",
    "Hampton Pirates": "Hampton",
    "Alabama State Hornets": "Alabama St.",
    "Alabama State": "Alabama St.",
    "Prairie View A&M Panthers": "Prairie View A&M",
    "Texas Southern Tigers": "Texas Southern",
    "Mississippi Valley State": "Mississippi Valley St.",
    "Miss Valley St. Delta Devils": "Mississippi Valley St.",
    # Other common aliases
    "Southeastern Louisiana Lions": "Southeastern Louisiana",
    "SE Louisiana": "Southeastern Louisiana",
    "SE Louisiana Lions": "Southeastern Louisiana",
    "Tarleton State Texans": "Tarleton St.",
    "Tarleton State": "Tarleton St.",
    "Tarleton St. Texans": "Tarleton St.",
    "North Alabama Lions": "North Alabama",
    "California Golden Bears": "California",
    "Cal Bears": "California",
    "Cal": "California",
    "High Point Panthers": "High Point",
    "La Salle Explorers": "La Salle",
    "Navy Midshipmen": "Navy",
}


def normalize_team_name(name: str) -> str:
    """Normalize team name for matching.

    First checks local aliases for fast path, then relies on
    database resolve_team_name() function for 950+ aliases.
    """
    return TEAM_NAME_ALIASES.get(name, name)


class OddsSyncService:
    """
    Syncs odds from The Odds API to the database.
    
    Compatible with the Rust odds-ingestion service schema.
    """

    def __init__(
        self,
        database_url: str,
        api_key: Optional[str] = None,
        enable_full: bool = True,
        enable_h1: bool = True,
        enable_h2: bool = False,
    ):
        self.database_url = database_url
        self.api_key = api_key
        self.enable_full = enable_full
        self.enable_h1 = enable_h1
        self.enable_h2 = enable_h2
        
        # Parse database URL for psycopg2
        # Format: postgres://user:pass@host:port/db?sslmode=require
        self._parse_db_url()
        
        self.client = OddsApiClient(api_key=api_key)
        self.game_cache: Dict[str, uuid.UUID] = {}

    def _parse_db_url(self):
        """Parse DATABASE_URL into psycopg2 connection params."""
        import urllib.parse
        
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        
        parsed = urllib.parse.urlparse(url)
        self.db_params = {
            "host": parsed.hostname,
            "port": parsed.port or 5432,
            "user": parsed.username,
            "password": parsed.password,
            "dbname": parsed.path.lstrip("/"),
        }
        
        # Parse query string for sslmode
        query = urllib.parse.parse_qs(parsed.query)
        if "sslmode" in query:
            self.db_params["sslmode"] = query["sslmode"][0]

    def _get_connection(self):
        """Get a database connection."""
        return psycopg2.connect(**self.db_params)

    def _resolve_team_id(self, cur, team_name: str) -> Optional[uuid.UUID]:
        """
        Resolve a team name to its ID using strict matching.

        Priority order (NEVER settle for partial/fuzzy matches):
        1. Exact canonical_name match (case-insensitive)
        2. resolve_team_name() database function (uses 950+ aliases)
        3. Python-side normalization then exact match

        Returns None if no match found - caller must handle.
        """
        # Normalize with Python aliases first
        normalized = normalize_team_name(team_name)

        # Step 1: Try exact match on canonical_name
        cur.execute(
            """
            SELECT t.id FROM teams t
            LEFT JOIN team_ratings tr ON t.id = tr.team_id
            WHERE LOWER(t.canonical_name) = LOWER(%s)
            ORDER BY tr.team_id IS NOT NULL DESC
            LIMIT 1
            """,
            (normalized,)
        )
        row = cur.fetchone()
        if row:
            return row[0]

        # Step 2: Use database resolve_team_name() function
        cur.execute("SELECT resolve_team_name(%s)", (team_name,))
        resolved = cur.fetchone()
        if resolved and resolved[0]:
            cur.execute(
                """
                SELECT t.id FROM teams t
                LEFT JOIN team_ratings tr ON t.id = tr.team_id
                WHERE t.canonical_name = %s
                ORDER BY tr.team_id IS NOT NULL DESC
                LIMIT 1
                """,
                (resolved[0],)
            )
            row = cur.fetchone()
            if row:
                return row[0]

        # Step 3: Try normalized name exact match
        if normalized != team_name:
            cur.execute(
                """
                SELECT t.id FROM teams t
                LEFT JOIN team_ratings tr ON t.id = tr.team_id
                WHERE LOWER(t.canonical_name) = LOWER(%s)
                ORDER BY tr.team_id IS NOT NULL DESC
                LIMIT 1
                """,
                (normalized,)
            )
            row = cur.fetchone()
            if row:
                return row[0]

        # NO FUZZY/PARTIAL MATCHING - return None
        return None

    def _get_or_create_game_id(
        self,
        conn,
        external_id: str,
        home_team: str,
        away_team: str,
        commence_time: Optional[datetime]
    ) -> uuid.UUID:
        """Get or create a game_id for an external event."""
        if external_id in self.game_cache:
            return self.game_cache[external_id]

        with conn.cursor() as cur:
            # First try to find existing game by external_id
            cur.execute(
                "SELECT id FROM games WHERE external_id = %s",
                (external_id,)
            )
            row = cur.fetchone()
            if row:
                game_id = row[0]
                self.game_cache[external_id] = game_id
                return game_id

            # Resolve team IDs using strict matching
            home_team_id = self._resolve_team_id(cur, home_team)
            away_team_id = self._resolve_team_id(cur, away_team)

            # Try to match existing game by resolved teams and date
            if home_team_id and away_team_id and commence_time:
                game_date = commence_time.date()
                cur.execute(
                    """
                    SELECT g.id FROM games g
                    WHERE g.commence_time::date = %s
                      AND g.home_team_id = %s
                      AND g.away_team_id = %s
                    LIMIT 1
                    """,
                    (game_date, home_team_id, away_team_id)
                )
                row = cur.fetchone()
                if row:
                    game_id = row[0]
                    # Update external_id for future lookups
                    cur.execute(
                        "UPDATE games SET external_id = %s WHERE id = %s",
                        (external_id, game_id)
                    )
                    conn.commit()
                    self.game_cache[external_id] = game_id
                    return game_id

            # Create teams if not found (log warning - these won't have ratings)
            if not home_team_id:
                print(f"    WARNING: Creating new team '{home_team}' (no ratings)")
                cur.execute(
                    "INSERT INTO teams (canonical_name) VALUES (%s) RETURNING id",
                    (home_team,)
                )
                home_team_id = cur.fetchone()[0]

            if not away_team_id:
                print(f"    WARNING: Creating new team '{away_team}' (no ratings)")
                cur.execute(
                    "INSERT INTO teams (canonical_name) VALUES (%s) RETURNING id",
                    (away_team,)
                )
                away_team_id = cur.fetchone()[0]
            
            # Create new game
            game_id = uuid.uuid4()
            cur.execute(
                """
                INSERT INTO games (id, external_id, home_team_id, away_team_id, commence_time, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (external_id) DO UPDATE SET
                    home_team_id = EXCLUDED.home_team_id,
                    away_team_id = EXCLUDED.away_team_id,
                    commence_time = EXCLUDED.commence_time
                RETURNING id
                """,
                (
                    game_id,
                    external_id,
                    home_team_id,
                    away_team_id,
                    commence_time or datetime.now(timezone.utc),
                    datetime.now(timezone.utc),
                )
            )
            result = cur.fetchone()
            conn.commit()
            game_id = result[0] if result else game_id
            self.game_cache[external_id] = game_id
            return game_id

    def _parse_market(
        self, market: Dict[str, Any], home_team: str, away_team: str
    ) -> Optional[Dict[str, Any]]:
        """Parse a market into normalized odds fields."""
        market_key = market.get("key", "")
        outcomes = market.get("outcomes", [])
        
        # Only spreads/totals are supported
        if "spreads" in market_key:
            normalized_market = "spreads"
        elif "totals" in market_key:
            normalized_market = "totals"
        else:
            return None

        result = {
            "market_type": normalized_market,
            "period": self._get_period(market_key),
            "home_line": None,
            "away_line": None,
            "total_line": None,
            "home_price": None,
            "away_price": None,
            "over_price": None,
            "under_price": None,
        }
        
        # Parse based on market type
        if "spreads" in market_key:
            for outcome in outcomes:
                name = outcome.get("name", "")
                if name == home_team:
                    result["home_line"] = outcome.get("point")
                    result["home_price"] = outcome.get("price")
                elif name == away_team:
                    result["away_line"] = outcome.get("point")
                    result["away_price"] = outcome.get("price")
        elif "totals" in market_key:
            for outcome in outcomes:
                name = outcome.get("name", "").lower()
                if name == "over":
                    result["total_line"] = outcome.get("point")
                    result["over_price"] = outcome.get("price")
                elif name == "under":
                    result["under_price"] = outcome.get("price")

        return result

    def _get_period(self, market_key: str) -> str:
        """Determine period from market key."""
        if "_h1" in market_key:
            return "1h"  # Lowercase to match Rust service
        elif "_h2" in market_key:
            return "2h"
        return "full"

    def _store_snapshots(self, conn, snapshots: List[Dict[str, Any]]) -> int:
        """Store odds snapshots in the database."""
        if not snapshots:
            return 0
        
        with conn.cursor() as cur:
            sql = """
                INSERT INTO odds_snapshots (
                    time, game_id, bookmaker, market_type, period,
                    home_line, away_line, total_line,
                    home_price, away_price, over_price, under_price
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (time, game_id, bookmaker, market_type, period) DO UPDATE SET
                    home_line = EXCLUDED.home_line,
                    away_line = EXCLUDED.away_line,
                    total_line = EXCLUDED.total_line,
                    home_price = EXCLUDED.home_price,
                    away_price = EXCLUDED.away_price,
                    over_price = EXCLUDED.over_price,
                    under_price = EXCLUDED.under_price
            """
            
            data = [
                (
                    s["time"],
                    s["game_id"],
                    s["bookmaker"],
                    s["market_type"],
                    s["period"],
                    s["home_line"],
                    s["away_line"],
                    s["total_line"],
                    s["home_price"],
                    s["away_price"],
                    s["over_price"],
                    s["under_price"],
                )
                for s in snapshots
            ]
            
            execute_batch(cur, sql, data)
            conn.commit()
        
        return len(snapshots)

    def sync_full_game_odds(self) -> Tuple[int, int]:
        """Sync full-game odds. Returns (events_count, snapshots_count)."""
        print("    Fetching full-game odds...")
        events = self.client.get_odds_full()
        
        if not events:
            print("    No full-game odds events found")
            return 0, 0
        
        conn = self._get_connection()
        snapshots = []
        now = datetime.now(timezone.utc)
        
        try:
            for event in events:
                external_id = event.get("id", "")
                home_team = event.get("home_team", "")
                away_team = event.get("away_team", "")
                commence_time_str = event.get("commence_time")
                
                if not external_id or not home_team or not away_team:
                    continue
                
                commence_time = None
                if commence_time_str:
                    try:
                        commence_time = datetime.fromisoformat(
                            commence_time_str.replace("Z", "+00:00")
                        )
                    except ValueError:
                        pass
                
                game_id = self._get_or_create_game_id(
                    conn, external_id, home_team, away_team, commence_time
                )
                
                for bookmaker in event.get("bookmakers", []):
                    bookie_key = bookmaker.get("key", "")
                    
                    for market in bookmaker.get("markets", []):
                        parsed = self._parse_market(market, home_team, away_team)
                        if not parsed:
                            continue
                        
                        snapshots.append({
                            "time": now,
                            "game_id": game_id,
                            "bookmaker": bookie_key,
                            **parsed,
                        })
            
            stored = self._store_snapshots(conn, snapshots)
            print(f"    ✓ Full-game: {len(events)} events, {stored} snapshots")
            return len(events), stored
        finally:
            conn.close()

    def sync_h1_odds(self) -> Tuple[int, int]:
        """Sync first-half odds. Returns (events_count, snapshots_count)."""
        print("    Fetching 1H odds...")
        events = self.client.get_odds_h1()
        
        if not events:
            print("    No 1H odds events found")
            return 0, 0
        
        conn = self._get_connection()
        snapshots = []
        now = datetime.now(timezone.utc)
        
        try:
            for event in events:
                external_id = event.get("id", "")
                home_team = event.get("home_team", "")
                away_team = event.get("away_team", "")
                commence_time_str = event.get("commence_time")
                
                if not external_id or not home_team or not away_team:
                    continue
                
                commence_time = None
                if commence_time_str:
                    try:
                        commence_time = datetime.fromisoformat(
                            commence_time_str.replace("Z", "+00:00")
                        )
                    except ValueError:
                        pass
                
                game_id = self._get_or_create_game_id(
                    conn, external_id, home_team, away_team, commence_time
                )
                
                for bookmaker in event.get("bookmakers", []):
                    bookie_key = bookmaker.get("key", "")
                    
                    for market in bookmaker.get("markets", []):
                        parsed = self._parse_market(market, home_team, away_team)
                        if not parsed:
                            continue
                        
                        # Only store 1H markets
                        if parsed["period"] == "1h":
                            snapshots.append({
                                "time": now,
                                "game_id": game_id,
                                "bookmaker": bookie_key,
                                **parsed,
                            })
            
            stored = self._store_snapshots(conn, snapshots)
            print(f"    ✓ 1H: {len(events)} events, {stored} snapshots")
            return len(events), stored
        finally:
            conn.close()

    def sync_h2_odds(self) -> Tuple[int, int]:
        """Sync second-half odds. Returns (events_count, snapshots_count)."""
        print("    Fetching 2H odds...")
        events = self.client.get_odds_h2()
        
        if not events:
            print("    No 2H odds events found")
            return 0, 0
        
        conn = self._get_connection()
        snapshots = []
        now = datetime.now(timezone.utc)
        
        try:
            for event in events:
                external_id = event.get("id", "")
                home_team = event.get("home_team", "")
                away_team = event.get("away_team", "")
                commence_time_str = event.get("commence_time")
                
                if not external_id or not home_team or not away_team:
                    continue
                
                commence_time = None
                if commence_time_str:
                    try:
                        commence_time = datetime.fromisoformat(
                            commence_time_str.replace("Z", "+00:00")
                        )
                    except ValueError:
                        pass
                
                game_id = self._get_or_create_game_id(
                    conn, external_id, home_team, away_team, commence_time
                )
                
                for bookmaker in event.get("bookmakers", []):
                    bookie_key = bookmaker.get("key", "")
                    
                    for market in bookmaker.get("markets", []):
                        parsed = self._parse_market(market, home_team, away_team)
                        if not parsed:
                            continue
                        
                        # Only store 2H markets
                        if parsed["period"] == "2h":
                            snapshots.append({
                                "time": now,
                                "game_id": game_id,
                                "bookmaker": bookie_key,
                                **parsed,
                            })
            
            stored = self._store_snapshots(conn, snapshots)
            print(f"    ✓ 2H: {len(events)} events, {stored} snapshots")
            return len(events), stored
        finally:
            conn.close()

    def sync_all(self) -> Dict[str, Any]:
        """Sync all enabled odds types. Returns summary."""
        results = {
            "full": {"events": 0, "snapshots": 0},
            "h1": {"events": 0, "snapshots": 0},
            "h2": {"events": 0, "snapshots": 0},
            "total_events": 0,
            "total_snapshots": 0,
            "success": True,
            "error": None,
        }
        
        try:
            if self.enable_full:
                events, snaps = self.sync_full_game_odds()
                results["full"]["events"] = events
                results["full"]["snapshots"] = snaps
                results["total_events"] += events
                results["total_snapshots"] += snaps
            
            if self.enable_h1:
                events, snaps = self.sync_h1_odds()
                results["h1"]["events"] = events
                results["h1"]["snapshots"] = snaps
                results["total_events"] += events
                results["total_snapshots"] += snaps
            
            if self.enable_h2:
                events, snaps = self.sync_h2_odds()
                results["h2"]["events"] = events
                results["h2"]["snapshots"] = snaps
                results["total_events"] += events
                results["total_snapshots"] += snaps
        
        except Exception as e:
            results["success"] = False
            results["error"] = str(e)
            print(f"    ❌ Odds sync error: {e}")
        
        return results


def sync_odds(
    database_url: str,
    api_key: Optional[str] = None,
    enable_full: bool = True,
    enable_h1: bool = True,
    enable_h2: bool = False,
) -> Dict[str, Any]:
    """
    Convenience function to sync odds.
    
    Args:
        database_url: PostgreSQL connection URL
        api_key: The Odds API key (optional, will read from env/secrets)
        enable_full: Sync full-game odds
        enable_h1: Sync first-half odds
        enable_h2: Sync second-half odds
    
    Returns:
        Summary dict with results
    """
    service = OddsSyncService(
        database_url=database_url,
        api_key=api_key,
        enable_full=enable_full,
        enable_h1=enable_h1,
        enable_h2=enable_h2,
    )
    return service.sync_all()


if __name__ == "__main__":
    # CLI usage for testing
    import sys
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set")
        sys.exit(1)
    
    print("Starting odds sync...")
    result = sync_odds(db_url)
    
    print(f"\nResults:")
    print(f"  Full-game: {result['full']['events']} events, {result['full']['snapshots']} snapshots")
    print(f"  1H: {result['h1']['events']} events, {result['h1']['snapshots']} snapshots")
    print(f"  Total: {result['total_events']} events, {result['total_snapshots']} snapshots")
    
    if not result["success"]:
        print(f"  Error: {result['error']}")
        sys.exit(1)
