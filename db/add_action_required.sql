-- Migration: Add action_required column to alerts table
-- This column determines whether an alert should appear in "Actions Needed" vs "System Alerts"

ALTER TABLE alerts ADD COLUMN IF NOT EXISTS action_required BOOLEAN DEFAULT FALSE;

-- Update existing alerts to set action_required based on alert_type
UPDATE alerts
SET action_required = TRUE
WHERE alert_type IN ('RESTOCK_NOW', 'SUBSTITUTE_RECOMMENDED', 'SCHEDULE_CHANGE', 'SUPPLY_CHAIN_RISK');

UPDATE alerts
SET action_required = FALSE
WHERE alert_type IN ('SHORTAGE_WARNING', 'AUTO_ORDER_PLACED');
