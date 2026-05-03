import logging
from google import genai
from config import GEMINI_API_KEY
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.client import supabase

# Initialize the Gemini GenAI client
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    logging.error(f"Failed to init GenAI client: {e}")
    client = None

def get_base_prompt():
    return """You are an expert curriculum designer. 
TASK:
1. Provide 3 major recent global news summaries.
2. Teach 1 common English Idiom with an origin story and example.
3. Create 3 Multiple Choice Questions.

FORMAT INSTRUCTIONS:
Use Telegram-friendly Markdown (Bold *text*, Italics _text_).
Do not use markdown headers (like # heading) as Telegram does not support them."""

def generate_daily_content(source_text: str = None) -> str:
    """Generate content, optionally based on a source text."""
    if not client:
        return "❌ Generative AI client is not configured."
        
    prompt = get_base_prompt()
    if source_text:
        prompt = f"Based on this SOURCE_TEXT: {source_text}\n\n{prompt}"
        
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        logging.error(f"Gemini generation error: {e}")
        return f"❌ Error generating content: {e}"

def save_to_content_queue(admin_id: int, content_text: str) -> str:
    """Save generated text to the pending queue and return the DB uuid."""
    try:
        # First get the admin's UUID from the telegram_id
        resp = supabase.table("users").select("id").eq("telegram_id", admin_id).execute()
        if not resp.data:
            return None
            
        admin_uuid = resp.data[0]['id']
        
        new_item = {
            "type": "DAILY_MIX",
            "raw_generated_text": content_text,
            "status": "PENDING",
            "admin_id": admin_uuid
        }
        
        insert_resp = supabase.table("content_queue").insert(new_item).execute()
        return insert_resp.data[0]['id'] if insert_resp.data else None
    except Exception as e:
        logging.error(f"DB Error save_to_content_queue: {e}")
        return None
