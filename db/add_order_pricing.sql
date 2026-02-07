-- Add pricing columns to orders table
ALTER TABLE orders ADD COLUMN IF NOT EXISTS unit_price DECIMAL(10, 2);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS total_price DECIMAL(10, 2);
