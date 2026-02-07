"""
Agent 3 - Drug Substitute Finder

Flow:
  1. Receive drugs needing substitutes
  2. Fetch inventory and send to LLM for substitute selection + ranking
  3. Upsert substitute records in Supabase
  4. Log output

The LLM handles all matching, ranking, and clinical notes.
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
    get_drugs_inventory,
)

AGENT_NAME = "agent_3"
API_KEY_INDEX = 2

LLM_RESPONSE_SCHEMA = {
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
                    "stock_quantity": 0,
                }
            ],
            "no_substitute_available": False,
            "clinical_notes": "string",
        }
    ],
    "summary": "string",
}


def build_system_prompt() -> str:
    return """You are an expert clinical pharmacist.

You will receive:
1. A list of drugs needing substitutes.
2. Current inventory records.

Your job:
- Recommend clinically appropriate substitutes.
- Rank substitutes by preference (1 = best).
- Provide equivalence notes, dosing conversion guidance, and contraindications.
- Mark in_stock and stock_quantity based on the provided inventory.
- If no viable substitute exists, set no_substitute_available = true.

Respond with valid JSON matching the provided schema."""


def analyze_with_llm(drugs_needing_substitutes: list, inventory: list) -> dict | None:
    system_prompt = build_system_prompt()
    user_prompt = json.dumps(
        {
            "drugs_needing_substitutes": drugs_needing_substitutes,
            "inventory": inventory,
        },
        default=str,
    )

    result = call_dedalus(system_prompt, user_prompt, API_KEY_INDEX, LLM_RESPONSE_SCHEMA)
    if result and "substitutions" in result:
        return result

    return None


def upsert_substitutes(analysis: dict, inventory: list):
    if not supabase:
        print("  No Supabase client - skipping DB writes.")
        return

    inventory_by_name = {d["name"]: d for d in inventory}
    records_to_upsert = []

    for sub_info in analysis.get("substitutions", []):
        original_name = sub_info.get("original_drug")
        original_id = inventory_by_name.get(original_name, {}).get("id")
        if not original_id:
            print(f"  Skipping substitutes for unknown drug: {original_name}")
            continue

        for sub in sub_info.get("substitutes", []):
            sub_name = sub.get("name")
            sub_id = inventory_by_name.get(sub_name, {}).get("id")
            if not sub_id:
                print(f"  Skipping substitute not in inventory: {sub_name}")
                continue
            records_to_upsert.append(
                {
                    "drug_id": original_id,
                    "drug_name": original_name,
                    "substitute_name": sub_name,
                    "substitute_drug_id": sub_id,
                    "equivalence_notes": sub.get("equivalence_notes"),
                    "preference_rank": sub.get("preference_rank"),
                }
            )

    if records_to_upsert:
        print(f"  Upserting {len(records_to_upsert)} substitute records into the database...")
        supabase.table("substitutes").upsert(
            records_to_upsert, on_conflict="drug_name,substitute_name"
        ).execute()
        print("  Database upsert complete.")


def run(run_id: UUID, drugs_needing_substitutes: list):
    print(f"\n{'='*60}")
    print(f"Agent 3: Substitute Finder  |  run_id: {run_id}")
    print(f"{'='*60}")

    if not drugs_needing_substitutes:
        print("  No drugs require substitutes. Skipping.")
        log_agent_output(AGENT_NAME, run_id, {"substitutions": []}, "No drugs required substitutes.")
        print(f"{'='*60}\n")
        return

    try:
        inventory = get_drugs_inventory() or []
        print(f"  {len(inventory)} inventory records fetched.")

        analysis = analyze_with_llm(drugs_needing_substitutes, inventory)
        if analysis:
            print("  LLM analysis complete.")
            upsert_substitutes(analysis, inventory)
            log_agent_output(AGENT_NAME, run_id, analysis, analysis.get("summary", "Done."))
        else:
            summary = "LLM unavailable - no substitute updates performed."
            print(f"  {summary}")
            log_agent_output(AGENT_NAME, run_id, {"summary": summary}, summary)

    except Exception as e:
        msg = f"Agent 3 failed: {e}"
        print(f"  ERROR: {msg}")
        traceback.print_exc()
        log_agent_output(AGENT_NAME, run_id, {"error": str(e), "trace": traceback.format_exc()}, msg)

    print(f"{'='*60}\n")


if __name__ == "__main__":
    run(UUID("00000000-0000-0000-0000-000000000004"), ["Propofol", "Oxygen"])
