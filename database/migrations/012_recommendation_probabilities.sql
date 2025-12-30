-- Migration 012: Recommendation probabilities + no-vig market probs
-- Adds audit-friendly fields for EV analysis and market hold (vig).

ALTER TABLE betting_recommendations
ADD COLUMN IF NOT EXISTS pick_price INTEGER;

ALTER TABLE betting_recommendations
ADD COLUMN IF NOT EXISTS implied_prob DECIMAL(6,5);

ALTER TABLE betting_recommendations
ADD COLUMN IF NOT EXISTS market_prob DECIMAL(6,5);

ALTER TABLE betting_recommendations
ADD COLUMN IF NOT EXISTS market_prob_novig DECIMAL(6,5);

ALTER TABLE betting_recommendations
ADD COLUMN IF NOT EXISTS market_hold_percent DECIMAL(6,3);

ALTER TABLE betting_recommendations
ADD COLUMN IF NOT EXISTS prob_edge DECIMAL(7,6);

COMMENT ON COLUMN betting_recommendations.pick_price IS 'American odds for the recommended pick at recommendation time';
COMMENT ON COLUMN betting_recommendations.implied_prob IS 'Model implied probability for the recommended pick';
COMMENT ON COLUMN betting_recommendations.market_prob IS 'Market implied probability from listed pick odds (vig-included)';
COMMENT ON COLUMN betting_recommendations.market_prob_novig IS 'No-vig market implied probability for the recommended pick (two-way normalized)';
COMMENT ON COLUMN betting_recommendations.market_hold_percent IS 'Implied market hold (vig) in percent for the two-way market, when available';
COMMENT ON COLUMN betting_recommendations.prob_edge IS 'Probability edge: implied_prob - market_prob_novig (or market_prob if no-vig not available)';
