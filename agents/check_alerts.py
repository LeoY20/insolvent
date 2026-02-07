from agents.shared import supabase
import sys
import json

if not supabase:
    print("No Supabase client available.")
    sys.exit(1)

drug_name = "Propofol"
print(f"Checking all alerts for {drug_name}...")

response = supabase.table("alerts").select("*").eq("drug_name", drug_name).execute()
alerts = response.data

print(f"Found {len(alerts)} alerts for {drug_name}:")
for a in alerts:
    print(f"- {a['id'][:8]}... | {a['created_at']} | {a['alert_type']} | {a['title']} | ACK: {a['acknowledged']}")

# Also check for latest non-Propofol alerts just in case
print("\nChecking latest 5 alerts (any drug):")
response = supabase.table("alerts").select("id,created_at,drug_name,alert_type,acknowledged").order("created_at", desc=True).limit(5).execute()
for a in response.data:
    print(f"- {a['id'][:8]}... | {a['created_at']} | {a['drug_name']} : {a['alert_type']} | ACK: {a['acknowledged']}")
