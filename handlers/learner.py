from telegram import Update
from telegram.ext import ContextTypes
from database.client import get_or_create_user

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    
    # Save user to Supabase
    db_user = get_or_create_user(user.id)
    
    xp = db_user.get("xp", 0)
    level = db_user.get("level", 1)
    
    msg = (f"Hi {user.first_name}! 🎓\n"
           f"Welcome to your AI Learning Companion.\n\n"
           f"📊 Your Stats:\n"
           f"Level: {level} | XP: {xp}\n\n"
           f"Stay tuned for the daily missions!")
           
    await update.message.reply_text(msg)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Send me a question to use the Chatbot mode, or answer daily quizzes to earn XP!")
