"""
Agent 4 — Order & Supplier Manager

Responsibilities:
- Receives a list of drugs needing orders from the Overseer.
- Merges hard-coded major suppliers with database suppliers.
- Uses an LLM to select optimal suppliers based on urgency, proximity, and price.
- Writes order recommendations to the 'alerts' table.
- Logs its analysis to agent_logs.

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
    get_suppliers,
    get_drugs_inventory,
    HOSPITAL_LOCATION,
)

AGENT_NAME = "agent_4"
API_KEY_INDEX = 2

# The JSON schema Agent 4 expects the LLM to return
EXPECTED_JSON_SCHEMA = {
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
            "reasoning": "string"
        }
    ],
    "hospital_transfer_requests": [
        {
            "target_hospital": "string",
            "drug_name": "string",
            "quantity": 0,
            "justification": "string"
        }
    ],
    "cost_summary": {
        "total_estimated_cost": 0,
        "emergency_orders_cost": 0,
        "routine_orders_cost": 0
    },
    "summary": "string"
}

# Hard-coded major US pharmaceutical distributors and manufacturers from the project spec
MAJOR_SUPPLIERS = [
    {"name": "McKesson Corporation", "type": "DISTRIBUTOR", "lead_time_days": 1, "reliability": 0.98},
    {"name": "Cardinal Health", "type": "DISTRIBUTOR", "lead_time_days": 1, "reliability": 0.97},
    {"name": "AmerisourceBergen", "type": "DISTRIBUTOR", "lead_time_days": 1, "reliability": 0.96},
    {"name": "Pfizer (Direct)", "type": "MANUFACTURER", "lead_time_days": 5, "reliability": 0.99},
    {"name": "Teva Pharmaceuticals", "type": "MANUFACTURER", "lead_time_days": 7, "reliability": 0.93},
    {"name": "Baxter International", "type": "MANUFACTURER", "lead_time_days": 3, "reliability": 0.96},
]

def build_system_prompt() -> str:
    """Builds the system prompt for Agent 4."""
    return f"""You are an expert pharmaceutical procurement specialist. Your task is to recommend optimal suppliers for a list of drug orders based on urgency, cost, and reliability.

# HOSPITAL LOCATION
{HOSPITAL_LOCATION}

# DECISION LOGIC
- **EMERGENCY Orders (need < 24 hours):** Prioritize nearby hospital transfers above all else. If none, use national distributors with the fastest lead times. Cost is not a factor.
- **EXPEDITED Orders (need < 3 days):** Use national distributors with high reliability (>0.95). Balance speed and cost.
- **ROUTINE Orders (need > 3 days):** Optimize for the best price among reliable suppliers.
- **Critical Drugs (criticality rank 1-5):** For these, strongly prefer suppliers with reliability > 0.95. Recommend ordering from a backup source if available.
"""

def generate_fallback_analysis(drugs_to_order: List[Dict], all_suppliers: List[Dict], inventory_map: Dict) -> Dict:
    """A simple rule-based fallback to select suppliers if the LLM fails."""
    print("WARNING: LLM call failed or is mocked. Generating fallback order recommendations.")
    orders = []
    total_cost = 0

    for order_req in drugs_to_order:
        drug_name = order_req['drug_name']
        urgency = order_req['urgency']
        
        # Find suppliers for this drug from the combined list
        drug_suppliers = [s for s in all_suppliers if s.get('drug_name') == drug_name or s.get('drug_name') is None]
        nearby_hospitals = [s for s in drug_suppliers if s.get('is_nearby_hospital')]
        
        rec = None
        if urgency == 'EMERGENCY' and nearby_hospitals:
            rec = nearby_hospitals[0]
        else: # For EXPEDITED/ROUTINE or EMERGENCY with no hospitals
            # Pick a major distributor
            distributors = [s for s in all_suppliers if s.get('type') == 'DISTRIBUTOR']
            if distributors:
                # Sort by lead time, then reliability
                distributors.sort(key=lambda s: (s.get('lead_time_days', 99), -s.get('reliability', 0)))
                rec = distributors[0]

        if not rec: # Ultimate fallback
            rec = {"name": "McKesson Corporation", "type": "DISTRIBUTOR", "lead_time_days": 1}

        drug_info = inventory_map.get(drug_name, {})
        price = float(drug_info.get('price_per_unit', 25.0)) # Default price if not found
        quantity = order_req['quantity']
        cost = quantity * price

        orders.append({
            "drug_name": drug_name,
            "quantity": quantity,
            "unit": drug_info.get('unit', 'vials'),
            "urgency": urgency,
            "recommended_supplier": rec['name'],
            "supplier_type": rec.get('type', 'DISTRIBUTOR'),
            "estimated_cost": cost,
            "estimated_delivery_days": rec.get('lead_time_days', 1 if urgency != 'ROUTINE' else 3),
            "backup_supplier": "Cardinal Health" if "McKesson" in rec['name'] else "McKesson Corporation",
            "reasoning": f"Fallback analysis based on urgency '{urgency}'."
        })
        total_cost += cost

    return {
        "orders": orders,
        "hospital_transfer_requests": [],
        "cost_summary": {"total_estimated_cost": total_cost, "emergency_orders_cost": 0, "routine_orders_cost": total_cost},
        "summary": "Fallback order analysis generated based on simple rules."
    }

def run(run_id: UUID, drugs_needing_orders: List[Dict[str, Any]]):
    """Executes the full workflow for Agent 4."""
    print(f"\n----- Running Agent 4: Order Manager for run_id: {run_id} -----")
    if not drugs_needing_orders:
        print("No drugs require orders. Agent 4 is skipping its run.")
        log_agent_output(AGENT_NAME, run_id, {"orders": []}, "No orders required.")
        return

    try:
        # 1. Fetch data
        db_suppliers = get_suppliers(active_only=True) or []
        inventory = get_drugs_inventory() or []
        inventory_map = {drug['name']: drug for drug in inventory}
        all_suppliers = db_suppliers + MAJOR_SUPPLIERS
        
        # 2. Prepare for LLM
        system_prompt = build_system_prompt()
        user_prompt = json.dumps({
            "orders_to_process": drugs_needing_orders,
            "available_suppliers": all_suppliers,
            "current_drug_pricing": [{k: v for k, v in drug.items() if k in ['name', 'price_per_unit', 'unit']} for drug in inventory]
        }, default=str)

        # 3. Call LLM, with fallback
        llm_analysis = call_dedalus(system_prompt, user_prompt, API_KEY_INDEX, EXPECTED_JSON_SCHEMA)
        
        analysis_payload = llm_analysis
        if not analysis_payload:
            analysis_payload = generate_fallback_analysis(drugs_needing_orders, all_suppliers, inventory_map)

        # 4. Write order recommendations as alerts
        if supabase and 'orders' in analysis_payload:
            alerts_to_insert = []
            for order in analysis_payload['orders']:
                drug_id = inventory_map.get(order.get('drug_name'), {}).get('id')
                alerts_to_insert.append({
                    "run_id": str(run_id),
                    "alert_type": "AUTO_ORDER_PLACED",
                    "severity": "URGENT" if order.get('urgency') == 'EMERGENCY' else 'WARNING',
                    "drug_name": order.get("drug_name"),
                    "drug_id": drug_id,
                    "title": f"Order Recommended: {order['quantity']} {order['unit']} of {order['drug_name']}",
                    "description": f"Recommended supplier: {order['recommended_supplier']}. Reason: {order['reasoning']}",
                    "action_payload": order
                })
            
            if alerts_to_insert:
                print(f"Inserting {len(alerts_to_insert)} order alerts into the database...")
                supabase.table('alerts').insert(alerts_to_insert).execute()
                print("Alert insertion complete.")

        # 5. Log final output
        summary = analysis_payload.get('summary', 'Order management analysis completed.')
        log_agent_output(AGENT_NAME, run_id, analysis_payload, summary)

    except Exception as e:
        error_summary = f"Agent 4 failed: {e}"
        print(f"ERROR: {error_summary}")
        traceback.print_exc()
        log_agent_output(AGENT_NAME, run_id, {"error": str(e), "trace": traceback.format_exc()}, error_summary)
    
    finally:
        print("----- Agent 4 finished -----")

if __name__ == '__main__':
    test_run_id = UUID('00000000-0000-0000-0000-000000000005')
    orders_to_test = [
        {"drug_name": "Epinephrine (Adrenaline)", "quantity": 50, "urgency": "EMERGENCY"},
        {"drug_name": "Propofol", "quantity": 100, "urgency": "ROUTINE"},
    ]
    run(test_run_id, orders_to_test)
