-- Update the status check constraint to include new statuses
ALTER TABLE orders DROP CONSTRAINT IF EXISTS orders_status_check;
ALTER TABLE orders ADD CONSTRAINT orders_status_check 
    CHECK (status IN ('PENDING', 'ANALYZING', 'SUGGESTED', 'CONFIRMED', 'PROCESSING', 'PLACED', 'FAILED', 'CANCELLED'));
