import logging
from telegram import Update
from telegram.ext import ContextTypes
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GEMINI_API_KEY
from database.client import supabase
from google import genai

# Setup Gemini
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    logging.error(f"Failed to init GenAI client: {e}")
    client = None

def get_learner_context(user_id: int):
    # Fetch some history or profile context if needed
    try:
        resp = supabase.table("users").select("xp").eq("telegram_id", user_id).execute()
        return resp.data[0]['xp'] if resp.data else 0
    except:
        return 0

async def learner_chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_msg = update.message.text
    
    # Simple check to not reply to commands
    if user_msg.startswith("/"):
        return
        
    if not client:
        await update.message.reply_text("❌ AI Tutor is currently offline.")
        return

    xp = get_learner_context(user_id)
    
    system_prompt = f"""You are the AFCAT Tactical Mentor.
    The candidate has {xp} XP. Maintain a disciplined yet motivating tone.
    
    STRICT RULES:
    1. Keep answers extremely concise and mission-focused.
    2. Use ONLY <b> for bold and <i> for italics.
    3. ABSOLUTELY NO MARKDOWN (* or **). NO headers (like # heading).
    4. Focus on exam relevance for AFCAT/CDS.
    5. Answer the user's query with precision."""

    try:
        from services.gemini import generate_content_with_fallback
        # We can implement full conversation history, but keeping it stateless for Phase 7
        response_text = generate_content_with_fallback(contents=f"System Prompt: {system_prompt}\n\nUser query: {user_msg}")
        await update.message.reply_text(response_text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Chat error: {e}")
        await update.message.reply_text("🤔 Hmm... Let me think about that. Please ask again later.")
