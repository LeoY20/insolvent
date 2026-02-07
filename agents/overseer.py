"""
Overseer Agent — Decision Synthesizer

Responsibilities:
- Reads all agent_logs for current run_id
- Synthesizes intelligence from Agents 0, 1, and 2
- Makes decisions using a structured framework with EVIDENCE CITATIONS
- Writes alerts to the alerts table with source links
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
# Now includes EVIDENCE field for traceability
EXPECTED_JSON_SCHEMA = {
    "decisions": [
        {
            "action_type": "RESTOCK_NOW | SHORTAGE_WARNING | SUBSTITUTE_RECOMMENDED | SCHEDULE_CHANGE | SUPPLY_CHAIN_RISK",
            "severity": "INFO | WARNING | URGENT | CRITICAL",
            "drug_name": "string",
            "title": "string (short headline)",
            "description": "string (full recommendation)",
            "evidence": [
                {
                    "source_type": "INVENTORY | FDA | NEWS | SURGERY_SCHEDULE",
                    "description": "what data point supports this decision",
                    "source_url": "URL if available, else null",
                    "data_value": "the specific number or fact (e.g., 'burn rate: 6 days')"
                }
            ]
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
            "recommendation": "string",
            "affected_drugs": ["drug1", "drug2"]
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

# EVIDENCE REQUIREMENTS
Every decision MUST include at least one evidence entry. Here's how to decide what to include:

1. **INVENTORY evidence (ALWAYS REQUIRED)**: Every decision must cite the inventory data that triggered it.
   Include: burn_rate_days, stock_quantity, usage_rate_daily for the drug.

2. **FDA/NEWS evidence (ONLY if recent and specific)**:
   - ONLY include if the source is from the LAST 30 DAYS (can be longer ONLY if extremely relevant and still timely)
   - ONLY include if it specifically mentions the drug in question
   - MUST have a valid, working URL
   - If unsure about recency or relevance, OMIT the external source

Example decision with inventory evidence only (most common):
{
    "evidence": [
        {
            "source_type": "INVENTORY",
            "description": "Current stock will deplete based on usage rate",
            "source_url": null,
            "data_value": "burn_rate: 6.2 days, stock: 124 cylinders, daily_usage: 20"
        }
    ]
}

Example decision with inventory + recent FDA evidence:
{
    "evidence": [
        {
            "source_type": "INVENTORY",
            "description": "Low stock levels detected",
            "source_url": null,
            "data_value": "burn_rate: 5 days, stock: 50 vials, daily_usage: 10"
        },
        {
            "source_type": "FDA",
            "description": "Active FDA shortage (reported this week)",
            "source_url": "https://www.fda.gov/drugs/...",
            "data_value": "FDA status: ACTIVE, published: 2026-02-05"
        }
    ]
}
"""
    drug_ranking_info = "\n".join([f"- Rank {d['rank']}: {d['name']}" for d in MONITORED_DRUGS])

    return f"""You are the Chief Decision Maker for a hospital pharmacy supply chain. Your job is to synthesize intelligence from three agents and make actionable decisions.

The hospital monitors these critical drugs:
{drug_ranking_info}

You will receive JSON data from:
- Agent 0 (Inventory Analysis): Predicted burn rates, stock levels, usage patterns.
- Agent 1 (FDA Monitor): Official shortage statuses with source URLs.
- Agent 2 (News Analyzer): Risk signals from news with article URLs.
- Current Inventory: Real-time stock and burn rates.
- Unresolved Shortages: Active shortage records with source URLs.

IMPORTANT: Every decision you make MUST include evidence citations. Never recommend an action without citing the specific data that supports it. Include source URLs when available.

Synthesize all inputs and use the following framework to generate a response.
{decision_framework}
"""


def generate_fallback_decisions(inventory: list, agent_logs: dict, shortages: list) -> dict:
    """A simple rule-based fallback if the LLM fails. Includes evidence."""
    print("WARNING: LLM call failed or is mocked. Generating fallback decisions.")
    decisions = []
    drugs_needing_orders = []
    drugs_needing_substitutes = []

    # Get inventory analysis from agent_0
    inventory_analysis = agent_logs.get('agent_0', {}).get('drug_analysis', [])

    # Build a map of shortages by drug for quick lookup
    shortage_map = {}
    for s in shortages:
        drug_name = s.get('drug_name')
        if drug_name:
            if drug_name not in shortage_map:
                shortage_map[drug_name] = []
            shortage_map[drug_name].append(s)

    # Use current inventory if no analysis available
    data_source = inventory_analysis if inventory_analysis else inventory

    for item in data_source:
        drug_name = item.get('drug_name') or item.get('name')
        burn_rate = item.get('predicted_burn_rate_days') or item.get('burn_rate_days')
        stock = item.get('stock_quantity')
        usage = item.get('usage_rate_daily')

        if burn_rate is None or drug_name is None:
            continue

        drug_info = next((d for d in MONITORED_DRUGS if d['name'] == drug_name), None)
        if not drug_info:
            continue

        # Build evidence from inventory data
        evidence = [{
            "source_type": "INVENTORY",
            "description": f"Current stock level and burn rate calculation",
            "source_url": None,
            "data_value": f"burn_rate: {burn_rate:.1f} days, stock: {stock}, daily_usage: {usage}"
        }]

        # Add shortage evidence if exists
        if drug_name in shortage_map:
            for shortage in shortage_map[drug_name]:
                evidence.append({
                    "source_type": "FDA" if "FDA" in shortage.get('source', '') else "NEWS",
                    "description": shortage.get('description', 'Active shortage reported'),
                    "source_url": shortage.get('source_url'),
                    "data_value": f"severity: {shortage.get('impact_severity')}, source: {shortage.get('source')}"
                })

        if burn_rate < 7:
            decisions.append({
                "action_type": "RESTOCK_NOW",
                "severity": "CRITICAL" if burn_rate < 3 else "URGENT",
                "drug_name": drug_name,
                "title": f"Critically Low Stock: {drug_name}",
                "description": f"Stock for {drug_name} is critically low with ~{burn_rate:.1f} days remaining. Immediate action required.",
                "evidence": evidence
            })
            drugs_needing_orders.append({
                "drug_name": drug_name,
                "quantity": 100,
                "urgency": "EMERGENCY" if burn_rate < 3 else "EXPEDITED"
            })
            if drug_info['rank'] <= 5:
                drugs_needing_substitutes.append(drug_name)

        elif burn_rate < 14:
            decisions.append({
                "action_type": "SHORTAGE_WARNING",
                "severity": "WARNING",
                "drug_name": drug_name,
                "title": f"Monitor Stock: {drug_name}",
                "description": f"{drug_name} has ~{burn_rate:.1f} days of stock remaining. Monitor closely.",
                "evidence": evidence
            })

    return {
        "decisions": decisions,
        "drugs_needing_orders": drugs_needing_orders,
        "drugs_needing_substitutes": drugs_needing_substitutes,
        "schedule_adjustments": [],
        "summary": f"Fallback analysis: {len(decisions)} alerts generated based on inventory burn rates."
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

        # 2. Prepare for LLM - include shortage URLs for citation
        system_prompt = build_system_prompt()

        # Enrich shortages with source info for LLM
        shortages_with_sources = [
            {
                "drug_name": s.get("drug_name"),
                "source": s.get("source"),
                "source_url": s.get("source_url"),
                "impact_severity": s.get("impact_severity"),
                "description": s.get("description"),
                "reported_date": s.get("reported_date")
            }
            for s in unresolved_shortages
        ]

        user_prompt_data = {
            "agent_0_inventory_analysis": agent_outputs.get('agent_0'),
            "agent_1_fda_analysis": agent_outputs.get('agent_1'),
            "agent_2_news_analysis": agent_outputs.get('agent_2'),
            "current_inventory_snapshot": inventory,
            "current_unresolved_shortages_with_sources": shortages_with_sources
        }
        user_prompt = json.dumps(user_prompt_data, default=str)

        # 3. Call LLM, with fallback
        llm_decisions = call_dedalus(system_prompt, user_prompt, API_KEY_INDEX, EXPECTED_JSON_SCHEMA)

        analysis_payload = llm_decisions
        if not analysis_payload:
            analysis_payload = generate_fallback_decisions(inventory, agent_outputs, unresolved_shortages)

        # 4. Write alerts to the database with evidence in action_payload (dedupe per run_id)
        if supabase and 'decisions' in analysis_payload:
            existing_alerts = (
                supabase.table('alerts')
                .select('alert_type,drug_name,title,run_id')
                .eq('run_id', str(run_id))
                .execute()
                .data
                or []
            )
            existing_keys = {
                f"{a.get('alert_type')}|{a.get('drug_name')}|{a.get('title')}"
                for a in existing_alerts
            }
            alerts_to_insert = []
            for alert in analysis_payload['decisions']:
                drug_id = next((d['id'] for d in inventory if d['name'] == alert.get('drug_name')), None)
                key = f"{alert.get('action_type')}|{alert.get('drug_name')}|{alert.get('title')}"
                if key in existing_keys:
                    continue

                # Store evidence in action_payload for frontend display
                action_payload = {
                    "evidence": alert.get("evidence", []),
                    "order_details": alert.get("order_details")
                }

                alerts_to_insert.append({
                    "run_id": str(run_id),
                    "alert_type": alert.get("action_type"),
                    "severity": alert.get("severity"),
                    "drug_name": alert.get("drug_name"),
                    "drug_id": drug_id,
                    "title": alert.get("title"),
                    "description": alert.get("description"),
                    "action_payload": action_payload,
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
    print("Overseer cannot be run standalone without preceding agent logs in the database.")
