"""
Overseer Agent — Decision Synthesizer

Responsibilities:
- Reads all agent_logs for current run_id
- Synthesizes intelligence from Agents 0, 1, and 2
- Makes decisions using a structured framework
- Writes alerts to the alerts table
- Returns lists of drugs needing substitutes and orders for downstream agents

API Key: DEDALUS_API_KEY_2 (index 1)
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID
import traceback

from agents.shared import (
    supabase,
    call_dedalus,
    log_agent_output,
    get_agent_logs,
    get_drugs_inventory,
    get_unresolved_shortages,
    MONITORED_DRUGS
)

AGENT_NAME = "overseer"
API_KEY_INDEX = 1

# The JSON schema the Overseer expects the LLM to return
EXPECTED_JSON_SCHEMA = {
    "decisions": [
        {
            "action_type": "RESTOCK_NOW | SHORTAGE_WARNING | SUBSTITUTE_RECOMMENDED | SCHEDULE_CHANGE | SUPPLY_CHAIN_RISK | AUTO_ORDER_PLACED",
            "severity": "INFO | WARNING | URGENT | CRITICAL",
            "drug_name": "string",
            "title": "string (short headline)",
            "description": "string (full recommendation)",
        }
    ],
    "drugs_needing_substitutes": ["drug_name_1", "drug_name_2"],
    "drugs_needing_orders": [
        {"drug_name": "string", "quantity": 0, "urgency": "ROUTINE | EXPEDITED | EMERGENCY"}
    ],
    "schedule_adjustments": [
        {
            "surgery_date": "YYYY-MM-DD",
            "surgery_type": "string",
            "recommendation": "string"
        }
    ],
    "summary": "string"
}

def build_system_prompt() -> str:
    """Builds the detailed system prompt for the Overseer agent."""
    decision_framework = """
# DECISION FRAMEWORK
- **IMMEDIATE (burn_rate < 7 days)**: Generate `RESTOCK_NOW` alert. If criticality is <= 5 AND there's an active shortage, also trigger a `SUBSTITUTE_RECOMMENDED` alert.
- **WARNING (burn_rate 7–14 days)**: Generate `SHORTAGE_WARNING`. Escalate severity if FDA/news signals confirm a shortage.
- **PLANNING (burn_rate 14–30 days + any risk signal)**: Generate `SUPPLY_CHAIN_RISK` alert.
- **Severity Mapping**: CRITICAL (immediate patient risk), URGENT (action in 48h), WARNING (action this week), INFO (awareness).
- **Orders**: A drug needs an order if its burn rate is below its reorder threshold (typically 14 days). Urgency is EMERGENCY if burn rate < 3 days, EXPEDITED if < 7 days, else ROUTINE.
- **Substitutes**: A drug needs a substitute if it has a high criticality (rank <= 5) and is in the IMMEDIATE or WARNING zone with a confirmed external shortage signal.
"""
    drug_ranking_info = "\n".join([f"- Rank {d['rank']}: {d['name']}" for d in MONITORED_DRUGS])

    return f"""You are the Chief Decision Maker for a hospital pharmacy supply chain. Your job is to synthesize intelligence from three agents and make actionable decisions.

The hospital monitors these critical drugs:
{drug_ranking_info}

You will receive JSON data from:
- Agent 0 (Inventory Analysis): Predicted burn rates.
- Agent 1 (FDA Monitor): Official shortage statuses.
- Agent 2 (News Analyzer): Public sentiment and disruption risks.

Synthesize all inputs and use the following framework to generate a response.
{decision_framework}
"""

def generate_fallback_decisions(inventory: list, agent_logs: dict) -> dict:
    """A simple rule-based fallback if the LLM fails."""
    print("WARNING: LLM call failed or is mocked. Generating fallback decisions.")
    decisions = []
    drugs_needing_orders = []
    drugs_needing_substitutes = []

    inventory_analysis = agent_logs.get('agent_0', {}).get('drug_analysis', [])
    if not inventory_analysis:
        return {"summary": "Fallback failed: No inventory analysis available.", "decisions": [], "drugs_needing_orders": [], "drugs_needing_substitutes": []}

    for drug_data in inventory_analysis:
        burn_rate = drug_data.get('predicted_burn_rate_days')
        if burn_rate is None: continue

        drug_name = drug_data['drug_name']
        drug_info = next((d for d in MONITORED_DRUGS if d['name'] == drug_name), None)
        if not drug_info: continue

        if burn_rate < 7:
            decisions.append({
                "action_type": "RESTOCK_NOW", "severity": "URGENT", "drug_name": drug_name,
                "title": f"Critically Low Stock: {drug_name}",
                "description": f"Stock for {drug_name} is critically low with ~{burn_rate:.1f} days remaining. Immediate action required."
            })
            drugs_needing_orders.append({"drug_name": drug_name, "quantity": 100, "urgency": "EMERGENCY"})
            if drug_info['rank'] <= 5:
                drugs_needing_substitutes.append(drug_name)
    
    return {
        "decisions": decisions,
        "drugs_needing_orders": drugs_needing_orders,
        "drugs_needing_substitutes": drugs_needing_substitutes,
        "schedule_adjustments": [],
        "summary": "Fallback decisions generated based on inventory burn rate."
    }

def run(run_id: UUID) -> Optional[Dict[str, Any]]:
    """Executes the full workflow for the Overseer Agent."""
    print(f"\n----- Running Overseer: Decision Synthesizer for run_id: {run_id} -----")
    
    try:
        # 1. Fetch data for context
        agent_log_data = get_agent_logs(run_id) or []
        inventory = get_drugs_inventory() or []
        unresolved_shortages = get_unresolved_shortages() or []

        # Consolidate agent payloads
        agent_outputs = {
            log['agent_name']: log['payload']
            for log in agent_log_data
            if 'payload' in log and 'agent_name' in log
        }

        # 2. Prepare for LLM
        system_prompt = build_system_prompt()
        user_prompt_data = {
            "agent_0_inventory_analysis": agent_outputs.get('agent_0'),
            "agent_1_fda_analysis": agent_outputs.get('agent_1'),
            "agent_2_news_analysis": agent_outputs.get('agent_2'),
            "current_inventory_snapshot": inventory,
            "current_unresolved_shortages": unresolved_shortages
        }
        user_prompt = json.dumps(user_prompt_data, default=str)

        # 3. Call LLM, with fallback
        llm_decisions = call_dedalus(system_prompt, user_prompt, API_KEY_INDEX, EXPECTED_JSON_SCHEMA)
        
        analysis_payload = llm_decisions
        if not analysis_payload:
            analysis_payload = generate_fallback_decisions(inventory, agent_outputs)
        
        # 4. Write alerts to the database
        if supabase and 'decisions' in analysis_payload:
            alerts_to_insert = []
            for alert in analysis_payload['decisions']:
                drug_id = next((d['id'] for d in inventory if d['name'] == alert.get('drug_name')), None)
                alerts_to_insert.append({
                    "run_id": str(run_id),
                    "alert_type": alert.get("action_type"),
                    "severity": alert.get("severity"),
                    "drug_name": alert.get("drug_name"),
                    "drug_id": drug_id,
                    "title": alert.get("title"),
                    "description": alert.get("description"),
                    "action_payload": alert.get("order_details"),
                })
            
            if alerts_to_insert:
                print(f"Inserting {len(alerts_to_insert)} alerts into the database...")
                supabase.table('alerts').insert(alerts_to_insert).execute()
                print("Alert insertion complete.")

        # 5. Log final output
        summary = analysis_payload.get('summary', 'Overseer analysis completed.')
        log_agent_output(AGENT_NAME, run_id, analysis_payload, summary)
        
        print("----- Overseer finished -----")
        return analysis_payload

    except Exception as e:
        error_summary = f"Overseer Agent failed: {e}"
        print(f"ERROR: {error_summary}")
        traceback.print_exc()
        log_agent_output(AGENT_NAME, run_id, {"error": str(e), "trace": traceback.format_exc()}, error_summary)
        return None

if __name__ == '__main__':
    # This will not work well standalone as it depends on other agents' logs
    print("Overseer cannot be run standalone without preceding agent logs in the database.")
    # You would need to manually insert logs for a test run_id to test this module.
    # Example:
    # test_run_id = UUID('some-uuid-from-db')
    # run(test_run_id)
