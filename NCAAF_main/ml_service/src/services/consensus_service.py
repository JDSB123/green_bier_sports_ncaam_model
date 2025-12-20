"""
Consensus Odds Calculation Service

Calculates market consensus from multiple sportsbooks.
Removes hardcoded sportsbook IDs and provides configurable sharp/public book selection.
"""

from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ConsensusService:
    """
    Service for calculating market consensus from odds data.
    
    Supports:
    - Sharp book consensus (Pinnacle, Circa, etc.)
    - Public book consensus (DraftKings, FanDuel, etc.)
    - Weighted consensus (by book reputation)
    - Simple average consensus
    """
    
    # Sharp sportsbooks (reputable, low-vig books)
    SHARP_BOOKS = {
        '1105',  # Pinnacle
        '1106',  # Circa
        '1119',  # Bookmaker
        '1120',  # FiveDimes
    }
    
    # Public sportsbooks (major US books)
    PUBLIC_BOOKS = {
        '1100',  # DraftKings
        '1101',  # FanDuel
        '1102',  # PointsBet
        '1103',  # BetMGM
        '1104',  # Caesars
    }
    
    def __init__(self, prefer_sharp: bool = True):
        """
        Initialize consensus service.
        
        Args:
            prefer_sharp: If True, prefer sharp books for consensus. 
                         If False, use all available books.
        """
        self.prefer_sharp = prefer_sharp
    
    def calculate_consensus(
        self,
        odds: List[Dict],
        book_type: str = 'sharp'
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate consensus spread and total from odds data.
        
        Args:
            odds: List of odds dictionaries from database
            book_type: 'sharp', 'public', or 'all'
        
        Returns:
            Tuple of (consensus_spread, consensus_total) or (None, None)
        """
        if not odds:
            return None, None
        
        # Filter by book type
        filtered_odds = self._filter_by_book_type(odds, book_type)
        
        if not filtered_odds:
            # Fallback to all books if preferred type has no data
            logger.debug(f"No {book_type} books found, using all books")
            filtered_odds = odds
        
        # Extract spreads and totals
        spreads = []
        totals = []
        
        for odd in filtered_odds:
            # Spread consensus (home spread)
            if odd.get('home_spread') is not None:
                spreads.append(float(odd['home_spread']))
            
            # Total consensus
            if odd.get('over_under') is not None:
                totals.append(float(odd['over_under']))
        
        # Calculate averages
        consensus_spread = sum(spreads) / len(spreads) if spreads else None
        consensus_total = sum(totals) / len(totals) if totals else None
        
        logger.debug(
            f"Consensus calculated: spread={consensus_spread}, total={consensus_total} "
            f"from {len(filtered_odds)} books"
        )
        
        return consensus_spread, consensus_total
    
    def _filter_by_book_type(
        self,
        odds: List[Dict],
        book_type: str
    ) -> List[Dict]:
        """Filter odds by sportsbook type."""
        if book_type == 'sharp':
            target_books = self.SHARP_BOOKS
        elif book_type == 'public':
            target_books = self.PUBLIC_BOOKS
        elif book_type == 'all':
            return odds
        else:
            logger.warning(f"Unknown book_type: {book_type}, using all")
            return odds
        
        return [
            odd for odd in odds
            if odd.get('sportsbook_id') in target_books
        ]
    
    def get_best_line(
        self,
        odds: List[Dict],
        market: str = 'spread',
        side: str = 'home'
    ) -> Optional[float]:
        """
        Get the best available line (most favorable for bettor).
        
        Args:
            odds: List of odds dictionaries
            market: 'spread', 'total', or 'moneyline'
            side: 'home' or 'away' (for spread), 'over' or 'under' (for total)
        
        Returns:
            Best line value or None
        """
        if not odds:
            return None
        
        if market == 'spread':
            if side == 'home':
                # Best home spread is the most negative (most points)
                spreads = [
                    float(odd['home_spread'])
                    for odd in odds
                    if odd.get('home_spread') is not None
                ]
                return min(spreads) if spreads else None
            else:  # away
                # Best away spread is the most positive (most points)
                spreads = [
                    float(odd['away_spread'])
                    for odd in odds
                    if odd.get('away_spread') is not None
                ]
                return max(spreads) if spreads else None
        
        elif market == 'total':
            if side == 'over':
                # Best over is the highest total
                totals = [
                    float(odd['over_under'])
                    for odd in odds
                    if odd.get('over_under') is not None
                ]
                return max(totals) if totals else None
            else:  # under
                # Best under is the lowest total
                totals = [
                    float(odd['over_under'])
                    for odd in odds
                    if odd.get('over_under') is not None
                ]
                return min(totals) if totals else None
        
        return None
