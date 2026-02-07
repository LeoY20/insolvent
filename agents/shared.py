"""
PharmaSentinel Shared Agent Infrastructure

This module provides common utilities, constants, and functions used by all agents in the PharmaSentinel project.
It handles:
- Environment variable loading and validation.
- Supabase client initialization for database interactions.
- A wrapper for the Dedalus LLM API, including response parsing.
- Shared constants like the list of monitored drugs.
- Helper functions for common database queries.
- Agent output logging.
"""

import os
import json
import re
from typing import Dict, List, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta

from dotenv import load_dotenv
from supabase import create_client, Client
import requests

# ============================================================================
# Environment Configuration & Validation
# ============================================================================

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
DEDALUS_API_KEYS = [
    os.getenv('DEDALUS_API_KEY_1'),
    os.getenv('DEDALUS_API_KEY_2'),
    os.getenv('DEDALUS_API_KEY_3')
]
NEWS_API_KEY = os.getenv('NEWS_API_KEY')
HOSPITAL_LOCATION = os.getenv('HOSPITAL_LOCATION', 'Default Hospital, 123 Health St, Medville, USA')

def validate_environment():
    """Validates that all required environment variables are set and not placeholders."""
    required_vars = {
        'SUPABASE_URL': SUPABASE_URL,
        'SUPABASE_SERVICE_KEY': SUPABASE_SERVICE_KEY,
        'DEDALUS_API_KEY_1': DEDALUS_API_KEYS[0],
        'DEDALUS_API_KEY_2': DEDALUS_API_KEYS[1],
        'DEDALUS_API_KEY_3': DEDALUS_API_KEYS[2],
        'NEWS_API_KEY': NEWS_API_KEY
    }
    missing_vars = [key for key, val in required_vars.items() if not val]
    placeholder_vars = [key for key, val in required_vars.items() if val and 'your_' in val]

    if missing_vars:
        print(f"ERROR: Missing critical environment variables: {', '.join(missing_vars)}")
        return False
    if placeholder_vars:
        print(f"WARNING: Found placeholder values for: {', '.join(placeholder_vars)}. API calls may fail.")
    return True

# ============================================================================
# Supabase Client
# ============================================================================

supabase: Optional[Client] = None
if validate_environment() and SUPABASE_URL and SUPABASE_SERVICE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        print("Successfully connected to Supabase.")
    except Exception as e:
        print(f"FATAL: Could not connect to Supabase: {e}")
        supabase = None
else:
    print("FATAL: Supabase client could not be initialized due to missing environment variables.")

# ============================================================================
# Core Constants
# ============================================================================

MONITORED_DRUGS: List[Dict[str, Any]] = [
    {"rank": 1, "name": "Epinephrine (Adrenaline)", "type": "Anaphylaxis / Cardiac Arrest"},
    {"rank": 2, "name": "Oxygen", "type": "Respiratory Support"},
    {"rank": 3, "name": "Levofloxacin", "type": "Broad-Spectrum Antibiotic"},
    {"rank": 4, "name": "Propofol", "type": "Anesthetic"},
    {"rank": 5, "name": "Penicillin", "type": "Antibiotic"},
    {"rank": 6, "name": "IV Fluids", "type": "Hydration / Shock / Blood Loss"},
    {"rank": 7, "name": "Heparin / Warfarin", "type": "Anticoagulant"},
    {"rank": 8, "name": "Insulin", "type": "Diabetes / DKA Management"},
    {"rank": 9, "name": "Morphine", "type": "Analgesic / Pain Management"},
    {"rank": 10, "name": "Vaccines (e.g., Smallpox, Polio)", "type": "Immunization"},
]

MONITORED_DRUG_NAMES: List[str] = [drug["name"] for drug in MONITORED_DRUGS]

# ============================================================================
# Dedalus LLM API Wrapper
# ============================================================================

def call_dedalus(
    system_prompt: str,
    user_prompt: str,
    api_key_index: int,
    json_schema: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Calls the Dedalus LLM API and returns a parsed JSON response.
    """
    if not (0 <= api_key_index < len(DEDALUS_API_KEYS) and DEDALUS_API_KEYS[api_key_index]):
        print(f"ERROR: Dedalus API key at index {api_key_index} is not configured.")
        return None

    api_key = DEDALUS_API_KEYS[api_key_index]
    if 'your_' in api_key:
        print(f"WARNING: Cannot call Dedalus. API key at index {api_key_index} is a placeholder.")
        return None

    # Dedalus API endpoint ( OpenAI compatible )
    dedalus_api_url = "https://api.dedaluslabs.ai/v1/chat/completions"

    full_system_prompt = f"""{system_prompt}

You MUST respond with a valid JSON object that conforms to the following schema.
Do NOT include any other text, explanations, or markdown code fences.

JSON Schema:
{json.dumps(json_schema, indent=2)}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Dedalus supports various models. Using a standard provider/model identifier.
    payload = {
        "model": "openai/gpt-4o-mini", 
        "messages": [
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"}
    }

    try:
        # print(f"Calling Dedalus API (key_index={api_key_index})...")
        response = requests.post(dedalus_api_url, headers=headers, json=payload, timeout=90)
        
        if response.status_code != 200:
            print(f"ERROR: Dedalus API returned status {response.status_code}")
            print(f"Response: {response.text}")
            return None

        result = response.json()
        llm_response_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not llm_response_text:
            print("ERROR: Empty response from Dedalus API.")
            return None

        # Fallback parsing if the model still wraps in markdown despite instructions
        if "```json" in llm_response_text:
            match = re.search(r"```json\n(.*?)\n```", llm_response_text, re.DOTALL)
            if match:
                llm_response_text = match.group(1)
        elif "```" in llm_response_text:
            match = re.search(r"```\n?(.*?)\n?```", llm_response_text, re.DOTALL)
            if match:
                llm_response_text = match.group(1)

        return json.loads(llm_response_text)

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Dedalus API call failed: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to decode JSON response from LLM: {e}")
        print(f"Raw response: {llm_response_text[:500]}")
        return None

# ============================================================================
# Database Helper Functions
# ============================================================================

def log_agent_output(agent_name: str, run_id: UUID, payload: Dict[str, Any], summary: str) -> bool:
    """Inserts a log entry into the agent_logs table."""
    if not supabase:
        print("ERROR: Supabase client not available. Cannot log agent output.")
        return False
    try:
        data = {"agent_name": agent_name, "run_id": str(run_id), "payload": payload, "summary": summary}
        supabase.table("agent_logs").insert(data).execute()
        print(f"Successfully logged output for {agent_name} with run_id {run_id}.")
        return True
    except Exception as e:
        print(f"ERROR: Failed to log agent output for {agent_name}: {e}")
        return False

def get_drugs_inventory() -> Optional[List[Dict[str, Any]]]:
    """Fetches the full drugs inventory, ordered by criticality."""
    if not supabase: return None
    try:
        return supabase.table("drugs").select("*").order("criticality_rank", desc=False).execute().data
    except Exception as e:
        print(f"ERROR: Failed to fetch drugs inventory: {e}")
        return None

def get_unresolved_shortages(days_back: int = 180) -> Optional[List[Dict[str, Any]]]:
    """Fetches unresolved shortages within a given time window."""
    if not supabase: return None
    try:
        start_date = (datetime.now() - timedelta(days=days_back)).isoformat()
        return supabase.table("shortages").select("*").eq("resolved", False).gte("reported_date", start_date).execute().data
    except Exception as e:
        print(f"ERROR: Failed to fetch unresolved shortages: {e}")
        return None

def get_surgery_schedule(days_ahead: int = 30) -> Optional[List[Dict[str, Any]]]:
    """Fetches all scheduled surgeries within a given future timeframe."""
    if not supabase: return None
    try:
        end_date = (datetime.now() + timedelta(days=days_ahead)).isoformat()
        return supabase.table("surgery_schedule").select("*").eq("status", "SCHEDULED").lte("scheduled_date", end_date).execute().data
    except Exception as e:
        print(f"ERROR: Failed to fetch surgery schedule: {e}")
        return None

def get_suppliers(active_only: bool = True) -> Optional[List[Dict[str, Any]]]:
    """Fetches suppliers from the database, optionally filtering for active ones."""
    if not supabase: return None
    try:
        query = supabase.table("suppliers").select("*")
        if active_only:
            query = query.eq("active", True)
        return query.execute().data
    except Exception as e:
        print(f"ERROR: Failed to fetch suppliers: {e}")
        return None

def get_substitutes(drug_name: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
    """Fetches substitute drugs, optionally filtered by the original drug name."""
    if not supabase: return None
    try:
        query = supabase.table("substitutes").select("*")
        if drug_name:
            query = query.eq("drug_name", drug_name)
        return query.order("preference_rank", desc=False).execute().data
    except Exception as e:
        print(f"ERROR: Failed to fetch substitutes: {e}")
        return None

def get_agent_logs(run_id: UUID, agent_name: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
    """Fetches agent logs for a specific run, optionally filtered by agent name."""
    if not supabase: return None
    try:
        query = supabase.table("agent_logs").select("payload").eq("run_id", str(run_id))
        if agent_name:
            query = query.eq("agent_name", agent_name)
        
        response = query.order("created_at", desc=False).execute()
        return response.data
    except Exception as e:
        print(f"ERROR: Failed to fetch agent logs for run_id {run_id}: {e}")
        return None

if __name__ == '__main__':
    print("--- Running shared.py self-test ---")
    if supabase:
        print("Testing database connection...")
        inventory = get_drugs_inventory()
        if inventory is not None:
            print(f"✓ Successfully fetched {len(inventory)} drugs from the database.")
        else:
            print("✗ Failed to fetch drugs from the database.")
    else:
        print("✗ Supabase client is not available. Database tests skipped.")
    
    print("\n--- Self-test complete ---")