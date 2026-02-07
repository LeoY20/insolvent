"""
Agent 4 — Order Analysis & Suggestion (Enhanced)

Responsibilities:
- Invoked for a specific order (status: PENDING).
- Updates status to 'ANALYZING'.
- Fetches active suppliers for the drug.
- Uses LLM (Dedalus/GPT-4o) to analyze suppliers based on Price, Lead Time, and Reliability.
- output structured JSON for logs.
- Updates order with SUGGESTED supplier, quantity, unit_price, total_price, and reasoning.
- Sets status to 'SUGGESTED' for user review.

API Key: DEDALUS_API_KEY_0 (index 0) - reused
"""

import time
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

SYSTEM_PROMPT = """
You are the Procurement Agent for a hospital pharmacy.
Your goal is to select the BEST supplier for a specific drug order.

Criteria for selection (in order of priority):
1. **Stock Availability**: Must be active.
2. **Reliability**: Preference for higher reliability scores (0-1).
3. **Lead Time**: Lower is better, especially if the order is urgent (implied).
4. **Price**: Lower is better.

You will receive:
- The Drug Name and Quantity needed.
- A list of Suppliers with their attributes (Price, Lead Time, Reliability).

You MUST output a JSON object with the following structure:
{
    "selected_supplier_id": "uuid-string",
    "reasoning": "A concise explanation of why this supplier was chosen (e.g., 'Best price with acceptable lead time').",
    "unit_price": 12.50,
    "total_price": 1250.00,
    "estimated_delivery_days": 3
}

Notes:
- `total_price` = `unit_price` * `quantity`.
- If no supplier is good, select the 'least bad' one but note the issues in reasoning.
"""

def fetch_order(order_id: str):
    """Fetches a specific order."""
    response = supabase.table('orders').select('*, drug:drugs(*)').eq('id', order_id).single().execute()
    return response.data

def fetch_suppliers_for_drug(drug_id: str):
    """Fetches active suppliers for a specific drug."""
    response = supabase.table('suppliers').select('*').eq('drug_id', drug_id).eq('active', True).execute()
    return response.data or []

def analyze_and_suggest(order: Dict, run_id: UUID):
    """
    Analyzes the order and updates it with suggestions using LLM.
    """
    print(f"  Analyzing Order {order['id']} for drug {order['drug']['name']}...")
    
    # 1. Set status to ANALYZING
    supabase.table('orders').update({'status': 'ANALYZING'}).eq('id', order['id']).execute()
    
    drug_name = order['drug']['name']
    quantity = order['quantity']
    suppliers = fetch_suppliers_for_drug(order['drug_id'])
    
    if not suppliers:
        print(f"  No suppliers found for {drug_name}. Marking order as FAILED.")
        fail_reason = 'Analysis failed: No active suppliers found.'
        supabase.table('orders').update({
            'status': 'FAILED',
            'notes': fail_reason
        }).eq('id', order['id']).execute()
        
        log_agent_output(AGENT_NAME, run_id, {
            "order_id": order['id'],
            "status": "FAILED",
            "reason": fail_reason
        }, fail_reason)
        return

    # 2. Construct Prompt for LLM
    suppliers_text = json.dumps([{
        "id": s['id'],
        "name": s['name'],
        "price_per_unit": s['price_per_unit'],
        "lead_time_days": s['lead_time_days'],
        "reliability_score": s['reliability_score']
    } for s in suppliers], indent=2)

    user_prompt = f"""
    Drug Needed: {drug_name}
    Quantity: {quantity}
    
    Available Suppliers:
    {suppliers_text}
    """

    print("  Calling LLM for supplier selection...")
    
    # 3. Call LLM
    try:
        response = call_dedalus(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            api_key_index=0, # Using index 0
            json_schema={
                "type": "object",
                "properties": {
                    "selected_supplier_id": {"type": "string"},
                    "reasoning": {"type": "string"},
                    "unit_price": {"type": "number"},
                    "total_price": {"type": "number"},
                    "estimated_delivery_days": {"type": "integer"}
                },
                "required": ["selected_supplier_id", "reasoning", "unit_price", "total_price"]
            }
        )
    except Exception as e:
        print(f"  LLM Call Failed: {e}")
        response = None

    # Fallback if LLM fails: Use simple logic
    if not response:
        print("  LLM failed, falling back to deterministic logic.")
        # Sort by Price
        valid_suppliers = [s for s in suppliers if s.get('price_per_unit') is not None]
        if not valid_suppliers:
             supabase.table('orders').update({
                'status': 'FAILED',
                'notes': 'Analysis failed: Suppliers exist but lack pricing data.'
            }).eq('id', order['id']).execute()
             return

        best_supplier = sorted(valid_suppliers, key=lambda s: float(s.get('price_per_unit') or 999))[0]
        unit_price = float(best_supplier['price_per_unit'])
        response = {
            "selected_supplier_id": best_supplier['id'],
            "reasoning": f"Fallback Selection: Lowest price (${unit_price}).",
            "unit_price": unit_price,
            "total_price": unit_price * quantity,
            "estimated_delivery_days": best_supplier.get('lead_time_days', 3)
        }

    # 4. Update Order with Suggestions using new columns
    print(f"  Suggestion: Supplier {response['selected_supplier_id']} - ${response['total_price']}")
    
    update_payload = {
        'status': 'SUGGESTED',
        'supplier_id': response['selected_supplier_id'],
        'quantity': quantity,
        'notes': response['reasoning'],
        'unit_price': response['unit_price'],
        'total_price': response['total_price']
    }
    
    supabase.table('orders').update(update_payload).eq('id', order['id']).execute()

    # 5. Structured Log Output
    log_payload = {
        "order_id": order['id'],
        "drug_name": drug_name,
        "quantity": quantity,
        "suppliers_considered": len(suppliers),
        "decision": response
    }
    
    log_agent_output(AGENT_NAME, run_id, log_payload, f"Suggested supplier for {drug_name}: {response['reasoning']}")


def run_analysis(order_id: str, run_id: UUID) -> Dict[str, Any]:
    """Executes the Order Analysis for a single order."""
    print(f"\n----- Running Agent 4 (Analysis) for order: {order_id} -----")
    
    try:
        order = fetch_order(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")

        analyze_and_suggest(order, run_id)
            
        print("----- Agent 4 Analysis finished -----")
        return {"status": "success"}
        
    except Exception as e:
        error_msg = f"Agent 4 Analysis failed: {str(e)}"
        print(f"  ERROR: {error_msg}")
        traceback.print_exc()
        log_agent_output(AGENT_NAME, run_id, {"error": str(e)}, error_msg)
        return {"error": str(e)}

def run(run_id: UUID):
    print("Warning: Default run() called on Agent 4. This agent is designed for specific order analysis now.")
