"""
HISTORICAL DATA CANONICALIZATION PIPELINE

This script applies the production team resolver to all raw historical data
to create properly canonicalized datasets ready for backtesting.

SAFETY FEATURES:
- Never overwrites source data (creates new files)
- Full audit trail of every resolution
- Validation report before/after
- Dry-run mode by default
- Unresolved teams are logged, not silently dropped

Usage:
    # Dry run (validate only, no writes)
    python testing/scripts/canonicalize_historical_data.py --dry-run

    # Full run with output
    python testing/scripts/canonicalize_historical_data.py --execute

    # Validate existing canonical data
    python testing/scripts/canonicalize_historical_data.py --validate-only
"""

import argparse
import json
import pandas as pd
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Set, Tuple
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from testing.data_paths import DATA_PATHS
from testing.production_parity import ProductionTeamResolver, ResolutionStep


@dataclass
class ResolutionAudit:
    """Audit record for a single team name resolution."""
    source: str           # 'odds', 'scores', 'barttorvik'
    original_name: str
    resolved_name: Optional[str]
    step_used: str        # canonical, alias, normalized, mascot, unresolved
    matched_via: Optional[str]


@dataclass  
class ValidationReport:
    """Summary of canonicalization validation."""
    timestamp: str
    source: str
    total_rows: int
    unique_input_teams: int
    resolved_teams: int
    unresolved_teams: int
    resolution_by_step: Dict[str, int]
    unresolved_list: List[str]
    sample_resolutions: List[Dict]
    match_rate: float


class CanonicalPipeline:
    """Pipeline for canonicalizing historical data."""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.resolver = ProductionTeamResolver()
        self.audits: List[ResolutionAudit] = []
        self.reports: List[ValidationReport] = []
        
        # Output directories
        self.output_root = DATA_PATHS.root / "canonicalized"
        self.audit_dir = DATA_PATHS.root / "canonicalization_audit"
        
    def _resolve_with_audit(self, name: str, source: str) -> Optional[str]:
        """Resolve team name and record audit."""
        if pd.isna(name) or not str(name).strip():
            return None
            
        result = self.resolver.resolve(str(name).strip())
        
        self.audits.append(ResolutionAudit(
            source=source,
            original_name=str(name),
            resolved_name=result.canonical_name,
            step_used=result.step_used.value,
            matched_via=result.matched_via,
        ))
        
        return result.canonical_name
    
    def _generate_report(self, source: str, df: pd.DataFrame, 
                         team_cols: List[str]) -> ValidationReport:
        """Generate validation report for a dataset."""
        
        # Collect all team names
        all_teams = set()
        for col in team_cols:
            all_teams.update(df[col].dropna().unique())
        
        # Track resolutions
        resolved = set()
        unresolved = set()
        by_step = defaultdict(int)
        samples = []
        
        for team in all_teams:
            result = self.resolver.resolve(str(team))
            by_step[result.step_used.value] += 1
            
            if result.resolved:
                resolved.add(result.canonical_name)
                if len(samples) < 20:
                    samples.append({
                        'input': team,
                        'output': result.canonical_name,
                        'step': result.step_used.value,
                    })
            else:
                unresolved.add(team)
        
        return ValidationReport(
            timestamp=datetime.now().isoformat(),
            source=source,
            total_rows=len(df),
            unique_input_teams=len(all_teams),
            resolved_teams=len(resolved),
            unresolved_teams=len(unresolved),
            resolution_by_step=dict(by_step),
            unresolved_list=sorted(unresolved),
            sample_resolutions=samples,
            match_rate=100 * len(resolved) / len(all_teams) if all_teams else 0,
        )
    
    def validate_scores(self) -> ValidationReport:
        """Validate scores data resolution."""
        print("\n" + "="*70)
        print("VALIDATING: ESPN Scores")
        print("="*70)
        
        scores_file = DATA_PATHS.scores_fg / "games_all.csv"
        if not scores_file.exists():
            print(f"  ERROR: File not found: {scores_file}")
            return None
            
        df = pd.read_csv(scores_file)
        report = self._generate_report("espn_scores", df, ["home_team", "away_team"])
        
        print(f"\n  Total games:        {report.total_rows:,}")
        print(f"  Unique teams:       {report.unique_input_teams}")
        print(f"  Resolved:           {report.resolved_teams} ({report.match_rate:.1f}%)")
        print(f"  Unresolved:         {report.unresolved_teams}")
        
        print(f"\n  Resolution by step:")
        for step, count in sorted(report.resolution_by_step.items()):
            print(f"    {step:15}: {count}")
        
        if report.unresolved_list:
            print(f"\n  Unresolved teams (first 20):")
            for team in report.unresolved_list[:20]:
                print(f"    - {team}")
        
        self.reports.append(report)
        return report
    
    def validate_odds(self) -> ValidationReport:
        """Validate odds data resolution."""
        print("\n" + "="*70)
        print("VALIDATING: Odds (spreads/fg)")
        print("="*70)
        
        # Check current "canonical" folder
        odds_file = DATA_PATHS.odds_canonical_spreads_fg / "spreads_fg_all.csv"
        if not odds_file.exists():
            print(f"  ERROR: File not found: {odds_file}")
            return None
            
        df = pd.read_csv(odds_file)
        
        # Note: current files have 'home_team_canonical' but it's NOT actually canonical
        team_cols = ["home_team_canonical", "away_team_canonical"]
        if "home_team_canonical" not in df.columns:
            team_cols = ["home_team", "away_team"]
            
        report = self._generate_report("odds_api", df, team_cols)
        
        print(f"\n  Total rows:         {report.total_rows:,}")
        print(f"  Unique teams:       {report.unique_input_teams}")
        print(f"  Resolved:           {report.resolved_teams} ({report.match_rate:.1f}%)")
        print(f"  Unresolved:         {report.unresolved_teams}")
        
        print(f"\n  Resolution by step:")
        for step, count in sorted(report.resolution_by_step.items()):
            print(f"    {step:15}: {count}")
            
        self.reports.append(report)
        return report
    
    def validate_barttorvik(self) -> ValidationReport:
        """Validate Barttorvik data resolution."""
        print("\n" + "="*70)
        print("VALIDATING: Barttorvik Ratings")
        print("="*70)
        
        all_teams = set()
        total_rows = 0
        
        for json_file in DATA_PATHS.ratings_raw_barttorvik.glob("barttorvik_*.json"):
            with open(json_file) as f:
                data = json.load(f)
                total_rows += len(data)
                for row in data:
                    if isinstance(row, list) and len(row) > 1:
                        all_teams.add(str(row[1]))
        
        # Track resolutions
        resolved = set()
        unresolved = set()
        by_step = defaultdict(int)
        
        for team in all_teams:
            result = self.resolver.resolve(team)
            by_step[result.step_used.value] += 1
            
            if result.resolved:
                resolved.add(result.canonical_name)
            else:
                unresolved.add(team)
        
        report = ValidationReport(
            timestamp=datetime.now().isoformat(),
            source="barttorvik",
            total_rows=total_rows,
            unique_input_teams=len(all_teams),
            resolved_teams=len(resolved),
            unresolved_teams=len(unresolved),
            resolution_by_step=dict(by_step),
            unresolved_list=sorted(unresolved),
            sample_resolutions=[],
            match_rate=100 * len(resolved) / len(all_teams) if all_teams else 0,
        )
        
        print(f"\n  Total rows:         {report.total_rows:,}")
        print(f"  Unique teams:       {report.unique_input_teams}")
        print(f"  Resolved:           {report.resolved_teams} ({report.match_rate:.1f}%)")
        print(f"  Unresolved:         {report.unresolved_teams}")
        
        print(f"\n  Resolution by step:")
        for step, count in sorted(report.resolution_by_step.items()):
            print(f"    {step:15}: {count}")
            
        if report.unresolved_list:
            print(f"\n  Unresolved teams:")
            for team in report.unresolved_list:
                print(f"    - {team}")
        
        self.reports.append(report)
        return report
    
    def cross_validate(self) -> Dict:
        """Cross-validate that resolved names match across sources."""
        print("\n" + "="*70)
        print("CROSS-SOURCE VALIDATION")
        print("="*70)
        
        # Get resolved teams from each source
        sources = {}
        
        # Scores
        scores_file = DATA_PATHS.scores_fg / "games_all.csv"
        if scores_file.exists():
            df = pd.read_csv(scores_file)
            teams = set(df['home_team'].unique()) | set(df['away_team'].unique())
            resolved = {self.resolver.resolve(t).canonical_name for t in teams 
                       if self.resolver.resolve(t).resolved}
            sources['scores'] = resolved
            
        # Odds
        odds_file = DATA_PATHS.odds_canonical_spreads_fg / "spreads_fg_all.csv"
        if odds_file.exists():
            df = pd.read_csv(odds_file)
            col = 'home_team_canonical' if 'home_team_canonical' in df.columns else 'home_team'
            teams = set(df[col].unique()) | set(df[col.replace('home', 'away')].unique())
            resolved = {self.resolver.resolve(str(t)).canonical_name for t in teams 
                       if self.resolver.resolve(str(t)).resolved}
            sources['odds'] = resolved
            
        # Barttorvik
        bart_teams = set()
        for json_file in DATA_PATHS.ratings_raw_barttorvik.glob("barttorvik_*.json"):
            with open(json_file) as f:
                for row in json.load(f):
                    if isinstance(row, list) and len(row) > 1:
                        bart_teams.add(str(row[1]))
        resolved = {self.resolver.resolve(t).canonical_name for t in bart_teams 
                   if self.resolver.resolve(t).resolved}
        sources['barttorvik'] = resolved
        
        # Compare
        print(f"\n  Resolved teams by source:")
        for name, teams in sources.items():
            print(f"    {name:15}: {len(teams)} teams")
        
        if 'scores' in sources and 'odds' in sources:
            common = sources['scores'] & sources['odds']
            scores_only = sources['scores'] - sources['odds']
            odds_only = sources['odds'] - sources['scores']
            
            print(f"\n  Scores ∩ Odds:")
            print(f"    Common:           {len(common)} teams")
            print(f"    Only in scores:   {len(scores_only)} teams")
            print(f"    Only in odds:     {len(odds_only)} teams")
            
            if scores_only:
                print(f"\n    Scores-only teams (for info):")
                for t in sorted(scores_only)[:10]:
                    print(f"      - {t}")
                    
            if odds_only:
                print(f"\n    Odds-only teams (for info):")
                for t in sorted(odds_only)[:10]:
                    print(f"      - {t}")
        
        return sources
    
    def canonicalize_scores(self) -> Optional[Path]:
        """Canonicalize scores data."""
        print("\n" + "="*70)
        print("CANONICALIZING: ESPN Scores")
        print("="*70)
        
        scores_file = DATA_PATHS.scores_fg / "games_all.csv"
        df = pd.read_csv(scores_file)
        
        print(f"\n  Input: {scores_file}")
        print(f"  Rows: {len(df):,}")
        
        # Apply resolver
        print("  Resolving team names...")
        df['home_canonical'] = df['home_team'].apply(
            lambda x: self._resolve_with_audit(x, 'scores'))
        df['away_canonical'] = df['away_team'].apply(
            lambda x: self._resolve_with_audit(x, 'scores'))
        
        # Filter to D1 only
        d1_mask = df['home_canonical'].notna() & df['away_canonical'].notna()
        df_d1 = df[d1_mask].copy()
        
        print(f"  D1 games: {len(df_d1):,} ({100*len(df_d1)/len(df):.1f}%)")
        print(f"  Filtered out: {len(df) - len(df_d1)} non-D1 games")
        
        # Output
        if self.dry_run:
            print("\n  [DRY RUN] Would write to:")
            output_file = self.output_root / "scores" / "fg" / "games_all_canonical.csv"
            print(f"    {output_file}")
            return None
        else:
            output_dir = self.output_root / "scores" / "fg"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / "games_all_canonical.csv"
            df_d1.to_csv(output_file, index=False)
            print(f"\n  Written: {output_file}")
            print(f"  Size: {output_file.stat().st_size / 1024:.1f} KB")
            return output_file
    
    def canonicalize_h1_scores(self) -> Optional[Path]:
        """Canonicalize H1 scores data."""
        print("\n" + "="*70)
        print("CANONICALIZING: ESPN H1 Scores")
        print("="*70)
        
        h1_file = DATA_PATHS.scores_h1 / "h1_games_all.csv"
        if not h1_file.exists():
            print(f"  SKIPPED: {h1_file} not found")
            return None
            
        df = pd.read_csv(h1_file)
        
        print(f"\n  Input: {h1_file}")
        print(f"  Rows: {len(df):,}")
        
        # Apply resolver
        print("  Resolving team names...")
        df['home_canonical'] = df['home_team'].apply(
            lambda x: self._resolve_with_audit(x, 'h1_scores'))
        df['away_canonical'] = df['away_team'].apply(
            lambda x: self._resolve_with_audit(x, 'h1_scores'))
        
        # Filter to D1 only
        d1_mask = df['home_canonical'].notna() & df['away_canonical'].notna()
        df_d1 = df[d1_mask].copy()
        
        print(f"  D1 games: {len(df_d1):,} ({100*len(df_d1)/len(df):.1f}%)")
        print(f"  Filtered out: {len(df) - len(df_d1)} non-D1 games")
        
        # Output
        if self.dry_run:
            print("\n  [DRY RUN] Would write to:")
            output_file = self.output_root / "scores" / "h1" / "h1_games_all_canonical.csv"
            print(f"    {output_file}")
            return None
        else:
            output_dir = self.output_root / "scores" / "h1"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / "h1_games_all_canonical.csv"
            df_d1.to_csv(output_file, index=False)
            print(f"\n  Written: {output_file}")
            print(f"  Size: {output_file.stat().st_size / 1024:.1f} KB")
            return output_file
    
    def canonicalize_odds(self) -> Optional[Path]:
        """Canonicalize odds data."""
        print("\n" + "="*70)
        print("CANONICALIZING: Odds (spreads/fg)")
        print("="*70)
        
        odds_file = DATA_PATHS.odds_canonical_spreads_fg / "spreads_fg_all.csv"
        df = pd.read_csv(odds_file)
        
        print(f"\n  Input: {odds_file}")
        print(f"  Rows: {len(df):,}")
        
        # Identify source columns
        home_col = 'home_team_canonical' if 'home_team_canonical' in df.columns else 'home_team'
        away_col = 'away_team_canonical' if 'away_team_canonical' in df.columns else 'away_team'
        
        # Apply resolver
        print("  Resolving team names...")
        df['home_canonical'] = df[home_col].apply(
            lambda x: self._resolve_with_audit(x, 'odds'))
        df['away_canonical'] = df[away_col].apply(
            lambda x: self._resolve_with_audit(x, 'odds'))
        
        # Filter to D1 only
        d1_mask = df['home_canonical'].notna() & df['away_canonical'].notna()
        df_d1 = df[d1_mask].copy()
        
        print(f"  D1 rows: {len(df_d1):,} ({100*len(df_d1)/len(df):.1f}%)")
        
        # Output
        if self.dry_run:
            print("\n  [DRY RUN] Would write to:")
            output_file = self.output_root / "odds" / "spreads" / "fg" / "spreads_fg_canonical.csv"
            print(f"    {output_file}")
            return None
        else:
            output_dir = self.output_root / "odds" / "spreads" / "fg"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / "spreads_fg_canonical.csv"
            df_d1.to_csv(output_file, index=False)
            print(f"\n  Written: {output_file}")
            print(f"  Size: {output_file.stat().st_size / 1024:.1f} KB")
            return output_file
    
    def _canonicalize_odds_file(self, input_path: Path, output_subdir: str, 
                                 output_name: str, source_label: str) -> Optional[Path]:
        """Generic method to canonicalize any odds file."""
        print("\n" + "="*70)
        print(f"CANONICALIZING: {source_label}")
        print("="*70)
        
        if not input_path.exists():
            print(f"  SKIPPED: {input_path} not found")
            return None
            
        df = pd.read_csv(input_path)
        
        print(f"\n  Input: {input_path}")
        print(f"  Rows: {len(df):,}")
        
        # Identify source columns
        home_col = 'home_team_canonical' if 'home_team_canonical' in df.columns else 'home_team'
        away_col = 'away_team_canonical' if 'away_team_canonical' in df.columns else 'away_team'
        
        # Apply resolver
        print("  Resolving team names...")
        df['home_canonical'] = df[home_col].apply(
            lambda x: self._resolve_with_audit(x, source_label.lower().replace(' ', '_')))
        df['away_canonical'] = df[away_col].apply(
            lambda x: self._resolve_with_audit(x, source_label.lower().replace(' ', '_')))
        
        # Filter to D1 only
        d1_mask = df['home_canonical'].notna() & df['away_canonical'].notna()
        df_d1 = df[d1_mask].copy()
        
        print(f"  D1 rows: {len(df_d1):,} ({100*len(df_d1)/len(df):.1f}%)")
        
        # Output
        if self.dry_run:
            print("\n  [DRY RUN] Would write to:")
            output_file = self.output_root / output_subdir / output_name
            print(f"    {output_file}")
            return None
        else:
            output_dir = self.output_root / output_subdir
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / output_name
            df_d1.to_csv(output_file, index=False)
            print(f"\n  Written: {output_file}")
            print(f"  Size: {output_file.stat().st_size / 1024:.1f} KB")
            return output_file
    
    def canonicalize_all_odds(self) -> List[Path]:
        """Canonicalize all odds files (spreads + totals, FG + H1)."""
        outputs = []
        
        # Spreads FG (already have method but use generic for consistency)
        out = self._canonicalize_odds_file(
            DATA_PATHS.odds_canonical_spreads_fg / "spreads_fg_all.csv",
            "odds/spreads/fg", "spreads_fg_canonical.csv", "Odds Spreads FG"
        )
        if out:
            outputs.append(out)
        
        # Spreads H1
        out = self._canonicalize_odds_file(
            DATA_PATHS.odds_canonical_spreads_h1 / "spreads_h1_all.csv",
            "odds/spreads/h1", "spreads_h1_canonical.csv", "Odds Spreads H1"
        )
        if out:
            outputs.append(out)
        
        # Totals FG
        out = self._canonicalize_odds_file(
            DATA_PATHS.odds_canonical_totals_fg / "totals_fg_all.csv",
            "odds/totals/fg", "totals_fg_canonical.csv", "Odds Totals FG"
        )
        if out:
            outputs.append(out)
        
        # Totals H1
        out = self._canonicalize_odds_file(
            DATA_PATHS.odds_canonical_totals_h1 / "totals_h1_all.csv",
            "odds/totals/h1", "totals_h1_canonical.csv", "Odds Totals H1"
        )
        if out:
            outputs.append(out)
        
        return outputs
    
    def validate_join(self, scores_file: Path, odds_file: Path) -> Dict:
        """Validate that canonicalized data can be joined properly."""
        print("\n" + "="*70)
        print("POST-CANONICALIZATION JOIN VALIDATION")
        print("="*70)
        
        if scores_file is None or odds_file is None:
            print("  [SKIPPED - dry run or missing files]")
            return {}
        
        scores = pd.read_csv(scores_file)
        odds = pd.read_csv(odds_file)
        
        # Normalize dates
        scores['date'] = pd.to_datetime(scores['date']).dt.date
        odds['date'] = pd.to_datetime(odds['game_date']).dt.date
        
        # Create match keys
        scores['key'] = scores['date'].astype(str) + '|' + scores['home_canonical'] + '|' + scores['away_canonical']
        odds['key'] = odds['date'].astype(str) + '|' + odds['home_canonical'] + '|' + odds['away_canonical']
        
        scores_games = set(scores['key'].unique())
        odds_games = set(odds['key'].unique())
        matched = scores_games & odds_games
        
        print(f"\n  Canonicalized scores games: {len(scores_games):,}")
        print(f"  Canonicalized odds games:   {len(odds_games):,}")
        print(f"  Matched games:              {len(matched):,}")
        print(f"  Match rate (of scores):     {100*len(matched)/len(scores_games):.1f}%")
        
        # By season
        def get_season(key):
            d = pd.to_datetime(key.split('|')[0])
            return d.year + 1 if d.month >= 11 else (d.year if d.month <= 4 else None)
        
        print(f"\n  Match rate by season:")
        for season in [2021, 2022, 2023, 2024, 2025, 2026]:
            scores_s = {k for k in scores_games if get_season(k) == season}
            odds_s = {k for k in odds_games if get_season(k) == season}
            matched_s = scores_s & odds_s
            rate = 100*len(matched_s)/len(scores_s) if scores_s else 0
            status = "✓" if rate > 90 else ("⚠" if rate > 50 else "✗")
            print(f"    {season}: {len(matched_s)}/{len(scores_s)} ({rate:.1f}%) {status}")
        
        return {
            'scores_games': len(scores_games),
            'odds_games': len(odds_games),
            'matched': len(matched),
            'match_rate': 100*len(matched)/len(scores_games) if scores_games else 0,
        }
    
    def save_audit_log(self):
        """Save full audit log to file."""
        if self.dry_run:
            print("\n  [DRY RUN] Would save audit log")
            return
            
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        
        # Save audit records
        audit_file = self.audit_dir / f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(audit_file, 'w') as f:
            json.dump([asdict(a) for a in self.audits], f, indent=2)
        print(f"\n  Audit log: {audit_file}")
        
        # Save reports
        report_file = self.audit_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump([asdict(r) for r in self.reports], f, indent=2)
        print(f"  Report: {report_file}")
    
    def run(self, validate_only: bool = False):
        """Run the full pipeline."""
        print("\n" + "="*70)
        print("NCAAM HISTORICAL DATA CANONICALIZATION PIPELINE")
        print("="*70)
        print(f"  Mode: {'DRY RUN' if self.dry_run else 'EXECUTE'}")
        print(f"  Validate only: {validate_only}")
        print(f"  Output root: {self.output_root}")
        
        # Step 1: Validate all sources
        print("\n" + "#"*70)
        print("# STEP 1: VALIDATION")
        print("#"*70)
        
        self.validate_scores()
        self.validate_odds()
        self.validate_barttorvik()
        self.cross_validate()
        
        if validate_only:
            print("\n" + "="*70)
            print("VALIDATION COMPLETE (--validate-only mode)")
            print("="*70)
            return
        
        # Step 2: Canonicalize
        print("\n" + "#"*70)
        print("# STEP 2: CANONICALIZATION")
        print("#"*70)
        
        scores_out = self.canonicalize_scores()
        h1_scores_out = self.canonicalize_h1_scores()
        odds_outputs = self.canonicalize_all_odds()
        
        # Step 3: Validate join
        print("\n" + "#"*70)
        print("# STEP 3: JOIN VALIDATION")
        print("#"*70)
        
        # Use first odds output (spreads FG) for validation
        odds_out = odds_outputs[0] if odds_outputs else None
        if not self.dry_run:
            self.validate_join(scores_out, odds_out)
        else:
            print("\n  [DRY RUN] Skipping join validation")
        
        # Save audit
        self.save_audit_log()
        
        # Summary
        print("\n" + "="*70)
        print("PIPELINE COMPLETE")
        print("="*70)
        
        if self.dry_run:
            print("\n  This was a DRY RUN. No files were written.")
            print("  Re-run with --execute to write canonical files.")


def main():
    parser = argparse.ArgumentParser(description="Canonicalize historical NCAAM data")
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Validate only, do not write files (default)')
    parser.add_argument('--execute', action='store_true',
                       help='Actually write canonical files')
    parser.add_argument('--validate-only', action='store_true',
                       help='Only validate, skip canonicalization')
    
    args = parser.parse_args()
    
    # If --execute is specified, disable dry_run
    dry_run = not args.execute
    
    pipeline = CanonicalPipeline(dry_run=dry_run)
    pipeline.run(validate_only=args.validate_only)


if __name__ == "__main__":
    main()
