"""
Agent 1 — FDA Drug Shortage Monitor

Responsibilities:
- Queries openFDA API for drug shortage data
- Fetches existing shortages from database
- Uses LLM to match FDA data to monitored drugs and assess impact
- Inserts new shortage records into shortages table
- Logs analysis to agent_logs

API Key: DEDALUS_API_KEY_1 (index 0)
"""

import json
import requests
from typing import Dict, Any, List
from datetime import datetime
from uuid import UUID
import traceback

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
FDA_API_BASE = "https://api.fda.gov"

# The JSON schema Agent 1 expects the LLM to return
EXPECTED_JSON_SCHEMA = {
    "shortages_found": [
        {
            "drug_name": "string (matched to our monitored list)",
            "fda_drug_name": "string (exact FDA name)",
            "status": "ONGOING | RESOLVED | WORSENING",
            "impact_severity": "LOW | MEDIUM | HIGH | CRITICAL",
            "reason": "string",
            "estimated_resolution": "string or null",
            "source_url": "string"
        }
    ],
    "no_impact_drugs": ["list of monitored drugs with no shortage"],
    "summary": "string"
}

def query_fda_api_for_drug(drug_name: str) -> List[Dict[str, Any]]:
    """
    Queries relevant FDA endpoints for a given drug name to find signals of shortage.
    The openFDA API does not have a direct shortage endpoint, so we look for recalls,
    enforcement actions, and other potential indicators.
    """
    results = []
    # Using a generic search term that might appear in recall reasons or product descriptions
    search_term = f'"{drug_name}"'
    
    try:
        # Query for recalls and other enforcement actions
        enforcement_url = f"{FDA_API_BASE}/drug/enforcement.json"
        params = {'search': f'reason_for_recall:{search_term} OR product_description:{search_term}', 'limit': 5}
        response = requests.get(enforcement_url, params=params, timeout=15)
        
        if response.status_code == 200:
            enforcement_data = response.json().get('results', [])
            for item in enforcement_data:
                results.append({"source": "FDA Enforcement API", "data": item})
            if enforcement_data:
                print(f"  Found {len(enforcement_data)} enforcement records for {drug_name}.")
        else:
            print(f"  WARNING: FDA enforcement query for {drug_name} returned status {response.status_code}.")

    except requests.exceptions.RequestException as e:
        print(f"  ERROR: FDA API request for {drug_name} failed: {e}")
        
    return results

def build_system_prompt() -> str:
    """Builds the system prompt for Agent 1."""
    drug_ranking_info = "\n".join([f"- Rank {d['rank']}: {d['name']} ({d['type']})" for d in MONITORED_DRUGS])
    return f"""You are an expert FDA drug shortage analyst. Your task is to analyze data from FDA enforcement reports and existing database records to identify and assess drug shortages.

The hospital monitors these critical drugs:
{drug_ranking_info}

You will receive existing shortage records and new data from the FDA API. You must:
1.  Analyze the FDA data for signals of a new or worsening shortage (e.g., recalls).
2.  Match findings to our monitored drug list.
3.  Assess if a shortage is ONGOING, RESOLVED, or WORSENING.
4.  Rate the impact severity (LOW, MEDIUM, HIGH, CRITICAL) based on the drug's criticality rank. A shortage for a rank 1-3 drug is CRITICAL. A shortage for a rank 4-6 drug is HIGH.
5.  Provide a brief reason for the shortage based on the data.
"""

def generate_fallback_analysis(existing_shortages: list, fda_data: dict) -> dict:
    """Generates a simple, rule-based analysis if the LLM call fails."""
    print("WARNING: LLM call failed or is mocked. Generating a fallback analysis.")
    shortages_found = []
    processed_drugs = set()

    # Add existing shortages to the list
    for short in existing_shortages:
        if short.get('drug_name') in MONITORED_DRUG_NAMES:
            shortages_found.append({
                "drug_name": short['drug_name'],
                "fda_drug_name": short.get('drug_name'),
                "status": "ONGOING",
                "impact_severity": short.get('impact_severity', 'MEDIUM'),
                "reason": f"Existing shortage from DB: {short.get('description', 'No description')}",
                "estimated_resolution": "Unknown",
                "source_url": short.get('source_url')
            })
            processed_drugs.add(short['drug_name'])

    # Check for new signals from FDA data
    for drug_name, records in fda_data.items():
        if drug_name not in processed_drugs and records:
            # Simple rule: any enforcement record is a potential shortage
            drug_info = next((d for d in MONITORED_DRUGS if d['name'] == drug_name), {})
            severity = "LOW"
            if drug_info.get('rank', 10) <= 3: severity = "CRITICAL"
            elif drug_info.get('rank', 10) <= 6: severity = "HIGH"

            shortages_found.append({
                "drug_name": drug_name,
                "fda_drug_name": drug_name,
                "status": "ONGOING",
                "impact_severity": severity,
                "reason": f"Fallback analysis detected {len(records)} FDA enforcement record(s).",
                "estimated_resolution": "Unknown",
                "source_url": "https://api.fda.gov/drug/enforcement.json"
            })
            processed_drugs.add(drug_name)

    no_impact = [name for name in MONITORED_DRUG_NAMES if name not in processed_drugs]
    return {
        "shortages_found": shortages_found,
        "no_impact_drugs": no_impact,
        "summary": "Fallback analysis: Identified potential shortages from existing DB and new FDA signals."
    }

def run(run_id: UUID):
    """Executes the full workflow for Agent 1."""
    print(f"\n----- Running Agent 1: FDA Monitor for run_id: {run_id} -----")
    
    try:
        # 1. Fetch existing unresolved shortages
        existing_shortages = get_unresolved_shortages(days_back=180) or []
        print(f"Found {len(existing_shortages)} existing unresolved shortages.")

        # 2. Query FDA for all monitored drugs
        fda_data = {}
        for drug_name in MONITORED_DRUG_NAMES:
            fda_data[drug_name] = query_fda_api_for_drug(drug_name)
        print("Completed querying FDA APIs for all monitored drugs.")

        # 3. Prepare for LLM
        system_prompt = build_system_prompt()
        user_prompt = json.dumps({
            "existing_shortages": existing_shortages,
            "new_fda_data": fda_data
        }, default=str)
        
        # 4. Call LLM, with fallback
        llm_analysis = call_dedalus(system_prompt, user_prompt, API_KEY_INDEX, EXPECTED_JSON_SCHEMA)
        
        analysis_payload = llm_analysis
        if not analysis_payload:
            analysis_payload = generate_fallback_analysis(existing_shortages, fda_data)

        # 5. Process and insert new shortages
        if supabase and 'shortages_found' in analysis_payload:
            new_shortage_count = 0
            existing_drug_names = {s['drug_name'] for s in existing_shortages}

            for shortage in analysis_payload['shortages_found']:
                drug_name = shortage.get('drug_name')
                # Only insert if it's a new shortage for this drug
                if drug_name and drug_name not in existing_drug_names:
                    supabase.table('shortages').insert({
                        'drug_name': drug_name,
                        'type': 'FDA_REPORTED',
                        'source': 'FDA openFDA API',
                        'impact_severity': shortage.get('impact_severity', 'MEDIUM'),
                        'description': shortage.get('reason', 'No reason specified.'),
                        'reported_date': datetime.now().date().isoformat(),
                        'resolved': False,
                        'source_url': shortage.get('source_url')
                    }).execute()
                    new_shortage_count += 1
            
            if new_shortage_count > 0:
                print(f"Inserted {new_shortage_count} new shortage records into the database.")
            else:
                print("No new shortages to insert.")

        # 6. Log final output
        summary = analysis_payload.get('summary', 'FDA analysis completed.')
        log_agent_output(AGENT_NAME, run_id, analysis_payload, summary)

    except Exception as e:
        error_summary = f"Agent 1 failed: {e}"
        print(f"ERROR: {error_summary}")
        traceback.print_exc()
        log_agent_output(AGENT_NAME, run_id, {"error": str(e), "trace": traceback.format_exc()}, error_summary)
    
    finally:
        print("----- Agent 1 finished -----")

if __name__ == '__main__':
    test_run_id = UUID('00000000-0000-0000-0000-000000000002')
    run(test_run_id)
