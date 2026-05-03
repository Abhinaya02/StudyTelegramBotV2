import logging
from database.client import supabase
from utils.time_helper import get_ist_date_string

logger = logging.getLogger(__name__)

def record_user_activity(user_id: int):
    """Marks the user active today in the database."""
    ist_date = get_ist_date_string()
    try:
        # Get existing progress
        progress_res = supabase.table("user_progress").select("*").eq("user_id", user_id).execute()
        if not progress_res.data:
            supabase.table("user_progress").insert({
                "user_id": user_id,
                "last_active_date": ist_date,
                "streak": 0
            }).execute()
            return

        progress = progress_res.data[0]
        if progress.get("last_active_date") != ist_date:
            supabase.table("user_progress").update({
                "last_active_date": ist_date
            }).eq("user_id", user_id).execute()
            
    except Exception as e:
        logger.error(f"Failed to record user activity for {user_id}: {e}")

def increment_streak(user_id: int) -> int:
    """Increments the user's streak if they completed tasks correctly."""
    ist_date = get_ist_date_string()
    try:
        res = supabase.table("user_progress").select("streak, last_correct_date").eq("user_id", user_id).execute()
        streak = 0
        
        if res.data:
            progress = res.data[0]
            last_correct = progress.get("last_correct_date")
            streak = progress.get("streak") or 0
            
            # If already updated today, don't increment again
            if last_correct == ist_date:
                return streak
                
            streak += 1
            
        supabase.table("user_progress").upsert({
            "user_id": user_id,
            "streak": streak,
            "last_correct_date": ist_date,
            "last_active_date": ist_date
        }).execute()
        
        return streak
    except Exception as e:
        logger.error(f"Failed to increment streak for {user_id}: {e}")
        return 0

def log_quiz_history(user_id: int, question: str, is_correct: bool, category: str):
    try:
        supabase.table("quiz_history").insert({
            "user_id": user_id,
            "question": question,
            "is_correct": is_correct,
            "category": category,
        }).execute()
    except Exception as e:
        logger.error(f"Quiz history log failed: {e}")
