import logging
import json
from database.client import supabase

logger = logging.getLogger(__name__)

def get_user_session(user_id: int) -> dict:
    """Retrieves the user's current session state from the database."""
    try:
        res = supabase.table("user_sessions").select("state_data").eq("user_id", user_id).execute()
        if res.data:
            return res.data[0].get("state_data", {})
    except Exception as e:
        logger.error(f"Failed to get session for {user_id}: {e}")
    return {}

def update_user_session(user_id: int, new_data: dict, clear: bool = False):
    """Updates or merges the user's session state. Clears if requested."""
    try:
        if clear:
            supabase.table("user_sessions").upsert({"user_id": user_id, "state_data": {}}).execute()
            return
            
        current = get_user_session(user_id)
        current.update(new_data)
        
        supabase.table("user_sessions").upsert({
            "user_id": user_id,
            "state_data": current
        }).execute()
    except Exception as e:
        logger.error(f"Failed to update session for {user_id}: {e}")
