from dedalus_mcp import tool
from agents.shared import supabase

@tool(
    description="Deletes all unacknowledged (active) alerts from the database for monitored drugs. This clears the dashboard of stale or redundant entries before new analysis.",
)
def delete_redundant_entries() -> str:
    """
    Clears all 'alerts' where acknowledged=False to prepare for a fresh run.
    This ensures no duplicates exist when new alerts are generated.
    Returns a summary string of actions taken.
    """
    if not supabase:
        return "Error: Supabase client not available."

    try:
        # Fetch all alerts that are unacknowledged
        response = supabase.table("alerts").select("id").eq("acknowledged", False).execute()
        alerts = response.data
        
        if not alerts:
            return "No active alerts found to clear."

        ids_to_delete = [alert['id'] for alert in alerts]
        deleted_count = len(ids_to_delete)

        if ids_to_delete:
            # Delete all found alerts
            supabase.table("alerts").delete().in_("id", ids_to_delete).execute()
            return f"Successfully cleared {deleted_count} stale alerts to prepare for new analysis."
        else:
            return "No stale alerts found."

    except Exception as e:
        return f"Error executing delete_redundant_entries: {str(e)}"
