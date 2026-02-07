"""
Agent 4 — Order Processing & Supplier Selection

Responsibilities:
- Monitors 'orders' table for 'CONFIRMED' orders.
- Analyzes available suppliers for the requested drug.
- Selects the best supplier based on:
    1. Lowest price
    2. Shortest lead time
    3. Reliability score
- Updates order status to 'PLACED'.
- Adds notes explaining the decision.

API Key: DEDALUS_API_KEY_0 (index 0) - reused
"""

import json
from uuid import UUID
from typing import Optional, Dict, Any, List
import traceback

from agents.shared import (
    supabase,
    log_agent_output,
    call_dedalus,
)

AGENT_NAME = "agent_4_orders"

def fetch_confirmed_orders():
    """Fetches all orders with status 'CONFIRMED'."""
    response = supabase.table('orders').select('*, drug:drugs(*)').eq('status', 'CONFIRMED').execute()
    return response.data or []

def fetch_suppliers_for_drug(drug_id: str):
    """Fetches active suppliers for a specific drug."""
    response = supabase.table('suppliers').select('*').eq('drug_id', drug_id).eq('active', True).execute()
    return response.data or []

def select_best_supplier(suppliers: List[Dict]) -> Optional[Dict]:
    """
    Selects the best supplier based on simple logic:
    Priority:
    1. Nearby Hospital (fastest usually)? No, prioritize Price -> Lead Time -> Reliability.
    Actually, let's use a weighted score:
    Score = (1/Price) * 0.5 + (1/LeadTime) * 0.3 + Reliability * 0.2
    
    For now, let's keep it deterministic and simple for the demo:
    Sort by Price (asc), then Lead Time (asc), then Reliability (desc).
    """
    if not suppliers:
        return None
        
    # Valid suppliers must have a price
    valid_suppliers = [s for s in suppliers if s.get('price_per_unit') is not None]
    
    if not valid_suppliers:
        return None

    # Sort: Price ASC, Lead Time ASC, Reliability DESC
    def sort_key(s):
        price = float(s.get('price_per_unit') or 999999)
        lead_time = s.get('lead_time_days') or 999
        reliability = float(s.get('reliability_score') or 0)
        return (price, lead_time, -reliability)

    valid_suppliers.sort(key=sort_key)
    return valid_suppliers[0]

def process_order(order: Dict):
    """Processes a single confirmed order."""
    print(f"  Processing Order {order['id']} for drug {order['drug']['name']}...")
    
    drug_id = order['drug_id']
    suppliers = fetch_suppliers_for_drug(drug_id)
    
    if not suppliers:
        print(f"  No suppliers found for drug {drug_id}. Marking order as FAILED.")
        supabase.table('orders').update({
            'status': 'FAILED',
            'notes': 'No active suppliers found for this drug.'
        }).eq('id', order['id']).execute()
        return

    best_supplier = select_best_supplier(suppliers)
    
    if best_supplier:
        notes = (
            f"Auto-selected supplier '{best_supplier['name']}'. "
            f"Price: ${best_supplier['price_per_unit']}/unit, "
            f"Lead Time: {best_supplier['lead_time_days']} days, "
            f"Reliability: {int(best_supplier['reliability_score'] * 100)}%."
        )
        print(f"  Selected Supplier: {best_supplier['name']}")
        
        supabase.table('orders').update({
            'status': 'PLACED',
            'supplier_id': best_supplier['id'],
            'notes': notes
        }).eq('id', order['id']).execute()
    else:
        print("  Failed to select a supplier (valid suppliers missing data).")
        supabase.table('orders').update({
            'status': 'FAILED',
            'notes': 'Suppliers exist but have invalid data (missing price).'
        }).eq('id', order['id']).execute()


def run(run_id: UUID, ignored_arg=None) -> Dict[str, Any]:
    """Executes the Order Agent workflow."""
    print(f"\n----- Running Agent 4 (Orders) for run_id: {run_id} -----")
    
    try:
        confirmed_orders = fetch_confirmed_orders()
        print(f"  Found {len(confirmed_orders)} confirmed orders in queue.")
        
        processed_count = 0
        for order in confirmed_orders:
            process_order(order)
            processed_count += 1
            
        summary = f"Processed {processed_count} confirmed orders."
        log_agent_output(AGENT_NAME, run_id, {"processed": processed_count}, summary)
        
        print("----- Agent 4 finished -----")
        return {"processed": processed_count, "summary": summary}
        
    except Exception as e:
        error_msg = f"Agent 4 failed: {str(e)}"
        print(f"  ERROR: {error_msg}")
        traceback.print_exc()
        log_agent_output(AGENT_NAME, run_id, {"error": str(e)}, error_msg)
        return {"error": str(e)}

if __name__ == "__main__":
    import uuid
    run(uuid.uuid4())
