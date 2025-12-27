-- Migration 010: Enhanced CLV Tracking
-- Adds additional fields for comprehensive Closing Line Value analysis
-- CLV is the gold standard for measuring betting model quality

-- Add CLV percentage (clv as % of closing line)
ALTER TABLE betting_recommendations
ADD COLUMN IF NOT EXISTS clv_percent DECIMAL(6,3);

-- Add timestamp for when closing line was captured
ALTER TABLE betting_recommendations
ADD COLUMN IF NOT EXISTS closing_line_captured_at TIMESTAMPTZ;

-- Add market line at time of recommendation (for CLV calculation)
ALTER TABLE betting_recommendations
ADD COLUMN IF NOT EXISTS market_line_at_bet DECIMAL(5,2);

-- Create index for CLV analysis queries
CREATE INDEX IF NOT EXISTS idx_recommendations_clv ON betting_recommendations(clv DESC) WHERE clv IS NOT NULL;

-- Create index for settled bets analysis
CREATE INDEX IF NOT EXISTS idx_recommendations_settled ON betting_recommendations(settled_at DESC) WHERE status = 'settled';

-- Add comment explaining CLV calculation
COMMENT ON COLUMN betting_recommendations.clv IS 'Closing Line Value: our line - closing line. Positive = we got value';
COMMENT ON COLUMN betting_recommendations.clv_percent IS 'CLV as percentage: (clv / closing_line) * 100';
COMMENT ON COLUMN betting_recommendations.closing_line_captured_at IS 'Timestamp when closing line was captured (ideally just before game start)';
COMMENT ON COLUMN betting_recommendations.market_line_at_bet IS 'Market line at time recommendation was made (for CLV calculation)';
