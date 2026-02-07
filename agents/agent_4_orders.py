"""
Agent 4 - Order & Supplier Manager

Flow:
  1. Receive drugs needing orders
  2. Fetch suppliers + inventory and send to LLM for recommendations
  3. Write order recommendations to alerts
  4. Log output

The LLM handles supplier selection, quantities, and cost estimates.
If the LLM is unavailable, we log and skip DB writes (no changes).

API Key: DEDALUS_API_KEY_3 (index 2)
"""

import json
import traceback
from uuid import UUID

from agents.shared import (
    supabase,
    call_dedalus,
    log_agent_output,
    get_suppliers,
    get_drugs_inventory,
    HOSPITAL_LOCATION,
)

AGENT_NAME = "agent_4"
API_KEY_INDEX = 2

LLM_RESPONSE_SCHEMA = {
    "orders": [
        {
            "drug_name": "string",
            "quantity": 0,
            "unit": "string",
            "urgency": "EMERGENCY | EXPEDITED | ROUTINE",
            "recommended_supplier": "string",
            "supplier_type": "DISTRIBUTOR | MANUFACTURER | NEARBY_HOSPITAL",
            "estimated_cost": 0,
            "estimated_delivery_days": 0,
            "backup_supplier": "string",
            "reasoning": "string",
        }
    ],
    "hospital_transfer_requests": [
        {
            "target_hospital": "string",
            "drug_name": "string",
            "quantity": 0,
            "justification": "string",
        }
    ],
    "cost_summary": {
        "total_estimated_cost": 0,
        "emergency_orders_cost": 0,
        "routine_orders_cost": 0,
    },
    "summary": "string",
}


def build_system_prompt() -> str:
    return f"""You are an expert pharmaceutical procurement specialist.

Hospital location:
{HOSPITAL_LOCATION}

You will receive:
1. Order requests (drug name, quantity, urgency).
2. Available suppliers (from the database).
3. Current drug pricing (from inventory).

Your job:
- Select the best supplier for each order based on urgency, cost, and reliability.
- Recommend backup suppliers for critical orders.
- Estimate delivery days and total cost.
- If hospital-to-hospital transfer is best, include it in hospital_transfer_requests.

Respond with valid JSON matching the provided schema."""


def analyze_with_llm(orders: list, suppliers: list, inventory: list) -> dict | None:
    system_prompt = build_system_prompt()
    user_prompt = json.dumps(
        {
            "orders_to_process": orders,
            "available_suppliers": suppliers,
            "current_drug_pricing": [
                {k: v for k, v in drug.items() if k in ["name", "price_per_unit", "unit"]}
                for drug in inventory
            ],
        },
        default=str,
    )

    result = call_dedalus(system_prompt, user_prompt, API_KEY_INDEX, LLM_RESPONSE_SCHEMA)
    if result and "orders" in result:
        return result

    return None


def write_alerts(run_id: UUID, analysis: dict, inventory: list):
    if not supabase:
        print("  No Supabase client - skipping DB writes.")
        return

    inventory_by_name = {d["name"]: d for d in inventory}
    alerts_to_insert = []

    for order in analysis.get("orders", []):
        drug_id = inventory_by_name.get(order.get("drug_name"), {}).get("id")
        alerts_to_insert.append(
            {
                "run_id": str(run_id),
                "alert_type": "AUTO_ORDER_PLACED",
                "severity": "URGENT" if order.get("urgency") == "EMERGENCY" else "WARNING",
                "drug_name": order.get("drug_name"),
                "drug_id": drug_id,
                "title": f"Order Recommended: {order.get('quantity')} {order.get('unit')} of {order.get('drug_name')}",
                "description": f"Recommended supplier: {order.get('recommended_supplier')}. Reason: {order.get('reasoning')}",
                "action_payload": order,
            }
        )

    if alerts_to_insert:
        print(f"  Inserting {len(alerts_to_insert)} order alerts into the database...")
        supabase.table("alerts").insert(alerts_to_insert).execute()
        print("  Alert insertion complete.")


def run(run_id: UUID, drugs_needing_orders: list):
    print(f"\n{'='*60}")
    print(f"Agent 4: Order Manager  |  run_id: {run_id}")
    print(f"{'='*60}")

    if not drugs_needing_orders:
        print("  No drugs require orders. Skipping.")
        log_agent_output(AGENT_NAME, run_id, {"orders": []}, "No orders required.")
        print(f"{'='*60}\n")
        return

    try:
        suppliers = get_suppliers(active_only=True) or []
        inventory = get_drugs_inventory() or []
        print(f"  {len(suppliers)} suppliers, {len(inventory)} inventory records fetched.")

        analysis = analyze_with_llm(drugs_needing_orders, suppliers, inventory)
        if analysis:
            print("  LLM analysis complete.")
            write_alerts(run_id, analysis, inventory)
            log_agent_output(AGENT_NAME, run_id, analysis, analysis.get("summary", "Done."))
        else:
            summary = "LLM unavailable - no order updates performed."
            print(f"  {summary}")
            log_agent_output(AGENT_NAME, run_id, {"summary": summary}, summary)

    except Exception as e:
        msg = f"Agent 4 failed: {e}"
        print(f"  ERROR: {msg}")
        traceback.print_exc()
        log_agent_output(AGENT_NAME, run_id, {"error": str(e), "trace": traceback.format_exc()}, msg)

    print(f"{'='*60}\n")


if __name__ == "__main__":
    run(
        UUID("00000000-0000-0000-0000-000000000005"),
        [
            {"drug_name": "Epinephrine (Adrenaline)", "quantity": 50, "urgency": "EMERGENCY"},
            {"drug_name": "Propofol", "quantity": 100, "urgency": "ROUTINE"},
        ],
    )
