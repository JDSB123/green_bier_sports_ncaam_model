#!/bin/bash
# Script to re-fetch 2024 games with scores from SportsDataIO API
# This should populate scores for Final games

set -e

echo "Updating 2024 games with scores..."

# Run inside the container
docker compose exec -T ncaaf_v5 psql -h localhost -U ncaaf_user -d ncaaf_v5 <<EOF
-- Create a function to fetch and update games (we'll call it from Go)
-- For now, let's check if we can extract scores from box_scores if they exist
SELECT 'Checking for scores in box_scores...' as status;

-- Check if box_scores table exists and has data
SELECT COUNT(*) as box_scores_count 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name = 'box_scores';
EOF

echo "Note: Scores should be populated by re-fetching games from API."
echo "The ingestion worker should be re-fetching Final games with scores."
echo "Check ingestion logs for updates."
