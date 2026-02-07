from agents.shared import supabase
import sys
import uuid
import datetime

if not supabase:
    print("No Supabase client available.")
    sys.exit(1)

run_id = str(uuid.uuid4())
drug_name = "Propofol"
alert = {
    "run_id": run_id,
    "alert_type": "RESTOCK_NOW",
    "severity": "CRITICAL",
    "drug_name": drug_name,
    "title": "Test Alert - Propofol Low Stock",
    "description": "This is a test alert created by the debugger.",
    "action_required": True,
    "acknowledged": False,
    "created_at": datetime.datetime.now().isoformat()
}

print(f"Inserting test alert for {drug_name}...")
data = supabase.table("alerts").insert(alert).execute()
print(f"Inserted: {data.data}")
