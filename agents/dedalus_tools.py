from dedalus_mcp import tool
from agents.shared import supabase

@tool(
    description="Deletes all unacknowledged (active) alerts from the database for monitored drugs. This clears the dashboard of stale or redundant entries before new analysis.",
)
def delete_redundant_entries() -> str:
    """
    Deletes duplicate active alerts (keeps the newest per key).
    Key: alert_type + drug_name + title.
    Returns a summary string of actions taken.
    """
    if not supabase:
        return "Error: Supabase client not available."

    try:
        # Fetch all alerts that are unacknowledged
        response = supabase.table("alerts").select("id,alert_type,drug_name,title,created_at").eq("acknowledged", False).execute()
        alerts = response.data or []
        
        if not alerts:
            return "No active alerts found to clear."

        # Group by key and keep newest (by created_at)
        groups = {}
        for alert in alerts:
            key = f"{alert.get('alert_type')}|{alert.get('drug_name')}|{alert.get('title')}"
            groups.setdefault(key, []).append(alert)

        ids_to_delete = []
        for key, items in groups.items():
            if len(items) <= 1:
                continue
            # Sort newest first; if created_at missing, keep first
            items.sort(key=lambda a: a.get('created_at') or '', reverse=True)
            # Keep the first, delete the rest
            ids_to_delete.extend([a['id'] for a in items[1:] if a.get('id')])

        deleted_count = len(ids_to_delete)

        if ids_to_delete:
            # Delete all found alerts
            supabase.table("alerts").delete().in_("id", ids_to_delete).execute()
            return f"Successfully deleted {deleted_count} duplicate alerts."
        else:
            return "No duplicate alerts found."

    except Exception as e:
        return f"Error executing delete_redundant_entries: {str(e)}"
