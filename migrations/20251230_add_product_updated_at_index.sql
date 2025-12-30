-- Add index to optimize filtering products by age (time since last source update)
-- Speeds up max_age filter queries that find recently updated products from their sources

-- Index on source_last_updated for fast age-based filtering
CREATE INDEX IF NOT EXISTS idx_products_source_last_updated ON products(source_last_updated DESC);
