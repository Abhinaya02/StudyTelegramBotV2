import logging
import traceback
import html
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def global_error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log the error and send a telegram message to notify the developer."""
    logger.error("Exception while handling an update:", exc_info=context.error)

    # Traceback extraction
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"🔴 <b>BOT EXCEPTION</b>\n\n"
        f"<b>Update:</b>\n<pre>{html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}</pre>\n\n"
        f"<b>Error:</b>\n<pre>{html.escape(tb_string[:2000])}</pre>"
    )

    # Notify admin/developer explicitly configured in bot_data
    admin_id = context.bot_data.get("admin_id")
    if admin_id:
        try:
            await context.bot.send_message(
                chat_id=admin_id, text=message, parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to send error alert to admin: {e}")

    # Optionally notify the user gracefully
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Sorry, an internal sector fault occurred. The tech team has been notified. 🛠️",
                parse_mode="HTML"
            )
        except Exception:
            pass
