import logging
import datetime
from telegram import Update
from telegram.ext import ContextTypes

from services.gemini import client as gemini_client
from google.genai import types
from utils.formatting import to_telegram_html
from utils.time_helper import get_ist_now
from database.client import load_today_lesson, load_user_progress

logger = logging.getLogger(__name__)

async def revise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lesson = load_today_lesson() or {}
    vocab = lesson.get("vocab")
    idiom = lesson.get("idiom")
    gk = lesson.get("gk_fact")
    current_affairs = lesson.get("current_affairs")
    
    if not (vocab or idiom or gk or current_affairs):
        await update.message.reply_text(
            "<b>No intel logged yet today.</b> Wait for your morning brief, idiom, GK shot, or current affairs.",
            parse_mode="HTML"
        )
        return
    
    parts = []
    if vocab:
        parts.append(f"VOCAB: {vocab}")
    if idiom:
        parts.append(f"IDIOM: {idiom}")
    if gk:
        parts.append(f"STATIC GK: {gk}")
    if current_affairs:
        parts.append(f"CURRENT AFFAIRS: {current_affairs}")
    
    context_str = "\n\n".join(parts)
    prompt = (
        "Create a SHORT AFCAT revision sheet from the content below.\n"
        "Use ONLY <b> and line breaks. No Markdown (* or **).\n\n"
        "FORMAT (STRICT):\n"
        "<b>🔁 QUICK REVISION</b>\n"
        "• [point 1]\n"
        "• [point 2]\n"
        "• [point 3]\n"
        "Max 7 bullets, each under 18–20 words.\n\n"
        f"CONTENT:\n{context_str}"
    )
    
    try:
        if not gemini_client:
            raise ValueError("Gemini client not initialized")
            
        response = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        text = to_telegram_html(response.text or "")
        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Revise failed: {e}")
        await update.message.reply_text(
            "⚠️ <b>Revision sheet offline.</b> AI is temporarily unavailable.",
            parse_mode="HTML",
        )

async def debug_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    userid = update.effective_chat.id
    progress = load_user_progress(userid)
    lesson = load_today_lesson() or {}
    
    now = get_ist_now()
    
    job_names = [job.name for job in context.job_queue.jobs()]
    
    debug_msg = f"""<b>🔧 SYSTEM DEBUG REPORT</b>

<b>Current Time (IST):</b> {now.strftime('%H:%M:%S')}
<b>Current Streak:</b> {progress.get('streak', 0)} Days
<b>Last Correct:</b> {progress.get('last_correct_date', 'Never')}

<b>DAILY MEMORY STATUS</b>
Vocab: {'✅' if lesson.get('vocab') else '❌'}
Idiom: {'✅' if lesson.get('idiom') else '❌'}
Static GK: {'✅' if lesson.get('gk_fact') else '❌'}
Current Affairs: {'✅' if lesson.get('current_affairs') else '❌'}

<b>ACTIVE JOBS</b>
{', '.join(job_names) if job_names else 'None'}
"""
    await update.message.reply_text(debug_msg, parse_mode="HTML")

async def testquiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from jobs.daily_scheduler import send_pop_quiz
    await update.message.reply_text("Testing pop quiz...", parse_mode="HTML")
    await send_pop_quiz(context, manual_chatid=update.effective_chat.id)

async def manual_idiom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from jobs.daily_scheduler import send_idiom_drop
    await update.message.reply_text("Triggering idiom drop...", parse_mode="HTML")
    await send_idiom_drop(context, manual_chatid=update.effective_chat.id)

async def manual_gk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from jobs.daily_scheduler import send_gk_shot
    await update.message.reply_text("Triggering GK shot...", parse_mode="HTML")
    await send_gk_shot(context, manual_chatid=update.effective_chat.id)

async def manual_ca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from jobs.daily_scheduler import send_current_affairs_shot
    await update.message.reply_text("Triggering Current Affairs shot...", parse_mode="HTML")
    await send_current_affairs_shot(context, manual_chatid=update.effective_chat.id)

async def week_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import ADMIN_ID
    if update.effective_chat.id != int(ADMIN_ID or 0):
        await update.message.reply_text("Unauthorized.", parse_mode="HTML")
        return
    
    from jobs.weekly_scheduler import send_weekly_notes
    await update.message.reply_text("Generating weekly notes PDF...", parse_mode="HTML")
    await send_weekly_notes(context, manual_chatid=update.effective_chat.id)

async def trigger_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from jobs.weekly_scheduler import send_sunday_review
    await update.message.reply_text("Triggering sunday review...", parse_mode="HTML")
    await send_sunday_review(context, manual_chatid=update.effective_chat.id)
