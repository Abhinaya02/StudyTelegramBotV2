import os
from supabase import create_client, Client
from dotenv import load_dotenv
from utils.time_helper import get_ist_date_string

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase credentials in .env")

# Initialize and export the client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Example helper function
def get_or_create_user(telegram_id: int):
    # Try to fetch existing user
    response = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
    
    if response.data:
        # Update last active
        supabase.table("users").update({"last_active_at": "now()"}).eq("telegram_id", telegram_id).execute()
        return response.data[0]
    
    # Create new user
    new_user = {
        "telegram_id": telegram_id,
        "role": "LEARNER"
    }
    response = supabase.table("users").insert(new_user).execute()
    return response.data[0]

def get_target_users(manual_chat_id=None):
    if manual_chat_id:
        return [{"telegram_id": manual_chat_id, "displayname": "Admin"}]
    else:
        response = supabase.table("users").select("telegram_id, role").eq("role", "LEARNER").execute()
        return response.data

def get_or_init_today_lesson():
    date_str = get_ist_date_string()
    response = supabase.table("daily_shots").select("*").eq("lesson_date", date_str).execute()
    if response.data:
        return response.data[0]
    else:
        new_row = {"lesson_date": date_str}
        res = supabase.table("daily_shots").insert(new_row).execute()
        return res.data[0]

def load_today_lesson():
    date_str = get_ist_date_string()
    response = supabase.table("daily_shots").select("*").eq("lesson_date", date_str).execute()
    if response.data:
        return response.data[0]
    return {}

def update_today_lesson(data_dict):
    date_str = get_ist_date_string()
    supabase.table("daily_shots").update(data_dict).eq("lesson_date", date_str).execute()

def load_user_progress(chat_id):
    # In V2, progress metrics are merged with the 'users' table
    res = supabase.table("users").select("*").eq("telegram_id", chat_id).execute()
    if res.data:
        return {"streak": res.data[0].get("streak", 0), "last_correct_date": res.data[0].get("last_correct_date")}
    return {}
