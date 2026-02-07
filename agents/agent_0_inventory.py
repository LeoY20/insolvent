"""
Agent 0 - Inventory Analyzer

Flow:
  1. Fetch inventory + upcoming surgery schedule
  2. Send to LLM for matching, prediction, and risk analysis
  3. Upsert predicted fields in Supabase
  4. Log output

The LLM handles all calculations and risk assessment.
If the LLM is unavailable, we log and skip DB writes (no changes).

API Key: DEDALUS_API_KEY_1 (index 0)
"""

import json
import traceback
from datetime import datetime
from uuid import UUID

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

LLM_RESPONSE_SCHEMA = {
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
            "notes": "string",
        }
    ],
    "schedule_impact": [
        {
            "surgery_date": "YYYY-MM-DD",
            "surgery_type": "string",
            "drugs_at_risk": ["drug_name"],
            "recommendation": "string",
        }
    ],
    "summary": "string",
}


def build_system_prompt() -> str:
    drug_ranking_info = "\n".join(
        [f"- Rank {d['rank']}: {d['name']} ({d['type']})" for d in MONITORED_DRUGS]
    )

    return f"""You are an expert hospital pharmacy inventory analyst.

We monitor these critical drugs (1 is most critical):
{drug_ranking_info}

You will receive:
1. Current inventory records.
2. Upcoming surgery schedule.

Your job:
- Compute predicted daily usage and burn rate (days) using current usage + surgeries.
- Flag risk levels (CRITICAL if burn_rate < 7 days, HIGH if < 14 days).
- Consider criticality ranking when assigning risk.
- Identify surgeries likely impacted by low stock.
- drug_name in your response MUST exactly match a name from our inventory.

Respond with valid JSON matching the provided schema."""


def analyze_with_llm(inventory: list, schedule: list) -> dict | None:
    system_prompt = build_system_prompt()
    user_prompt = json.dumps(
        {
            "current_inventory": inventory,
            "surgery_schedule": schedule,
        },
        default=str,
    )

    result = call_dedalus(system_prompt, user_prompt, API_KEY_INDEX, LLM_RESPONSE_SCHEMA)
    if result and "drug_analysis" in result:
        return result

    return None


def normalize_analysis(analysis: dict, inventory: list) -> dict:
    """Ensure burn rates are deterministic based on inventory numbers."""
    inventory_by_name = {d["name"]: d for d in inventory}
    for item in analysis.get("drug_analysis", []):
        name = item.get("drug_name")
        if not name or name not in inventory_by_name:
            continue

        inv = inventory_by_name[name]
        stock = float(inv.get("stock_quantity") or 0)
        usage = float(inv.get("usage_rate_daily") or 0)
        predicted_usage = item.get("predicted_daily_usage_rate")
        try:
            predicted_usage = float(predicted_usage)
        except (TypeError, ValueError):
            predicted_usage = usage

        burn_rate = stock / usage if usage > 0 else None
        predicted_burn = stock / predicted_usage if predicted_usage > 0 else None

        item["current_stock"] = stock
        item["daily_usage_rate"] = usage
        item["predicted_daily_usage_rate"] = predicted_usage
        item["burn_rate_days"] = round(burn_rate, 1) if burn_rate is not None else None
        item["predicted_burn_rate_days"] = round(predicted_burn, 1) if predicted_burn is not None else None

    return analysis


def upsert_predictions(analysis: dict, inventory: list):
    if not supabase:
        print("  No Supabase client - skipping DB writes.")
        return

    today = datetime.now().isoformat()
    inventory_by_name = {d["name"]: d for d in inventory}

    upsert_data = []
    for item in analysis.get("drug_analysis", []):
        drug_name = item.get("drug_name")
        if not drug_name or drug_name not in inventory_by_name:
            continue

        drug_record = inventory_by_name[drug_name]
        upsert_data.append(
            {
                "id": drug_record["id"],
                "name": drug_record["name"],
                "type": drug_record["type"],
                "predicted_usage_rate": item.get("predicted_daily_usage_rate"),
                "predicted_burn_rate_days": item.get("predicted_burn_rate_days"),
                "burn_rate_days": item.get("burn_rate_days"),
                "updated_at": today,
            }
        )

    if upsert_data:
        print(f"  Batch updating {len(upsert_data)} drug records in the database...")
        supabase.table("drugs").upsert(upsert_data).execute()
        print("  Database updates complete.")


def run(run_id: UUID):
    print(f"\n{'='*60}")
    print(f"Agent 0: Inventory Analyzer  |  run_id: {run_id}")
    print(f"{'='*60}")

    try:
        inventory = get_drugs_inventory() or []
        schedule = get_surgery_schedule(days_ahead=30) or []
        print(f"  {len(inventory)} inventory records, {len(schedule)} scheduled surgeries.")

        analysis = analyze_with_llm(inventory, schedule)
        if analysis:
            analysis = normalize_analysis(analysis, inventory)
            print("  LLM analysis complete.")
            upsert_predictions(analysis, inventory)
            log_agent_output(AGENT_NAME, run_id, analysis, analysis.get("summary", "Done."))
        else:
            summary = "LLM unavailable - no inventory updates performed."
            print(f"  {summary}")
            log_agent_output(AGENT_NAME, run_id, {"summary": summary}, summary)

    except Exception as e:
        msg = f"Agent 0 failed: {e}"
        print(f"  ERROR: {msg}")
        traceback.print_exc()
        log_agent_output(AGENT_NAME, run_id, {"error": str(e), "trace": traceback.format_exc()}, msg)

    print(f"{'='*60}\n")


if __name__ == "__main__":
    run(UUID("00000000-0000-0000-0000-000000000001"))
