#!/usr/bin/env python3
"""
Export team aliases from database for ML training.

This uses our established 98%+ team matching system.
"""
import json
import os
import sys
from pathlib import Path

# Try database connection
try:
    from sqlalchemy import create_engine, text
    
    # Build connection
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        db_host = os.environ.get("DB_HOST", "localhost")
        db_port = os.environ.get("DB_PORT", "5450")
        db_user = os.environ.get("DB_USER", "ncaam")
        db_name = os.environ.get("DB_NAME", "ncaam")
        db_pass = os.environ.get("DB_PASSWORD", "ncaam")
        
        # Try secrets file
        pw_file = Path("/run/secrets/db_password")
        if pw_file.exists():
            db_pass = pw_file.read_text().strip()
        
        db_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    
    engine = create_engine(db_url, pool_pre_ping=True)
    HAS_DB = True
except Exception as e:
    print(f"Database not available: {e}")
    HAS_DB = False


def export_aliases_from_db(output_path: Path):
    """Export team aliases from database."""
    if not HAS_DB:
        print("Database not available")
        return None
    
    aliases = {}  # alias -> canonical_name
    
    with engine.connect() as conn:
        # Get all teams with their canonical names
        result = conn.execute(text("""
            SELECT t.canonical_name, ta.alias
            FROM teams t
            JOIN team_aliases ta ON t.id = ta.team_id
            ORDER BY t.canonical_name
        """))
        
        for row in result:
            canonical = row.canonical_name
            alias = row.alias.lower().strip()
            aliases[alias] = canonical
        
        # Also add canonical names as aliases (exact match)
        result = conn.execute(text("SELECT canonical_name FROM teams"))
        for row in result:
            canonical = row.canonical_name
            aliases[canonical.lower().strip()] = canonical
        
        print(f"Exported {len(aliases)} aliases from database")
    
    # Save to file
    with open(output_path, 'w') as f:
        json.dump(aliases, f, indent=2, sort_keys=True)
    
    print(f"Saved to {output_path}")
    return aliases


def create_hardcoded_aliases() -> dict:
    """
    Create hardcoded alias mapping for common Basketball API -> Barttorvik variants.
    This is a fallback when database is not available.
    """
    # Based on migration 011 and common variants
    return {
        # Major programs
        "uconn": "Connecticut",
        "uconn huskies": "Connecticut",
        "connecticut huskies": "Connecticut",
        "ole miss": "Mississippi",
        "ole miss rebels": "Mississippi",
        "brigham young": "BYU",
        "brigham young cougars": "BYU",
        "st. marys (ca)": "St. Mary's",
        "st. mary's (ca)": "St. Mary's",
        "st marys (ca)": "St. Mary's",
        "saint marys": "St. Mary's",
        "saint mary's": "St. Mary's",
        "miami (fl)": "Miami FL",
        "miami hurricanes": "Miami FL",
        "miami fl": "Miami FL",
        
        # California schools
        "cs northridge": "Cal St. Northridge",
        "cal st northridge": "Cal St. Northridge",
        "csun": "Cal St. Northridge",
        "cs fullerton": "Cal St. Fullerton",
        "cal st fullerton": "Cal St. Fullerton",
        "csu bakersfield": "Cal St. Bakersfield",
        "cs bakersfield": "Cal St. Bakersfield",
        
        # Texas schools
        "utrgv": "UT Rio Grande Valley",
        "ut rio grande valley": "UT Rio Grande Valley",
        "ualr": "Little Rock",
        "arkansas little rock": "Little Rock",
        
        # Other common variants
        "ipfw": "Purdue Fort Wayne",
        "purdue-fort wayne": "Purdue Fort Wayne",
        "n. carolina a&t": "North Carolina A&T",
        "n carolina a&t": "North Carolina A&T",
        "nc a&t": "North Carolina A&T",
        "n. carolina central": "North Carolina Central",
        "n carolina central": "North Carolina Central",
        "nccu": "North Carolina Central",
        "miss. valley st.": "Mississippi Valley St.",
        "mississippi valley st.": "Mississippi Valley St.",
        "mississippi valley state": "Mississippi Valley St.",
        "middle tenn. st.": "Middle Tennessee",
        "middle tenn st": "Middle Tennessee",
        "middle tennessee state": "Middle Tennessee",
        "mtsu": "Middle Tennessee",
        
        # UNC system
        "unc": "North Carolina",
        "north carolina tar heels": "North Carolina",
        "unc-wilmington": "UNC Wilmington",
        "unc wilmington": "UNC Wilmington",
        "uncw": "UNC Wilmington",
        "unc-greensboro": "UNC Greensboro",
        "unc greensboro": "UNC Greensboro",
        "uncg": "UNC Greensboro",
        "unc-asheville": "UNC Asheville",
        "unc asheville": "UNC Asheville",
        "unca": "UNC Asheville",
        
        # More common aliases
        "lsu": "LSU",
        "louisiana state": "LSU",
        "louisiana st": "LSU",
        "lsu tigers": "LSU",
        "usc": "USC",
        "southern california": "USC",
        "usc trojans": "USC",
        "ucla": "UCLA",
        "ucla bruins": "UCLA",
        "unlv": "UNLV",
        "unlv rebels": "UNLV",
        "utep": "UTEP",
        "utep miners": "UTEP",
        "vcu": "VCU",
        "vcu rams": "VCU",
        "virginia commonwealth": "VCU",
        "smu": "SMU",
        "smu mustangs": "SMU",
        "southern methodist": "SMU",
        "tcu": "TCU",
        "tcu horned frogs": "TCU",
        "texas christian": "TCU",
        "ucf": "UCF",
        "ucf knights": "UCF",
        "central florida": "UCF",
        "uab": "UAB",
        "uab blazers": "UAB",
        "alabama-birmingham": "UAB",
        "usf": "South Florida",
        "south florida bulls": "South Florida",
        "fau": "FAU",
        "fau owls": "FAU",
        "florida atlantic": "FAU",
        "fiu": "FIU",
        "fiu panthers": "FIU",
        "florida international": "FIU",
        
        # State abbreviations
        "pitt": "Pittsburgh",
        "pitt panthers": "Pittsburgh",
        "cuse": "Syracuse",
        "syracuse orange": "Syracuse",
        "uva": "Virginia",
        "virginia cavaliers": "Virginia",
        "duke blue devils": "Duke",
        "unc tar heels": "North Carolina",
        "wake forest demon deacons": "Wake Forest",
        "nc state wolfpack": "NC State",
        "n.c. state": "NC State",
        "florida state": "Florida St.",
        "florida st": "Florida St.",
        "fsu": "Florida St.",
        "ohio state": "Ohio St.",
        "ohio st": "Ohio St.",
        "michigan state": "Michigan St.",
        "michigan st": "Michigan St.",
        "penn state": "Penn St.",
        "penn st": "Penn St.",
        "iowa state": "Iowa St.",
        "iowa st": "Iowa St.",
        "kansas state": "Kansas St.",
        "kansas st": "Kansas St.",
        "oklahoma state": "Oklahoma St.",
        "oklahoma st": "Oklahoma St.",
        "oregon state": "Oregon St.",
        "oregon st": "Oregon St.",
        "washington state": "Washington St.",
        "washington st": "Washington St.",
        "arizona state": "Arizona St.",
        "arizona st": "Arizona St.",
        "colorado state": "Colorado St.",
        "colorado st": "Colorado St.",
        "san diego state": "San Diego St.",
        "san diego st": "San Diego St.",
        "sdsu": "San Diego St.",
        "boise state": "Boise St.",
        "boise st": "Boise St.",
        "fresno state": "Fresno St.",
        "fresno st": "Fresno St.",
        "utah state": "Utah St.",
        "utah st": "Utah St.",
        
        # Conference oddities
        "gonzaga": "Gonzaga",
        "gonzaga bulldogs": "Gonzaga",
        "zags": "Gonzaga",
        "villanova": "Villanova",
        "villanova wildcats": "Villanova",
        "nova": "Villanova",
        "memphis": "Memphis",
        "memphis tigers": "Memphis",
        "xavier": "Xavier",
        "xavier musketeers": "Xavier",
        "creighton": "Creighton",
        "creighton bluejays": "Creighton",
        "marquette": "Marquette",
        "marquette golden eagles": "Marquette",
        
        # SEC
        "auburn": "Auburn",
        "auburn tigers": "Auburn",
        "alabama": "Alabama",
        "alabama crimson tide": "Alabama",
        "kentucky": "Kentucky",
        "kentucky wildcats": "Kentucky",
        "tennessee": "Tennessee",
        "tennessee volunteers": "Tennessee",
        "florida": "Florida",
        "florida gators": "Florida",
        "georgia": "Georgia",
        "georgia bulldogs": "Georgia",
        "arkansas": "Arkansas",
        "arkansas razorbacks": "Arkansas",
        "texas a&m": "Texas A&M",
        "texas a&m aggies": "Texas A&M",
        "tamu": "Texas A&M",
        
        # Big Ten
        "michigan": "Michigan",
        "michigan wolverines": "Michigan",
        "purdue": "Purdue",
        "purdue boilermakers": "Purdue",
        "indiana": "Indiana",
        "indiana hoosiers": "Indiana",
        "illinois": "Illinois",
        "illinois fighting illini": "Illinois",
        "wisconsin": "Wisconsin",
        "wisconsin badgers": "Wisconsin",
        "iowa": "Iowa",
        "iowa hawkeyes": "Iowa",
        "minnesota": "Minnesota",
        "minnesota golden gophers": "Minnesota",
        "northwestern": "Northwestern",
        "northwestern wildcats": "Northwestern",
        "nebraska": "Nebraska",
        "nebraska cornhuskers": "Nebraska",
        "maryland": "Maryland",
        "maryland terrapins": "Maryland",
        "rutgers": "Rutgers",
        "rutgers scarlet knights": "Rutgers",
        
        # Big 12
        "kansas": "Kansas",
        "kansas jayhawks": "Kansas",
        "ku": "Kansas",
        "texas": "Texas",
        "texas longhorns": "Texas",
        "baylor": "Baylor",
        "baylor bears": "Baylor",
        "houston": "Houston",
        "houston cougars": "Houston",
        "cincinnati": "Cincinnati",
        "cincinnati bearcats": "Cincinnati",
        "west virginia": "West Virginia",
        "west virginia mountaineers": "West Virginia",
        "wvu": "West Virginia",
    }


def main():
    output_dir = Path(__file__).parent.parent / "training_data"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / "team_aliases.json"
    
    print("=" * 60)
    print("Team Alias Export")
    print("=" * 60)
    
    # Try database first
    if HAS_DB:
        try:
            aliases = export_aliases_from_db(output_path)
            if aliases:
                return
        except Exception as e:
            print(f"Database export failed: {e}")
    
    # Fallback to hardcoded
    print("\nUsing hardcoded aliases...")
    aliases = create_hardcoded_aliases()
    
    with open(output_path, 'w') as f:
        json.dump(aliases, f, indent=2, sort_keys=True)
    
    print(f"Saved {len(aliases)} aliases to {output_path}")


if __name__ == "__main__":
    main()
