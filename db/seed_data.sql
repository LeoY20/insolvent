-- ============================================================================
-- PharmaSentinel Seed Data (FIXED & ROBUST)
-- Run this AFTER schema.sql to populate or RESTORE initial data.
-- Updated to handle duplicates and missing rows gracefully.
-- ============================================================================

-- ============================================================================
-- 0. CLEANUP: Deduplicate existing rows before creating constraints
-- ============================================================================

-- Remove duplicate drugs (keep the one with latest ID)
DELETE FROM drugs a USING drugs b
WHERE a.id < b.id AND a.name = b.name;

-- Remove duplicate suppliers (keep the one with latest ID)
DELETE FROM suppliers a USING suppliers b
WHERE a.id < b.id AND a.name = b.name AND a.drug_name = b.drug_name;

-- ============================================================================
-- 1. Ensure Unique Constraints Exist (Idempotent)
-- Required for ON CONFLICT clauses to work correctly.
-- ============================================================================

-- Drugs: Name must be unique to prevent duplicates during reseeding
CREATE UNIQUE INDEX IF NOT EXISTS idx_drugs_name_unique ON drugs(name);

-- Suppliers: Name + Drug Name combination should be unique per location/type
-- Note: A supplier can supply multiple drugs, but (Supplier, Drug) pair is unique here.
CREATE UNIQUE INDEX IF NOT EXISTS idx_suppliers_unique_pair ON suppliers(name, drug_name);

-- Substitutes: (Drug, Substitute) pair already has a UNIQUE constraint in schema.sql
-- Surgery Schedule: No strict unique constraint needed for seed, but good practice.


-- ============================================================================
-- 2. Seed: drugs table
-- The 10 monitored critical drugs with realistic initial stock values
-- Uses ON CONFLICT DO UPDATE to restore values if row exists (e.g. after soft delete or partial data).
-- ============================================================================

INSERT INTO drugs (name, type, stock_quantity, unit, price_per_unit, usage_rate_daily, criticality_rank, reorder_threshold_days)
VALUES
    ('Epinephrine', 'Anaphylaxis/Cardiac', 150, 'vials', 35.00, 8, 1, 14),
    ('Oxygen', 'Respiratory Support', 500, 'liters', 0.50, 120, 2, 7),
    ('Levofloxacin', 'Broad-Spectrum Antibiotic', 200, 'tablets', 12.00, 15, 3, 14),
    ('Propofol', 'Anesthetic', 80, 'vials', 45.00, 6, 4, 14),
    ('Penicillin', 'Antibiotic', 300, 'vials', 8.00, 20, 5, 14),
    ('IV Fluids', 'Hydration/Shock', 400, 'bags', 3.50, 50, 6, 14),
    ('Heparin', 'Anticoagulant', 120, 'vials', 28.00, 10, 7, 14),
    ('Insulin', 'Diabetes Management', 180, 'vials', 55.00, 12, 8, 14),
    ('Morphine', 'Analgesic/Pain', 100, 'vials', 18.00, 7, 9, 14),
    ('Vaccines', 'Immunization', 250, 'doses', 22.00, 5, 10, 21)
ON CONFLICT (name) DO UPDATE SET
    type = EXCLUDED.type,
    stock_quantity = EXCLUDED.stock_quantity,
    unit = EXCLUDED.unit,
    price_per_unit = EXCLUDED.price_per_unit,
    usage_rate_daily = EXCLUDED.usage_rate_daily,
    criticality_rank = EXCLUDED.criticality_rank,
    reorder_threshold_days = EXCLUDED.reorder_threshold_days;


-- ============================================================================
-- 3. Seed: suppliers table
-- Dependent on drugs table for IDs. Uses subqueries.
-- ============================================================================

INSERT INTO suppliers (name, drug_name, drug_id, location, lead_time_days, price_per_unit, reliability_score, is_nearby_hospital, active)
VALUES
    -- McKesson Corporation
    ('McKesson Corporation', 'Epinephrine',   (SELECT id FROM drugs WHERE name = 'Epinephrine'),   'National (US)', 1, 33.00, 0.98, FALSE, TRUE),
    ('McKesson Corporation', 'Propofol',      (SELECT id FROM drugs WHERE name = 'Propofol'),      'National (US)', 1, 43.00, 0.98, FALSE, TRUE),
    ('McKesson Corporation', 'Levofloxacin',  (SELECT id FROM drugs WHERE name = 'Levofloxacin'),  'National (US)', 1, 11.50, 0.98, FALSE, TRUE),
    ('McKesson Corporation', 'Penicillin',    (SELECT id FROM drugs WHERE name = 'Penicillin'),    'National (US)', 1, 7.50,  0.98, FALSE, TRUE),
    ('McKesson Corporation', 'IV Fluids',     (SELECT id FROM drugs WHERE name = 'IV Fluids'),     'National (US)', 1, 3.25,  0.98, FALSE, TRUE),
    ('McKesson Corporation', 'Heparin',       (SELECT id FROM drugs WHERE name = 'Heparin'),       'National (US)', 1, 27.00, 0.98, FALSE, TRUE),
    ('McKesson Corporation', 'Insulin',       (SELECT id FROM drugs WHERE name = 'Insulin'),       'National (US)', 1, 53.00, 0.98, FALSE, TRUE),
    ('McKesson Corporation', 'Morphine',      (SELECT id FROM drugs WHERE name = 'Morphine'),      'National (US)', 1, 17.00, 0.98, FALSE, TRUE),

    -- Cardinal Health
    ('Cardinal Health', 'Epinephrine',   (SELECT id FROM drugs WHERE name = 'Epinephrine'),   'National (US)', 1, 34.00, 0.97, FALSE, TRUE),
    ('Cardinal Health', 'Propofol',      (SELECT id FROM drugs WHERE name = 'Propofol'),      'National (US)', 1, 44.00, 0.97, FALSE, TRUE),
    ('Cardinal Health', 'Oxygen',        (SELECT id FROM drugs WHERE name = 'Oxygen'),        'National (US)', 1, 0.48,  0.97, FALSE, TRUE),
    ('Cardinal Health', 'Levofloxacin',  (SELECT id FROM drugs WHERE name = 'Levofloxacin'),  'National (US)', 1, 11.75, 0.97, FALSE, TRUE),
    ('Cardinal Health', 'IV Fluids',     (SELECT id FROM drugs WHERE name = 'IV Fluids'),     'National (US)', 1, 3.30,  0.97, FALSE, TRUE),

    -- AmerisourceBergen
    ('AmerisourceBergen', 'Penicillin', (SELECT id FROM drugs WHERE name = 'Penicillin'), 'National (US)', 1, 7.75,  0.96, FALSE, TRUE),
    ('AmerisourceBergen', 'Heparin',    (SELECT id FROM drugs WHERE name = 'Heparin'),    'National (US)', 1, 27.50, 0.96, FALSE, TRUE),
    ('AmerisourceBergen', 'Insulin',    (SELECT id FROM drugs WHERE name = 'Insulin'),    'National (US)', 1, 54.00, 0.96, FALSE, TRUE),
    ('AmerisourceBergen', 'Morphine',   (SELECT id FROM drugs WHERE name = 'Morphine'),   'National (US)', 1, 17.50, 0.96, FALSE, TRUE),
    ('AmerisourceBergen', 'Vaccines',   (SELECT id FROM drugs WHERE name = 'Vaccines'),   'National (US)', 1, 21.50, 0.96, FALSE, TRUE),

    -- Morris & Dickson (Regional)
    ('Morris & Dickson', 'Epinephrine', (SELECT id FROM drugs WHERE name = 'Epinephrine'), 'Southeast US', 2, 34.50, 0.95, FALSE, TRUE),
    ('Morris & Dickson', 'Propofol',    (SELECT id FROM drugs WHERE name = 'Propofol'),    'Southeast US', 2, 44.50, 0.95, FALSE, TRUE),
    ('Morris & Dickson', 'IV Fluids',   (SELECT id FROM drugs WHERE name = 'IV Fluids'),   'Southeast US', 2, 3.40,  0.95, FALSE, TRUE),

    -- Henry Schein (Regional)
    ('Henry Schein', 'Levofloxacin', (SELECT id FROM drugs WHERE name = 'Levofloxacin'), 'National (US)', 2, 12.00, 0.94, FALSE, TRUE),
    ('Henry Schein', 'Penicillin',   (SELECT id FROM drugs WHERE name = 'Penicillin'),   'National (US)', 2, 8.00,  0.94, FALSE, TRUE),
    ('Henry Schein', 'Vaccines',     (SELECT id FROM drugs WHERE name = 'Vaccines'),     'National (US)', 2, 22.00, 0.94, FALSE, TRUE),

    -- Pfizer (Direct Manufacturer)
    ('Pfizer (Direct)', 'Vaccines',   (SELECT id FROM drugs WHERE name = 'Vaccines'),   'Global', 5, 20.00, 0.99, FALSE, TRUE),
    ('Pfizer (Direct)', 'Penicillin', (SELECT id FROM drugs WHERE name = 'Penicillin'), 'Global', 5, 7.00,  0.99, FALSE, TRUE),

    -- Teva Pharmaceuticals (Direct Manufacturer)
    ('Teva Pharmaceuticals', 'Epinephrine', (SELECT id FROM drugs WHERE name = 'Epinephrine'), 'Global', 7, 32.00, 0.93, FALSE, TRUE),
    ('Teva Pharmaceuticals', 'Morphine',    (SELECT id FROM drugs WHERE name = 'Morphine'),    'Global', 7, 16.50, 0.93, FALSE, TRUE),

    -- Fresenius Kabi (Direct Manufacturer)
    ('Fresenius Kabi', 'Propofol',  (SELECT id FROM drugs WHERE name = 'Propofol'),  'Global', 5, 42.00, 0.95, FALSE, TRUE),
    ('Fresenius Kabi', 'IV Fluids', (SELECT id FROM drugs WHERE name = 'IV Fluids'), 'Global', 5, 3.00,  0.95, FALSE, TRUE),
    ('Fresenius Kabi', 'Heparin',   (SELECT id FROM drugs WHERE name = 'Heparin'),   'Global', 5, 26.00, 0.95, FALSE, TRUE),

    -- Baxter International (Direct Manufacturer)
    ('Baxter International', 'IV Fluids', (SELECT id FROM drugs WHERE name = 'IV Fluids'), 'Global', 3, 3.20,  0.96, FALSE, TRUE),
    ('Baxter International', 'Heparin',   (SELECT id FROM drugs WHERE name = 'Heparin'),   'Global', 3, 26.50, 0.96, FALSE, TRUE),
    ('Baxter International', 'Morphine',  (SELECT id FROM drugs WHERE name = 'Morphine'),  'Global', 3, 17.25, 0.96, FALSE, TRUE),

    -- Nearby Hospitals (Pittsburgh area)
    ('Pittsburgh General Hospital', 'Epinephrine', (SELECT id FROM drugs WHERE name = 'Epinephrine'), 'Pittsburgh, PA', 0, 35.00, 0.90, TRUE, TRUE),
    ('Pittsburgh General Hospital', 'Oxygen',      (SELECT id FROM drugs WHERE name = 'Oxygen'),      'Pittsburgh, PA', 0, 0.50,  0.90, TRUE, TRUE),
    ('Pittsburgh General Hospital', 'IV Fluids',   (SELECT id FROM drugs WHERE name = 'IV Fluids'),   'Pittsburgh, PA', 0, 3.50,  0.90, TRUE, TRUE),

    ('UPMC Mercy', 'Propofol', (SELECT id FROM drugs WHERE name = 'Propofol'), 'Pittsburgh, PA', 0, 45.00, 0.92, TRUE, TRUE),
    ('UPMC Mercy', 'Heparin',  (SELECT id FROM drugs WHERE name = 'Heparin'),  'Pittsburgh, PA', 0, 28.00, 0.92, TRUE, TRUE),
    ('UPMC Mercy', 'Morphine', (SELECT id FROM drugs WHERE name = 'Morphine'), 'Pittsburgh, PA', 0, 18.00, 0.92, TRUE, TRUE),

    ('Allegheny General Hospital', 'Levofloxacin', (SELECT id FROM drugs WHERE name = 'Levofloxacin'), 'Pittsburgh, PA', 0, 12.00, 0.91, TRUE, TRUE),
    ('Allegheny General Hospital', 'Penicillin',   (SELECT id FROM drugs WHERE name = 'Penicillin'),   'Pittsburgh, PA', 0, 8.00,  0.91, TRUE, TRUE),
    ('Allegheny General Hospital', 'Insulin',      (SELECT id FROM drugs WHERE name = 'Insulin'),      'Pittsburgh, PA', 0, 55.00, 0.91, TRUE, TRUE)
ON CONFLICT (name, drug_name) DO UPDATE SET
    drug_id = EXCLUDED.drug_id,
    price_per_unit = EXCLUDED.price_per_unit,
    lead_time_days = EXCLUDED.lead_time_days,
    reliability_score = EXCLUDED.reliability_score,
    is_nearby_hospital = EXCLUDED.is_nearby_hospital,
    active = EXCLUDED.active;


-- ============================================================================
-- 4. Seed: substitutes table
-- ============================================================================

INSERT INTO substitutes (drug_id, drug_name, substitute_name, equivalence_notes, preference_rank)
VALUES
    -- Epinephrine substitutes
    ((SELECT id FROM drugs WHERE name = 'Epinephrine'), 'Epinephrine', 'Norepinephrine',
     'For cardiac use only (NOT anaphylaxis). Similar vasopressor effects.', 1),
    ((SELECT id FROM drugs WHERE name = 'Epinephrine'), 'Epinephrine', 'Vasopressin',
     'Second-line for cardiac arrest. Different mechanism but can support BP.', 2),

    -- Propofol substitutes
    ((SELECT id FROM drugs WHERE name = 'Propofol'), 'Propofol', 'Etomidate',
     'Shorter duration. Good for rapid sequence intubation. Less hypotension.', 1),
    ((SELECT id FROM drugs WHERE name = 'Propofol'), 'Propofol', 'Ketamine',
     'Useful for hemodynamically unstable patients. Maintains BP. Different side effect profile.', 2),
    ((SELECT id FROM drugs WHERE name = 'Propofol'), 'Propofol', 'Midazolam',
     'Slower onset. Benzodiazepine class. Useful for sedation but not ideal for induction.', 3),

    -- Penicillin substitutes
    ((SELECT id FROM drugs WHERE name = 'Penicillin'), 'Penicillin', 'Amoxicillin',
     'Similar spectrum, oral or IV. Well tolerated. First choice substitute.', 1),
    ((SELECT id FROM drugs WHERE name = 'Penicillin'), 'Penicillin', 'Cephalexin',
     'First-generation cephalosporin. Check for penicillin allergy cross-reactivity (~10%).', 2),
    ((SELECT id FROM drugs WHERE name = 'Penicillin'), 'Penicillin', 'Azithromycin',
     'Macrolide. Use if penicillin allergy confirmed. Different spectrum.', 3),

    -- Levofloxacin substitutes
    ((SELECT id FROM drugs WHERE name = 'Levofloxacin'), 'Levofloxacin', 'Moxifloxacin',
     'Same fluoroquinolone class. Similar spectrum with better anaerobic coverage.', 1),
    ((SELECT id FROM drugs WHERE name = 'Levofloxacin'), 'Levofloxacin', 'Ciprofloxacin',
     'Same fluoroquinolone class. Better for UTIs and GI infections.', 2),
    ((SELECT id FROM drugs WHERE name = 'Levofloxacin'), 'Levofloxacin', 'Doxycycline',
     'Tetracycline class. Different mechanism. Broad spectrum alternative.', 3),

    -- Heparin substitutes
    ((SELECT id FROM drugs WHERE name = 'Heparin'), 'Heparin', 'Enoxaparin',
     'Low molecular weight heparin (LMWH). More predictable dosing. Preferred by many.', 1),
    ((SELECT id FROM drugs WHERE name = 'Heparin'), 'Heparin', 'Fondaparinux',
     'Synthetic factor Xa inhibitor. Use for HIT patients. No cross-reactivity.', 2),
    ((SELECT id FROM drugs WHERE name = 'Heparin'), 'Heparin', 'Warfarin',
     'Oral anticoagulant. Slower onset (days). Requires INR monitoring. For chronic use.', 3),

    -- Insulin substitutes
    ((SELECT id FROM drugs WHERE name = 'Insulin'), 'Insulin', 'Insulin Lispro',
     'Rapid-acting analog (Humalog). Onset 15 min. For meal coverage.', 1),
    ((SELECT id FROM drugs WHERE name = 'Insulin'), 'Insulin', 'Insulin Glargine',
     'Long-acting basal insulin (Lantus). For basal coverage, not acute DKA.', 2),

    -- Morphine substitutes
    ((SELECT id FROM drugs WHERE name = 'Morphine'), 'Morphine', 'Hydromorphone',
     '5-7x more potent than morphine. Dilaudid. Adjust dose carefully. Less nausea.', 1),
    ((SELECT id FROM drugs WHERE name = 'Morphine'), 'Morphine', 'Fentanyl',
     '50-100x more potent. Rapid onset. Use in ICU settings. Careful dosing required.', 2),
    ((SELECT id FROM drugs WHERE name = 'Morphine'), 'Morphine', 'Oxycodone',
     'Oral option. ~1.5x potency of morphine. For moderate to severe pain.', 3),

    -- IV Fluids substitutes
    ((SELECT id FROM drugs WHERE name = 'IV Fluids'), 'IV Fluids', 'Lactated Ringers',
     'Better for large-volume resuscitation. Contains electrolytes. Preferred for trauma.', 1),
    ((SELECT id FROM drugs WHERE name = 'IV Fluids'), 'IV Fluids', 'Normal Saline',
     '0.9% NaCl. Standard isotonic crystalloid. Universal for most indications.', 2),
    ((SELECT id FROM drugs WHERE name = 'IV Fluids'), 'IV Fluids', 'D5W',
     '5% dextrose in water. For specific indications (hypoglycemia, maintenance). Not for resuscitation.', 3)
ON CONFLICT (drug_name, substitute_name) DO NOTHING;


-- ============================================================================
-- 5. Seed: surgery_schedule table
-- ============================================================================

INSERT INTO surgery_schedule (surgery_type, scheduled_date, estimated_duration_hours, drugs_required, status)
VALUES
    (
        'Cardiac Bypass',
        CURRENT_DATE + INTERVAL '3 days',
        5.5,
        '[
            {"drug_name": "Heparin", "quantity": 10, "unit": "vials"},
            {"drug_name": "Propofol", "quantity": 3, "unit": "vials"},
            {"drug_name": "Morphine", "quantity": 5, "unit": "vials"},
            {"drug_name": "IV Fluids", "quantity": 8, "unit": "bags"}
        ]'::jsonb,
        'SCHEDULED'
    ),
    (
        'Appendectomy',
        CURRENT_DATE + INTERVAL '5 days',
        2.0,
        '[
            {"drug_name": "Propofol", "quantity": 2, "unit": "vials"},
            {"drug_name": "Levofloxacin", "quantity": 4, "unit": "tablets"},
            {"drug_name": "IV Fluids", "quantity": 4, "unit": "bags"},
            {"drug_name": "Morphine", "quantity": 2, "unit": "vials"}
        ]'::jsonb,
        'SCHEDULED'
    ),
    (
        'Hip Replacement',
        CURRENT_DATE + INTERVAL '7 days',
        3.5,
        '[
            {"drug_name": "Propofol", "quantity": 2, "unit": "vials"},
            {"drug_name": "Heparin", "quantity": 6, "unit": "vials"},
            {"drug_name": "Morphine", "quantity": 4, "unit": "vials"},
            {"drug_name": "IV Fluids", "quantity": 6, "unit": "bags"}
        ]'::jsonb,
        'SCHEDULED'
    ),
    (
        'Emergency Trauma',
        CURRENT_DATE + INTERVAL '1 day',
        4.0,
        '[
            {"drug_name": "Epinephrine", "quantity": 3, "unit": "vials"},
            {"drug_name": "IV Fluids", "quantity": 12, "unit": "bags"},
            {"drug_name": "Morphine", "quantity": 6, "unit": "vials"},
            {"drug_name": "Heparin", "quantity": 4, "unit": "vials"},
            {"drug_name": "Oxygen", "quantity": 200, "unit": "liters"}
        ]'::jsonb,
        'SCHEDULED'
    ),
    (
        'Tonsillectomy',
        CURRENT_DATE + INTERVAL '10 days',
        1.5,
        '[
            {"drug_name": "Propofol", "quantity": 1, "unit": "vials"},
            {"drug_name": "Penicillin", "quantity": 6, "unit": "vials"},
            {"drug_name": "Morphine", "quantity": 1, "unit": "vials"},
            {"drug_name": "IV Fluids", "quantity": 2, "unit": "bags"}
        ]'::jsonb,
        'SCHEDULED'
    ),
    (
        'Cesarean Section',
        CURRENT_DATE + INTERVAL '12 days',
        2.5,
        '[
            {"drug_name": "Propofol", "quantity": 2, "unit": "vials"},
            {"drug_name": "Morphine", "quantity": 3, "unit": "vials"},
            {"drug_name": "IV Fluids", "quantity": 6, "unit": "bags"},
            {"drug_name": "Penicillin", "quantity": 4, "unit": "vials"}
        ]'::jsonb,
        'SCHEDULED'
    ),
    (
        'Knee Arthroscopy',
        CURRENT_DATE + INTERVAL '15 days',
        2.0,
        '[
            {"drug_name": "Propofol", "quantity": 2, "unit": "vials"},
            {"drug_name": "Morphine", "quantity": 2, "unit": "vials"},
            {"drug_name": "IV Fluids", "quantity": 3, "unit": "bags"},
            {"drug_name": "Levofloxacin", "quantity": 3, "unit": "tablets"}
        ]'::jsonb,
        'SCHEDULED'
    ),
    (
        'Cholecystectomy',
        CURRENT_DATE + INTERVAL '18 days',
        3.0,
        '[
            {"drug_name": "Propofol", "quantity": 2, "unit": "vials"},
            {"drug_name": "Levofloxacin", "quantity": 5, "unit": "tablets"},
            {"drug_name": "Morphine", "quantity": 3, "unit": "vials"},
            {"drug_name": "IV Fluids", "quantity": 5, "unit": "bags"}
        ]'::jsonb,
        'SCHEDULED'
    ),
    (
        'Spinal Fusion',
        CURRENT_DATE + INTERVAL '21 days',
        6.0,
        '[
            {"drug_name": "Propofol", "quantity": 3, "unit": "vials"},
            {"drug_name": "Heparin", "quantity": 8, "unit": "vials"},
            {"drug_name": "Morphine", "quantity": 8, "unit": "vials"},
            {"drug_name": "IV Fluids", "quantity": 10, "unit": "bags"}
        ]'::jsonb,
        'SCHEDULED'
    ),
    (
        'Cataract Surgery',
        CURRENT_DATE + INTERVAL '25 days',
        1.0,
        '[
            {"drug_name": "Propofol", "quantity": 1, "unit": "vials"},
            {"drug_name": "IV Fluids", "quantity": 1, "unit": "bags"}
        ]'::jsonb,
        'SCHEDULED'
    )
ON CONFLICT DO NOTHING;
