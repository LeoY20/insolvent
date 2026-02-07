-- Create Orders Table
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    drug_id UUID REFERENCES drugs(id) ON DELETE SET NULL,
    alert_id UUID REFERENCES alerts(id) ON DELETE SET NULL,
    quantity INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'CONFIRMED', 'PROCESSING', 'PLACED', 'FAILED', 'CANCELLED')),
    supplier_id UUID REFERENCES suppliers(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Row Level Security
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

-- Policy (Permissive for Hackathon)
CREATE POLICY "Allow all operations on orders" ON orders FOR ALL USING (true);

-- Trigger for updated_at
CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON orders
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
