
from agents.shared import supabase
from collections import defaultdict

def verify():
    print("Verifying alert deduplication...")
    if not supabase:
        print("Supabase client missing.")
        return

    response = supabase.table("alerts").select("*").eq("acknowledged", False).execute()
    alerts = response.data
    
    if not alerts:
        print("No active alerts to check.")
        return

    groups = defaultdict(list)
    duplicates_found = 0
    
    for alert in alerts:
        key = (alert['drug_name'], alert['alert_type'], alert['severity'])
        groups[key].append(alert)

    for key, group in groups.items():
        if len(group) > 1:
            print(f"FAIL: Found {len(group)} duplicates for {key}")
            duplicates_found += 1
    
    if duplicates_found == 0:
        print("SUCCESS: No duplicate active alerts found.")
    else:
        print(f"FAIL: Found {duplicates_found} groups with duplicates.")

if __name__ == "__main__":
    verify()
