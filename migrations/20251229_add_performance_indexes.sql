-- Add indexes to optimize GET /products performance
-- Addresses slow queries when filtering by source and banned status

-- Index on source column for filtering
CREATE INDEX IF NOT EXISTS idx_products_source ON products(source);

-- Composite index on (banned, created_at DESC) for the most common query pattern
-- This speeds up queries that filter by banned status and order by created_at
CREATE INDEX IF NOT EXISTS idx_products_banned_created_at ON products(banned, created_at DESC);

-- Composite index on (banned, source, created_at DESC) for filtered source queries
-- This is the most specific common pattern
CREATE INDEX IF NOT EXISTS idx_products_banned_source_created_at ON products(banned, source, created_at DESC);

-- Index on created_at for ordering when include_banned=true
CREATE INDEX IF NOT EXISTS idx_products_created_at ON products(created_at DESC);
