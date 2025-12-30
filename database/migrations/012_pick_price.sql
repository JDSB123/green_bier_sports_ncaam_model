-- Add pick-specific American odds price to recommendations
-- This supports correct EV/Kelly reproduction and auditability.

ALTER TABLE betting_recommendations
    ADD COLUMN IF NOT EXISTS pick_price INTEGER;

COMMENT ON COLUMN betting_recommendations.pick_price IS
    'American odds price for the specific pick side (HOME/AWAY/OVER/UNDER) at recommendation time';
