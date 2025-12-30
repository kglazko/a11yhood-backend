-- Add indexes to optimize ratings and editor queries
-- Speeds up rating aggregation and editor loading for product display

-- Index on product_id for fast rating lookups
CREATE INDEX IF NOT EXISTS idx_ratings_product_id ON ratings(product_id);

-- Composite index for product_id + rating to support aggregation queries
CREATE INDEX IF NOT EXISTS idx_ratings_product_rating ON ratings(product_id, rating);

-- Index on product_editors for fast owner lookups
CREATE INDEX IF NOT EXISTS idx_product_editors_product_id ON product_editors(product_id);
