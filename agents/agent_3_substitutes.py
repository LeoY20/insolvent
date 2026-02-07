"""
Agent 3 — Drug Substitute Finder

Responsibilities:
- Receives a list of drugs needing substitutes from the Overseer.
- Uses hard-coded, medically validated substitution mappings.
- Checks inventory to see if substitutes are in stock.
- Uses an LLM to rank substitutes and add clinical notes.
- Upserts results to the 'substitutes' table.
- Logs analysis to agent_logs.

API Key: DEDALUS_API_KEY_3 (index 2)
"""

import json
from typing import Dict, Any, List
from uuid import UUID
import traceback

from agents.shared import (
    supabase,
    call_dedalus,
    log_agent_output,
    get_drugs_inventory,
    get_substitutes,
)

AGENT_NAME = "agent_3"
API_KEY_INDEX = 2

# The JSON schema Agent 3 expects the LLM to return
EXPECTED_JSON_SCHEMA = {
    "substitutions": [
        {
            "original_drug": "string",
            "substitutes": [
                {
                    "name": "string",
                    "preference_rank": 1,
                    "equivalence_notes": "string",
                    "dosing_conversion": "string",
                    "contraindications": "string",
                    "in_stock": True,
                    "stock_quantity": 0
                }
            ],
            "no_substitute_available": False,
            "clinical_notes": "string"
        }
    ],
    "summary": "string"
}

# Hard-coded, medically validated substitution mappings from the project spec
SUBSTITUTION_MAPPINGS = {
    "Epinephrine (Adrenaline)": [{"name": "Norepinephrine", "notes": "For cardiac use only"}, {"name": "Vasopressin", "notes": "Second-line for cardiac arrest"}],
    "Propofol": [{"name": "Etomidate", "notes": "Shorter duration"}, {"name": "Ketamine", "notes": "Good for hemodynamically unstable"}, {"name": "Midazolam", "notes": "Slower onset"}],
    "Penicillin": [{"name": "Amoxicillin", "notes": "Similar spectrum"}, {"name": "Cephalexin", "notes": "Check for cross-reactivity"}, {"name": "Azithromycin", "notes": "Use if allergy is confirmed"}],
    "Levofloxacin": [{"name": "Moxifloxacin", "notes": "Same class"}, {"name": "Ciprofloxacin", "notes": "Same class, different spectrum"}, {"name": "Doxycycline", "notes": "Tetracycline class alternative"}],
    "Heparin / Warfarin": [{"name": "Enoxaparin (Lovenox)", "notes": "LMWH, more predictable"}, {"name": "Fondaparinux", "notes": "For HIT patients"}, {"name": "Warfarin", "notes": "Oral, slower onset"}],
    "Insulin": [{"name": "Insulin Lispro (Humalog)", "notes": "Rapid-acting"}, {"name": "Insulin Glargine (Lantus)", "notes": "Long-acting basal"}],
    "Morphine": [{"name": "Hydromorphone (Dilaudid)", "notes": "5-7x more potent"}, {"name": "Fentanyl", "notes": "50-100x more potent"}, {"name": "Oxycodone", "notes": "Oral option"}],
    "IV Fluids": [{"name": "Lactated Ringer's", "notes": "Good for large-volume resuscitation"}, {"name": "Normal Saline (0.9% NaCl)", "notes": "Standard isotonic"}, {"name": "D5W", "notes": "Provides free water"}],
    "Oxygen": [],
    "Vaccines (e.g., Smallpox, Polio)": []
}

def build_system_prompt() -> str:
    """Builds the system prompt for Agent 3."""
    return """You are an expert clinical pharmacist. Your task is to analyze a list of drugs that are in short supply and recommend the best clinical substitutes.

You will be given a primary drug and a list of potential substitutes, including whether they are in stock. You must:
1.  Review the potential substitutes.
2.  Provide a clinical note on the appropriateness of the substitution.
3.  Include any critical dosing conversion information or contraindications.
4.  Rank the substitutes based on clinical preference (1 = best choice).
5.  Flag any drug that has no viable substitute (e.g., Oxygen).
"""

def generate_fallback_analysis(drugs_to_find: List[str], inventory_map: Dict[str, dict]) -> dict:
    """Generates a simple, rule-based analysis using the hard-coded map if the LLM fails."""
    print("WARNING: LLM call failed or is mocked. Generating a fallback analysis.")
    substitutions = []
    for drug_name in drugs_to_find:
        sub_list = []
        mappings = SUBSTITUTION_MAPPINGS.get(drug_name, [])
        for i, sub_map in enumerate(mappings):
            sub_name = sub_map['name']
            stock_info = inventory_map.get(sub_name, {})
            sub_list.append({
                "name": sub_name,
                "preference_rank": i + 1,
                "equivalence_notes": sub_map['notes'],
                "dosing_conversion": "Consult pharmacist for exact dosing.",
                "contraindications": "Review patient-specific factors.",
                "in_stock": bool(stock_info),
                "stock_quantity": float(stock_info.get('stock_quantity', 0))
            })
        
        substitutions.append({
            "original_drug": drug_name,
            "substitutes": sub_list,
            "no_substitute_available": not bool(mappings),
            "clinical_notes": "Fallback analysis using hard-coded data. Please verify clinically."
        })
    return {"substitutions": substitutions, "summary": "Fallback analysis generated from hard-coded mappings."}

def run(run_id: UUID, drugs_needing_substitutes: List[str]):
    """Executes the full workflow for Agent 3."""
    print(f"\n----- Running Agent 3: Substitute Finder for run_id: {run_id} -----")
    if not drugs_needing_substitutes:
        print("No drugs require substitutes. Agent 3 is skipping its run.")
        log_agent_output(AGENT_NAME, run_id, {"substitutions": []}, "No drugs required substitutes.")
        return

    try:
        print(f"Finding substitutes for: {', '.join(drugs_needing_substitutes)}")
        
        # 1. Fetch data
        inventory = get_drugs_inventory() or []
        inventory_map = {drug['name']: drug for drug in inventory}
        
        # 2. Prepare for LLM
        # For each drug, find its potential substitutes and their stock status
        prompt_data = []
        for drug_name in drugs_needing_substitutes:
            potential_subs = []
            for sub_map in SUBSTITUTION_MAPPINGS.get(drug_name, []):
                sub_name = sub_map['name']
                stock_info = inventory_map.get(sub_name, {})
                potential_subs.append({
                    "name": sub_name,
                    "notes": sub_map['notes'],
                    "in_stock": bool(stock_info),
                    "stock_quantity": float(stock_info.get('stock_quantity', 0))
                })
            prompt_data.append({"drug_to_replace": drug_name, "potential_substitutes": potential_subs})

        system_prompt = build_system_prompt()
        user_prompt = json.dumps(prompt_data, default=str)
        
        # 3. Call LLM, with fallback
        llm_analysis = call_dedalus(system_prompt, user_prompt, API_KEY_INDEX, EXPECTED_JSON_SCHEMA)
        
        analysis_payload = llm_analysis
        if not analysis_payload:
            analysis_payload = generate_fallback_analysis(drugs_needing_substitutes, inventory_map)

        # 4. Upsert substitute information into the database
        if supabase and 'substitutions' in analysis_payload:
            records_to_upsert = []
            for sub_info in analysis_payload['substitutions']:
                original_drug_name = sub_info['original_drug']
                original_drug_id = inventory_map.get(original_drug_name, {}).get('id')

                for sub in sub_info.get('substitutes', []):
                    sub_name = sub['name']
                    sub_drug_id = inventory_map.get(sub_name, {}).get('id')
                    records_to_upsert.append({
                        "drug_id": original_drug_id,
                        "drug_name": original_drug_name,
                        "substitute_name": sub_name,
                        "substitute_drug_id": sub_drug_id,
                        "equivalence_notes": sub.get('equivalence_notes'),
                        "preference_rank": sub.get('preference_rank')
                    })
            
            if records_to_upsert:
                print(f"Upserting {len(records_to_upsert)} substitute records into the database...")
                # The 'on_conflict' parameter tells Supabase which column(s) have the UNIQUE constraint.
                supabase.table('substitutes').upsert(records_to_upsert, on_conflict='drug_name,substitute_name').execute()
                print("Database upsert complete.")

        # 5. Log final output
        summary = analysis_payload.get('summary', 'Substitute analysis completed.')
        log_agent_output(AGENT_NAME, run_id, analysis_payload, summary)

    except Exception as e:
        error_summary = f"Agent 3 failed: {e}"
        print(f"ERROR: {error_summary}")
        traceback.print_exc()
        log_agent_output(AGENT_NAME, run_id, {"error": str(e), "trace": traceback.format_exc()}, error_summary)
    
    finally:
        print("----- Agent 3 finished -----")

if __name__ == '__main__':
    test_run_id = UUID('00000000-0000-0000-0000-000000000004')
    drugs_to_test = ["Propofol", "Oxygen"]
    run(test_run_id, drugs_to_test)
