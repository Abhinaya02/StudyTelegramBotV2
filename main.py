import logging
import datetime
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from config import BOT_TOKEN
from handlers.admin import admin_generate_command, admin_document_handler, admin_callback_handler
from handlers.learner import start_command, help_command
from handlers.gamification import leaderboard_command
from handlers.chat import learner_chat_handler

from handlers.legacy_commands import revise, debug_status, testquiz, manual_idiom, manual_gk, week_pdf, trigger_review
from handlers.quiz_handler import quiz_callback, explain_callback
from jobs.daily_scheduler import (
    send_daily_brief, send_idiom_drop, send_gk_shot,
    send_pop_quiz, send_nightly_recap
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def post_init(application: Application):
    """Schedule the legacy global daily jobs."""
    IST = pytz.timezone('Asia/Kolkata')
    
    # 08:00 AM - Daily Brief
    application.job_queue.run_daily(
        send_daily_brief,
        time=datetime.time(hour=8, minute=0, tzinfo=IST)
    )
    # 10:00 AM - Idiom Drop
    application.job_queue.run_daily(
        send_idiom_drop,
        time=datetime.time(hour=10, minute=0, tzinfo=IST)
    )
    # 12:00 PM - GK Shot
    application.job_queue.run_daily(
        send_gk_shot,
        time=datetime.time(hour=12, minute=0, tzinfo=IST)
    )
    # 07:00 PM - Pop Quiz
    application.job_queue.run_daily(
        send_pop_quiz,
        time=datetime.time(hour=19, minute=0, tzinfo=IST)
    )
    # 11:00 PM - Nightly Recap
    application.job_queue.run_daily(
        send_nightly_recap,
        time=datetime.time(hour=23, minute=0, tzinfo=IST)
    )
    
    logger.info("✅ Global Scheduled Jobs Re-Activated in V2.")

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Learner Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("leaderboard", leaderboard_command))
    
    # Legacy V1 Commands Restored
    application.add_handler(CommandHandler("revise", revise))
    application.add_handler(CommandHandler("debug", debug_status))
    application.add_handler(CommandHandler("testquiz", testquiz))
    application.add_handler(CommandHandler("idiom", manual_idiom))
    application.add_handler(CommandHandler("gk", manual_gk))
    application.add_handler(CommandHandler("weekpdf", week_pdf))
    application.add_handler(CommandHandler("weekreview", trigger_review))

    # Admin Handlers
    application.add_handler(CommandHandler("generate", admin_generate_command))
    application.add_handler(MessageHandler(filters.Document.ALL, admin_document_handler))
    
    # Callbacks
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^approve|^reject|^generate"))
    application.add_handler(CallbackQueryHandler(explain_callback, pattern="^explaingk"))
    application.add_handler(CallbackQueryHandler(quiz_callback, pattern="^quiz_next|^quizans"))

    # General Learner Chat handler (MUST be added after all command handlers)
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), learner_chat_handler))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

