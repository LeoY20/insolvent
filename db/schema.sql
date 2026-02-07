-- PharmaSentinel Database Schema
-- Run this in your Supabase SQL Editor to create all tables

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- Table: drugs
-- Primary inventory table for the 10 monitored critical drugs
-- ============================================================================
CREATE TABLE IF NOT EXISTS drugs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    stock_quantity NUMERIC NOT NULL DEFAULT 0,
    unit TEXT NOT NULL DEFAULT 'units',
    price_per_unit NUMERIC(10,2),
    primary_supplier_id UUID,
    usage_rate_daily NUMERIC NOT NULL DEFAULT 0,
    predicted_usage_rate NUMERIC,
    burn_rate_days NUMERIC,
    predicted_burn_rate_days NUMERIC,
    reorder_threshold_days INTEGER DEFAULT 14,
    criticality_rank INTEGER CHECK (criticality_rank >= 1 AND criticality_rank <= 10),
    last_restock_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Table: shortages
-- Tracks known shortages from FDA + news + internal detection
-- ============================================================================
CREATE TABLE IF NOT EXISTS shortages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    drug_name TEXT NOT NULL,
    drug_id UUID REFERENCES drugs(id) ON DELETE SET NULL,
    type TEXT,
    source TEXT NOT NULL,
    source_url TEXT,
    impact_severity TEXT CHECK (impact_severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    description TEXT,
    reported_date DATE NOT NULL,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast unresolved shortage queries
CREATE INDEX IF NOT EXISTS idx_shortages_unresolved
ON shortages(resolved, reported_date DESC)
WHERE resolved = FALSE;

-- ============================================================================
-- Table: suppliers
-- Includes both commercial suppliers AND nearby hospitals
-- ============================================================================
CREATE TABLE IF NOT EXISTS suppliers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    drug_name TEXT NOT NULL,
    drug_id UUID REFERENCES drugs(id) ON DELETE SET NULL,
    price_per_unit NUMERIC(10,2),
    location TEXT,
    lead_time_days INTEGER,
    reliability_score NUMERIC(3,2) DEFAULT 1.00 CHECK (reliability_score >= 0 AND reliability_score <= 1),
    contact_info TEXT,
    is_nearby_hospital BOOLEAN DEFAULT FALSE,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Table: substitutes
-- Drug substitution mappings
-- ============================================================================
CREATE TABLE IF NOT EXISTS substitutes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    drug_id UUID REFERENCES drugs(id) ON DELETE CASCADE NOT NULL,
    drug_name TEXT NOT NULL,
    substitute_name TEXT NOT NULL,
    substitute_drug_id UUID REFERENCES drugs(id) ON DELETE SET NULL,
    equivalence_notes TEXT,
    preference_rank INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(drug_name, substitute_name)
);

-- ============================================================================
-- Table: agent_logs
-- Temporary staging area for agent outputs
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name TEXT NOT NULL,
    run_id UUID NOT NULL,
    payload JSONB NOT NULL,
    summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast run_id queries
CREATE INDEX IF NOT EXISTS idx_agent_logs_run
ON agent_logs(run_id, agent_name);

-- ============================================================================
-- Table: alerts
-- Final actionable outputs displayed on the frontend
-- ============================================================================
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL,
    alert_type TEXT NOT NULL CHECK (alert_type IN (
        'RESTOCK_NOW',
        'SHORTAGE_WARNING',
        'SUBSTITUTE_RECOMMENDED',
        'SCHEDULE_CHANGE',
        'SUPPLY_CHAIN_RISK',
        'AUTO_ORDER_PLACED'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('INFO','WARNING','URGENT','CRITICAL')),
    drug_id UUID REFERENCES drugs(id) ON DELETE SET NULL,
    drug_name TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    action_payload JSONB,
    action_required BOOLEAN DEFAULT FALSE,
    source TEXT,
    acknowledged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast unacknowledged alert queries
CREATE INDEX IF NOT EXISTS idx_alerts_unacknowledged
ON alerts(acknowledged, severity, created_at DESC)
WHERE acknowledged = FALSE;

-- ============================================================================
-- Table: surgery_schedule
-- Input data for burn rate calculations
-- ============================================================================
CREATE TABLE IF NOT EXISTS surgery_schedule (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    surgery_type TEXT NOT NULL,
    scheduled_date DATE NOT NULL,
    estimated_duration_hours NUMERIC,
    drugs_required JSONB NOT NULL,
    status TEXT DEFAULT 'SCHEDULED' CHECK (status IN ('SCHEDULED','COMPLETED','CANCELLED','RESCHEDULED')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Row-Level Security (RLS)
-- For hackathon: permissive policies. In production, scope to hospital_id
-- ============================================================================

ALTER TABLE drugs ENABLE ROW LEVEL SECURITY;
ALTER TABLE shortages ENABLE ROW LEVEL SECURITY;
ALTER TABLE suppliers ENABLE ROW LEVEL SECURITY;
ALTER TABLE substitutes ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE surgery_schedule ENABLE ROW LEVEL SECURITY;

-- Permissive policies for all tables
CREATE POLICY "Allow all operations on drugs" ON drugs FOR ALL USING (true);
CREATE POLICY "Allow all operations on shortages" ON shortages FOR ALL USING (true);
CREATE POLICY "Allow all operations on suppliers" ON suppliers FOR ALL USING (true);
CREATE POLICY "Allow all operations on substitutes" ON substitutes FOR ALL USING (true);
CREATE POLICY "Allow all operations on agent_logs" ON agent_logs FOR ALL USING (true);
CREATE POLICY "Allow all operations on alerts" ON alerts FOR ALL USING (true);
CREATE POLICY "Allow all operations on surgery_schedule" ON surgery_schedule FOR ALL USING (true);

-- ============================================================================
-- Updated_at trigger function
-- ============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add trigger to drugs table
CREATE TRIGGER update_drugs_updated_at BEFORE UPDATE ON drugs
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
