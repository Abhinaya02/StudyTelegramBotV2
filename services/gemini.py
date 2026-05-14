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
    return """You are the Lead AFCAT Curriculum Designer at the Air Force Intelligence Cell. 
TASK:
1. Provide 3 major recent global news summaries with tactical relevance.
2. Teach 1 high-frequency English Idiom with origin and officer-context example.
3. Create 3 Multiple Choice Questions (Vocab, Idiom, GK).

🚨 STRICT FORMATTING:
1. Use ONLY <b> for bold and <i> for italics.
2. ABSOLUTELY NO MARKDOWN (* or **). NO headers (#).
3. Professional, disciplined tone throughout."""

def generate_content_with_fallback(contents: str, **kwargs) -> str:
    """Attempt to generate content using multiple models in case of failure (like 503 HTTP errors)."""
    import time
    if not client:
         return "❌ Generative AI client is not configured."
         
    models = ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash', 'gemini-2.0-flash-lite-preview-02-25', 'gemini-2.0-pro-exp-02-05']
    last_error = None
    
    for model_name in models:
        for attempt in range(2): # Try each model 2 times if 503 or 429
            try:
                logging.info(f"Trying model {model_name} (Attempt {attempt + 1})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    **kwargs
                )
                return response.text
            except Exception as e:
                error_str = str(e)
                logging.warning(f"Failed to generate with {model_name}: {error_str}")
                last_error = e
                if "503" in error_str or "429" in error_str:
                    logging.info("Sleeping before retry...")
                    time.sleep(15) # Wait 15s to clear rate limits
                else:
                    break # Skip to next model if it's 404 or other error
            
    logging.error(f"All models failed for content generation. Last error: {last_error}")
    raise Exception(f"Failed to generate content: {last_error}")

async def generate_content_with_fallback_async(contents: str, **kwargs) -> str:
    """Attempt to asynchronously generate content using multiple models in case of failure (like 503 HTTP errors)."""
    import asyncio
    if not client:
         return "❌ Generative AI client is not configured."
         
    models = ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash', 'gemini-2.0-flash-lite-preview-02-25', 'gemini-2.0-pro-exp-02-05']
    last_error = None
    
    for model_name in models:
        for attempt in range(2):
            try:
                logging.info(f"Trying async model {model_name} (Attempt {attempt + 1})...")
                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=contents,
                    **kwargs
                )
                return response.text
            except Exception as e:
                error_str = str(e)
                logging.warning(f"Failed to generate async with {model_name}: {error_str}")
                last_error = e
                if "503" in error_str or "429" in error_str:
                    logging.info("Sleeping before retry...")
                    await asyncio.sleep(15) # Wait 15s to clear rate limits
                else:
                    break # Skip to next model
            
    logging.error(f"All models failed for async content generation. Last error: {last_error}")
    raise Exception(f"Failed to generate async content: {last_error}")

def generate_daily_content(source_text: str = None) -> str:
    """Generate content, optionally based on a source text."""
    if not client:
        return "❌ Generative AI client is not configured."
        
    prompt = get_base_prompt()
    if source_text:
        prompt = f"Based on this SOURCE_TEXT: {source_text}\n\n{prompt}"
        
    try:
        return generate_content_with_fallback(contents=prompt)
    except Exception as e:
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
