
import sys
import os
import csv
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
import structlog

# Add project root and service root to path
ROOT_DIR = Path(os.getcwd())
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "services" / "prediction-service-python"))

from testing.production_parity.roi_simulator import ROISimulator, BetResult, ROIResults
from app.prediction_engine_v33 import PredictionEngineV33
from app.models import TeamRatings, MarketOdds, BetType, Pick

class MLROISimulator(ROISimulator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print("Initializing PredictionEngineV33 with ML models...")
        self.engine = PredictionEngineV33(use_ml_models=True)
        # RELAX FILTERS FOR BACKTESTING
        self.engine.config.min_confidence = 0.50 # Allow all > 50%
        self.engine.config.min_ev_percent = 0.0
        self.engine.config.min_prob_edge = 0.0
        self.engine.config.kelly_fraction = 0.25

        
    def _to_market_odds(self, odds_record, game_id) -> MarketOdds:
        """Convert OddsRecord to MarketOdds."""
        return MarketOdds(
            game_id=game_id,
            bookmaker=odds_record.bookmaker,
            timestamp=odds_record.timestamp or datetime.now(),
            spread=odds_record.spread,
            spread_price=-110, # Assumption
            total=odds_record.total,
            over_price=-110,
            under_price=-110,
            spread_1h=odds_record.h1_spread,
            spread_price_1h=-110,
            total_1h=odds_record.h1_total,
            over_price_1h=-110,
            under_price_1h=-110,
            # No sharp lines in basic history usually, unless we have them
            # For backtest, we might lack sharp lines so sharp-alignment will be skipped/neutral
        )

    def simulate_season_ml(self, season: int) -> Dict[str, ROIResults]:
        """Run simulation using the Production Engine (ML + Analytical)."""
        print(f"Loading games for season {season}...")
        full_games = self._load_full_games(season)
        # full_games = full_games[:50] # DEBUG: Limit games
        h1_games = self._load_h1_games(season)
        
        # We need to test specific Bet Types
        bet_results = {
            "FGSpread": [], "FGTotal": [], "H1Spread": [], "H1Total": []
        }
        
        # Create a map for H1 scores
        h1_map = {}
        for g in h1_games:
            key = f"{g['home_team']}|{g['away_team']}|{g['date']}"
            h1_map[key] = g

        print(f"Simulating {len(full_games)} games...")
        print("Applying ROBUST PREDICTION CANONICAL TEAM Filter (ProductionTeamResolver)...")
        
        stats = {"total": 0, "resolved": 0, "unresolved": 0, "no_ratings": 0, "simulated": 0}

        for row in full_games:
            stats["total"] += 1
            if stats["total"] % 100 == 0:
                print(f"Processed {stats['total']} games...", end="\r", flush=True)

            game_date = row.get("date")
            home_raw = row.get("home_team")
            away_raw = row.get("away_team")
            home_score = row.get("home_score")
            away_score = row.get("away_score")
            
            # Resolve - logic borrowed from ROI Simulator but simplified
            h_res = self.team_resolver.resolve(home_raw)
            a_res = self.team_resolver.resolve(away_raw)
            if not h_res.resolved or not a_res.resolved:
                stats["unresolved"] += 1
                # Optional: print unresolved for debugging
                # print(f"Unresolved: {home_raw} or {away_raw}")
                continue
            
            stats["resolved"] += 1
            home_can = h_res.canonical_name
            away_can = a_res.canonical_name
            
            # Ratings
            ratings_lookup_h = self.ratings_loader.get_ratings_for_game(home_can, game_date)
            ratings_lookup_a = self.ratings_loader.get_ratings_for_game(away_can, game_date)
            
            if not ratings_lookup_h.found or not ratings_lookup_a.found:
                stats["no_ratings"] += 1
                continue

                
            # Convert to App TeamRatings (pydantic)
            tr_h = self._to_app_ratings(ratings_lookup_h.ratings)
            tr_a = self._to_app_ratings(ratings_lookup_a.ratings)
            
            # Find Odds
            # Try FG markets
            odds_rec = self.find_odds_for_market(home_can, away_can, game_date, "fg_spread")
            # If valid odds found
            if odds_rec:
                market_odds = self._to_market_odds(odds_rec, row.get("game_id"))
                
                # PREDICTION
                try:
                    pred = self.engine.make_prediction(
                        game_id=row.get("game_id"),
                        home_team=home_can,
                        away_team=away_can,
                        commence_time=datetime.now(), # Dummy time
                        home_ratings=tr_h,
                        away_ratings=tr_a,
                        market_odds=market_odds
                    )
                    
                    recs = self.engine.generate_recommendations(
                        prediction=pred, 
                        market_odds=market_odds,
                        home_ratings=tr_h,
                        away_ratings=tr_a
                    )
                    
                    # Evaluate Recommendations
                    self._evaluate_recs(recs, row, h1_map, bet_results, home_can, away_can, game_date)
                    
                except Exception as e:
                    # Ignore occasional errors
                    pass
                    
        # Summarize
        summary = {}
        for model in bet_results:
            results = bet_results[model]
            if not results:
                continue
            
            wins = sum(1 for r in results if r['won'])
            total = len(results)
            units = sum(r['units_won'] for r in results)
            roi = units / total if total > 0 else 0
            
            print(f"{model}: {wins}/{total} ({wins/total:.1%}) Units: {units:.2f} ROI: {roi:.1%}")
            summary[model] = results
            
        return summary

    def _to_app_ratings(self, r):
        # Convert internal loader ratings to App Model TeamRatings
        return TeamRatings(
            team_name=r.team_name,
            adj_o=r.adj_o, adj_d=r.adj_d, tempo=r.tempo, rank=r.rank,
            efg=r.efg, efgd=r.efgd, tor=r.tor, tord=r.tord,
            orb=r.orb, drb=r.drb, ftr=r.ftr, ftrd=r.ftrd,
            two_pt_pct=r.two_pt_pct, two_pt_pct_d=r.two_pt_pct_d,
            three_pt_pct=r.three_pt_pct, three_pt_pct_d=r.three_pt_pct_d,
            three_pt_rate=r.three_pt_rate, three_pt_rate_d=r.three_pt_rate_d,
            barthag=r.barthag, wab=0.0
        )

    def _evaluate_recs(self, recs, full_row, h1_map, bet_results, home, away, date):
        # Result logic
        fg_home = self._parse_int(full_row.get("home_score"))
        fg_away = self._parse_int(full_row.get("away_score"))
        
        # H1 scores if available
        h1_row = h1_map.get(f"{home}|{away}|{date}")
        h1_home = None
        h1_away = None
        if h1_row:
             # Try mapped names often used in H1 files
             # NOTE: Check if roi_simulator loading logic differs
             # The _load_h1_games in roi_simulator maps column 'home_fg' etc.
             # In data structure it is h1_home/h1_away
             h1_home = h1_row.get("h1_home")
             h1_away = h1_row.get("h1_away")
        else:
             # Maybe full_row has them?
             # prepare_backtest mapped them to home_h1 / away_h1?
             # Wait, in the CSV diagnostics earlier, games_2024 has home_h1/away_h1
             # roi_simulator _load_full_games maps them to h1_home/h1_away dict keys!
             h1_home = full_row.get("h1_home")
             h1_away = full_row.get("h1_away")

        for rec in recs:
            won = False
            units = -1.1 # Default risk 1.1 to win 1? Or 1 to win 0.90?
            # Recommendation engine assumes betting to win? 
            # Usually flat unit.
            # Let's assume standard -110 juice (risk 1.1 to win 1.0)
            risk = 1.1
            win_amt = 1.0
            
            if rec.bet_type == BetType.SPREAD:
                if fg_home is None or fg_away is None: continue
                margin = fg_home - fg_away
                # Rec pick is enum.
                # If PICK=HOME, we win if margin + spread > 0
                # rec.line is the spread FROM THE PICK PERSPECTIVE?
                # PredictionEngine: "bet_line = market_line if pick == Pick.HOME else -market_line"
                # So if Home -5, bet_line is -5.
                # If Away +5, bet_line is +5. (Market is -5 home. Away line is +5).
                
                # Check cover
                # Margin (Home-Away) + Line (Home perspective) > 0?
                # If Pick Home (Line -5): Margin (6) + (-5) = 1 > 0. Win.
                # If Pick Away (Line +5): Margin (-6) + 5 = -1 < 0. Loss.
                
                # We need the line from the perspective of the pick.
                # rec.line IS that.
                
                # Margin must be aligned to pick.
                # If Pick=Home, margin = Home - Away
                # If Pick=Away, margin = Away - Home
                
                p_margin = (fg_home - fg_away) if rec.pick == Pick.HOME else (fg_away - fg_home)
                if (p_margin + rec.line) > 0:
                    won = True
                elif (p_margin + rec.line) == 0:
                    continue # Push
                    
                bet_results["FGSpread"].append({"won": won, "units_won": win_amt if won else -risk, "rec": rec})
                
            elif rec.bet_type == BetType.TOTAL:
                if fg_home is None or fg_away is None: continue
                total = fg_home + fg_away
                if rec.pick == Pick.OVER:
                    won = total > rec.line
                else:
                    won = total < rec.line
                if total == rec.line: continue
                bet_results["FGTotal"].append({"won": won, "units_won": win_amt if won else -risk, "rec": rec})
                
            elif rec.bet_type == BetType.SPREAD_1H:
                if h1_home is None or h1_away is None: continue
                p_margin = (h1_home - h1_away) if rec.pick == Pick.HOME else (h1_away - h1_home)
                if (p_margin + rec.line) > 0:
                    won = True
                elif (p_margin + rec.line) == 0:
                     continue
                bet_results["H1Spread"].append({"won": won, "units_won": win_amt if won else -risk, "rec": rec})

            elif rec.bet_type == BetType.TOTAL_1H:
                if h1_home is None or h1_away is None: continue
                total = h1_home + h1_away
                if rec.pick == Pick.OVER:
                    won = total > rec.line
                else:
                    won = total < rec.line
                if total == rec.line: continue
                bet_results["H1Total"].append({"won": won, "units_won": win_amt if won else -risk, "rec": rec})

        # --- Stats & Results ---
        print("\n=== Robust Prediction Canonical Team Filter Report ===")
        print(f"Total Games Processed: {stats['total']}")
        if stats['total'] > 0:
            print(f"Successfully Resolved: {stats['resolved']} ({stats['resolved']/stats['total']:.1%} coverage)")
        print(f"Unresolved (Filtered): {stats['unresolved']}")
        print(f"Missing Ratings:       {stats['no_ratings']}")
        print("===================================================\n")
        
        print(f"=== ML Backtest Results ({season}) ===")
        for btype, res in bet_results.items():
            if not res:
                print(f"{btype}: No bets.")
                continue
            wins = sum(1 for r in res if r['won'])
            total = len(res)
            units = sum(r['units_won'] for r in res)
            risk_amt = total * 1.1 # Approx
            roi = (units / risk_amt) * 100 if risk_amt > 0 else 0
            print(f"{btype}: {wins}/{total} ({wins/total:.1%}) | Units: {units:+.2f} | ROI: {roi:+.1f}%")
        
        return bet_results

if __name__ == "__main__":
    season = 2024
    if len(sys.argv) > 1:
        season = int(sys.argv[1])
    
    sim = MLROISimulator()
    sim.simulate_season_ml(season)
