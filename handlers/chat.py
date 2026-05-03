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
    
    system_prompt = f"""You are a friendly Telegram AI Tutor.
    The learner has {xp} XP. Be encouraging!
    Keep answers very concise. Use Markdown Formatting.
    Do not use markdown headers (like # heading).
    Answer the user's question directly."""

    try:
        # We can implement full conversation history, but keeping it stateless for Phase 7
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"System Prompt: {system_prompt}\n\nUser query: {user_msg}",
        )
        await update.message.reply_text(response.text, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Chat error: {e}")
        await update.message.reply_text("🤔 Hmm... Let me think about that. Please ask again later.")
