import json
import os
from typing import Dict

from .odds_api_client import OddsApiClient, OddsApiError


def main() -> int:
    client = OddsApiClient()

    summary: Dict[str, int] = {
        "events": 0,
        "full_game_events": 0,
        "h1_events": 0,
        "h2_events": 0,
    }

    try:
        events = client.get_events()
        summary["events"] = len(events)

        full = client.get_odds_full()
        summary["full_game_events"] = len(full)

        h1 = client.get_odds_h1()
        summary["h1_events"] = len(h1)

        h2 = client.get_odds_h2()
        summary["h2_events"] = len(h2)

        print("\nNCAAM Odds Pull Summary:")
        print(f"  Events listed:       {summary['events']}")
        print(f"  Full-game odds:      {summary['full_game_events']}")
        print(f"  First-half odds:     {summary['h1_events']}")
        print(f"  Second-half odds:    {summary['h2_events']}")

        # Optional: persist a dry-run snapshot for inspection
        out_dir = os.getenv("ODDS_PULL_OUT", "output/tmp_odds_pull")
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "events.json"), "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2)
        with open(os.path.join(out_dir, "full_game.json"), "w", encoding="utf-8") as f:
            json.dump(full, f, indent=2)
        with open(os.path.join(out_dir, "first_half.json"), "w", encoding="utf-8") as f:
            json.dump(h1, f, indent=2)
        with open(os.path.join(out_dir, "second_half.json"), "w", encoding="utf-8") as f:
            json.dump(h2, f, indent=2)

        print(f"\nSaved dry-run output to: {out_dir}")
        return 0

    except OddsApiError as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
