"""
Agent 1 — FDA Drug Shortage Monitor

Flow:
  1. Query FDA /drug/shortages.json for our monitored drugs
  2. Send results + existing DB records to LLM for matching & analysis
  3. Upsert shortage records in Supabase
  4. Log output

The LLM handles all drug name matching and impact assessment.
If the LLM is unavailable, we just carry forward existing records as-is.

API Key: DEDALUS_API_KEY_1 (index 0)
"""

import json
import requests
import traceback
from datetime import datetime
from uuid import UUID

from agents.shared import (
    supabase,
    call_dedalus,
    log_agent_output,
    get_unresolved_shortages,
    MONITORED_DRUGS,
    MONITORED_DRUG_NAMES,
)

AGENT_NAME = "agent_1"
API_KEY_INDEX = 0
FDA_URL = "https://api.fda.gov/drug/shortages.json"

# Clean search terms for the FDA API. We need these because our monitored
# names like "Epinephrine (Adrenaline)" won't match FDA's "EPINEPHRINE".
# The LLM handles the reverse mapping (FDA results → monitored drugs).
FDA_SEARCH_TERMS = [
    "Epinephrine", "Oxygen", "Levofloxacin", "Propofol", "Penicillin",
    "Sodium Chloride", "Heparin", "Warfarin", "Insulin", "Morphine", "Vaccine",
]

LLM_RESPONSE_SCHEMA = {
    "shortages_found": [
        {
            "drug_name":            "string — must be from our monitored list",
            "fda_drug_name":        "string — exact name from FDA data",
            "status":               "ONGOING | RESOLVED | WORSENING",
            "impact_severity":      "LOW | MEDIUM | HIGH | CRITICAL",
            "reason":               "string",
            "estimated_resolution": "string or null",
            "source_url":           "string",
        }
    ],
    "no_impact_drugs": ["monitored drugs with no shortage"],
    "summary": "string",
}


# ── Step 1: Query FDA ───────────────────────────────────────────────────

def query_fda() -> list[dict]:
    """Batch-query FDA shortages for all monitored drugs in one API call."""
    parts = [f'openfda.generic_name:"{t}"' for t in FDA_SEARCH_TERMS]
    query = "+OR+".join(parts)

    try:
        resp = requests.get(FDA_URL, params={"search": query, "limit": 100}, timeout=20)
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            print(f"  FDA returned {len(results)} shortage records.")
            return results
        elif resp.status_code == 404:
            print("  FDA: no matching shortages found.")
            return []
        else:
            print(f"  FDA error: HTTP {resp.status_code}")
            return []
    except requests.RequestException as e:
        print(f"  FDA request failed: {e}")
        return []


# ── Step 2: Analyze with LLM ────────────────────────────────────────────

def analyze(existing_shortages: list, fda_results: list) -> dict:
    """
    Send FDA data + existing records to the LLM. It handles all matching
    between FDA generic names and our monitored drug list.
    If LLM fails, just carry forward existing records unchanged.
    """
    drug_list = "\n".join(
        f"  Rank {d['rank']}: {d['name']} ({d['type']})" for d in MONITORED_DRUGS
    )

    system_prompt = f"""You are an FDA drug shortage analyst. You will receive:
1. Our hospital's existing internal shortage records.
2. Fresh data from the FDA Drug Shortages API.

We monitor these drugs (by priority):
{drug_list}

Your job:
- Match FDA records to our monitored drugs. Use fuzzy matching — e.g. FDA's
  "HEPARIN SODIUM" matches our "Heparin / Warfarin", "SODIUM CHLORIDE"
  matches "IV Fluids", etc.
- Status: ONGOING (no change), WORSENING (new delays/manufacturers), RESOLVED (available).
- Severity: CRITICAL for rank 1-3, HIGH for 4-6, MEDIUM otherwise.
- Extract reason and estimated resolution date when available.
- drug_name in your response MUST exactly match a name from our monitored list above.

Respond with valid JSON matching the provided schema."""

    user_prompt = json.dumps({
        "existing_internal_records": existing_shortages,
        "fresh_fda_data": fda_results,
    }, default=str)

    result = call_dedalus(system_prompt, user_prompt, API_KEY_INDEX, LLM_RESPONSE_SCHEMA)

    if result and "shortages_found" in result:
        return result

    # ── Fallback: just carry forward existing records ────────────────
    print("  LLM unavailable — carrying forward existing records only.")
    carried = [
        {
            "drug_name": rec["drug_name"],
            "fda_drug_name": rec.get("drug_name"),
            "status": "ONGOING",
            "impact_severity": rec.get("impact_severity", "MEDIUM"),
            "reason": "Carried forward (LLM offline).",
            "estimated_resolution": None,
            "source_url": rec.get("source_url"),
        }
        for rec in existing_shortages
        if rec.get("drug_name") in MONITORED_DRUG_NAMES
    ]

    return {
        "shortages_found": carried,
        "no_impact_drugs": [],
        "summary": f"Fallback: carried forward {len(carried)} existing records. "
                   f"{len(fda_results)} FDA records could not be analyzed without LLM.",
    }


# ── Step 3: Upsert to DB ───────────────────────────────────────────────

def upsert_shortages(analysis: dict, existing_shortages: list):
    """Update existing or insert new shortage records."""
    if not supabase:
        print("  No Supabase client — skipping DB writes.")
        return

    today = datetime.now().date().isoformat()
    existing_by_name = {s["drug_name"]: s for s in existing_shortages}

    for shortage in analysis.get("shortages_found", []):
        drug_name = shortage.get("drug_name")
        if not drug_name:
            continue

        is_resolved = shortage.get("status") == "RESOLVED"
        record = {
            "drug_name":      drug_name,
            "type":           "FDA_REPORTED",
            "source":         "FDA Shortages API",
            "impact_severity": shortage.get("impact_severity", "MEDIUM"),
            "description":    shortage.get("reason", "No reason provided."),
            "reported_date":  today,
            "resolved":       is_resolved,
            "resolved_date":  today if is_resolved else None,
            "source_url":     shortage.get("source_url"),
        }

        if drug_name in existing_by_name:
            rec_id = existing_by_name[drug_name]["id"]
            supabase.table("shortages").update(record).eq("id", rec_id).execute()
            print(f"  Updated: {drug_name}")
        elif not is_resolved:
            supabase.table("shortages").insert(record).execute()
            print(f"  Inserted: {drug_name}")


# ── Main ────────────────────────────────────────────────────────────────

def run(run_id: UUID):
    print(f"\n{'='*60}")
    print(f"Agent 1: FDA Monitor  |  run_id: {run_id}")
    print(f"{'='*60}")

    try:
        existing = get_unresolved_shortages(days_back=180) or []
        print(f"  {len(existing)} existing unresolved shortages in DB.")

        fda_results = query_fda()
        analysis = analyze(existing, fda_results)
        upsert_shortages(analysis, existing)
        log_agent_output(AGENT_NAME, run_id, analysis, analysis.get("summary", "Done."))

    except Exception as e:
        msg = f"Agent 1 failed: {e}"
        print(f"  ERROR: {msg}")
        traceback.print_exc()
        log_agent_output(AGENT_NAME, run_id, {"error": str(e), "trace": traceback.format_exc()}, msg)

    print(f"{'='*60}\n")


if __name__ == "__main__":
    run(UUID("00000000-0000-0000-0000-000000000002"))
