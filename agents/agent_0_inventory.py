"""
Agent 0 — Inventory Analyzer & Burn Rate Calculator

Responsibilities:
- Fetches current drug inventory and surgery schedule
- Computes basic burn rates (stock / daily usage)
- Uses LLM to predict future usage based on scheduled surgeries
- Identifies drugs at risk based on burn rate and criticality
- Updates drugs table with predictions
- Logs analysis to agent_logs

API Key: DEDALUS_API_KEY_1 (index 0)
"""

import json
from typing import Dict, Any, List
from datetime import datetime
from uuid import UUID
import traceback

from agents.shared import (
    supabase,
    call_dedalus,
    log_agent_output,
    get_drugs_inventory,
    get_surgery_schedule,
    MONITORED_DRUGS,
)

AGENT_NAME = "agent_0"
API_KEY_INDEX = 0

# The JSON schema Agent 0 expects the LLM to return
EXPECTED_JSON_SCHEMA = {
    "drug_analysis": [
        {
            "drug_name": "string",
            "current_stock": 0,
            "daily_usage_rate": 0,
            "predicted_daily_usage_rate": 0,
            "burn_rate_days": 0,
            "predicted_burn_rate_days": 0,
            "trend": "INCREASING | STABLE | DECREASING",
            "risk_level": "LOW | MEDIUM | HIGH | CRITICAL",
            "notes": "string"
        }
    ],
    "schedule_impact": [
        {
            "surgery_date": "YYYY-MM-DD",
            "surgery_type": "string",
            "drugs_at_risk": ["drug_name"],
            "recommendation": "string"
        }
    ],
    "summary": "string"
}


def build_system_prompt() -> str:
    """Builds the system prompt for Agent 0, including the full criticality ranking."""
    drug_ranking_info = "\n".join([f"- Rank {d['rank']}: {d['name']} ({d['type']})" for d in MONITORED_DRUGS])
    
    return f"""You are an expert hospital pharmacy inventory analyst. Your task is to analyze drug inventory levels, predict future usage based on surgical demand, and identify supply risks. Prioritize higher-criticality drugs in your analysis.

The hospital tracks the following critical drugs, ranked by criticality (1 is most critical):
{drug_ranking_info}

You will receive current inventory data and an upcoming surgery schedule. You must:
1.  Calculate a predicted daily usage rate based on current usage and scheduled surgery demand over the next 30 days.
2.  Calculate the predicted burn rate in days based on the new predicted usage rate.
3.  Flag any drug with a burn_rate < 7 days as CRITICAL, and < 14 days as HIGH.
4.  Identify specific surgeries that may be impacted by low stock.
5.  Consider the drug's criticality ranking when assessing risk.
"""

def aggregate_surgery_demand(surgeries: List[Dict[str, Any]]) -> Dict[str, float]:
    """Aggregates total drug demand from a list of upcoming surgeries."""
    demand = {}
    if not surgeries:
        return demand

    for surgery in surgeries:
        for req in surgery.get('drugs_required', []):
            drug_name = req.get('drug_name')
            quantity = float(req.get('quantity', 0))
            if drug_name and quantity > 0:
                demand[drug_name] = demand.get(drug_name, 0) + quantity
    return demand

def generate_fallback_analysis(drugs: list, surgery_demand: dict) -> dict:
    """Generates a simple, rule-based analysis if the LLM call fails."""
    print("WARNING: LLM call failed or is mocked. Generating a fallback analysis.")
    analysis = {"drug_analysis": [], "schedule_impact": [], "summary": "Fallback analysis due to LLM failure."}
    
    for drug in drugs:
        drug_name = drug['name']
        stock = float(drug.get('stock_quantity', 0))
        usage = float(drug.get('usage_rate_daily', 0))
        
        # Simplified prediction
        predicted_usage = usage + (surgery_demand.get(drug_name, 0) / 30)
        burn_rate = stock / usage if usage > 0 else float('inf')
        predicted_burn = stock / predicted_usage if predicted_usage > 0 else float('inf')
        
        risk = "LOW"
        if predicted_burn < 14: risk = "HIGH"
        if predicted_burn < 7: risk = "CRITICAL"

        analysis["drug_analysis"].append({
            "drug_name": drug_name,
            "current_stock": stock,
            "daily_usage_rate": usage,
            "predicted_daily_usage_rate": round(predicted_usage, 2),
            "burn_rate_days": round(burn_rate, 1),
            "predicted_burn_rate_days": round(predicted_burn, 1),
            "trend": "STABLE" if usage == predicted_usage else "INCREASING" if predicted_usage > usage else "DECREASING",
            "risk_level": risk,
            "notes": "Fallback analysis generated without LLM."
        })
    return analysis

def run(run_id: UUID):
    """Executes the full workflow for Agent 0."""
    print(f"\n----- Running Agent 0: Inventory Analyzer for run_id: {run_id} -----")
    
    try:
        # 1. Fetch data
        inventory = get_drugs_inventory()
        schedule = get_surgery_schedule(days_ahead=30)
        if inventory is None or schedule is None:
            raise ConnectionError("Failed to fetch data from Supabase.")
        
        print(f"Fetched {len(inventory)} drug records and {len(schedule)} upcoming surgeries.")

        # 2. Aggregate surgery demand
        surgery_demand = aggregate_surgery_demand(schedule)
        print(f"Aggregated demand for {len(surgery_demand)} drugs from schedule.")

        # 3. Prepare prompts for LLM
        system_prompt = build_system_prompt()
        user_prompt_data = {
            "current_inventory": inventory,
            "surgery_schedule": schedule
        }
        user_prompt = json.dumps(user_prompt_data, default=str)
        
        # 4. Call LLM for analysis
        llm_analysis = call_dedalus(system_prompt, user_prompt, API_KEY_INDEX, EXPECTED_JSON_SCHEMA)

        # 5. Use fallback if LLM fails
        if not llm_analysis:
            analysis_payload = generate_fallback_analysis(inventory, surgery_demand)
        else:
            analysis_payload = llm_analysis
            print("Successfully received analysis from LLM.")

        # 6. Update database with new predictions
        if supabase and 'drug_analysis' in analysis_payload:
            updates = []
            for item in analysis_payload['drug_analysis']:
                # Find matching drug from inventory to get its ID
                drug_record = next((d for d in inventory if d['name'] == item.get('drug_name')), None)
                if drug_record:
                    updates.append({
                        'id': drug_record['id'],
                        'predicted_usage_rate': item.get('predicted_daily_usage_rate'),
                        'predicted_burn_rate_days': item.get('predicted_burn_rate_days'),
                        'burn_rate_days': item.get('burn_rate_days'),
                        'updated_at': datetime.now().isoformat()
                    })
            
            if updates:
                # Supabase Python client v1 does not support batch updates, must iterate.
                # In v2, you could use upsert.
                print(f"Updating {len(updates)} drug records in the database...")
                for update in updates:
                    item_id = update.pop('id')
                    supabase.table('drugs').update(update).eq('id', item_id).execute()
                print("Database updates complete.")

        # 7. Log final output
        summary = analysis_payload.get('summary', 'Inventory analysis completed.')
        log_agent_output(AGENT_NAME, run_id, analysis_payload, summary)

    except Exception as e:
        error_summary = f"Agent 0 failed: {e}"
        print(f"ERROR: {error_summary}")
        traceback.print_exc()
        log_agent_output(AGENT_NAME, run_id, {"error": str(e), "trace": traceback.format_exc()}, error_summary)
    
    finally:
        print("----- Agent 0 finished -----")

if __name__ == '__main__':
    # This allows running the agent directly for testing
    test_run_id = UUID('00000000-0000-0000-0000-000000000001')
    run(test_run_id)
