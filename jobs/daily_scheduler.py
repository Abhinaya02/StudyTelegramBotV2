import asyncio
import datetime
import html
import logging
import re
import pytz
from io import BytesIO
import wave

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from google.genai import types
from services.gemini import client as gemini_client, generate_content_with_fallback_async
from services.tts_service import generate_tts_audio_once
from database.client import supabase, get_or_init_today_lesson, load_today_lesson, update_today_lesson, get_target_users, load_user_progress
from utils.formatting import to_telegram_html, split_by_length
from utils.time_helper import get_ist_now, get_ist_date_string
from handlers.quiz_handler import QUIZ_SESSIONS, send_next_quiz_question

logger = logging.getLogger(__name__)

async def _send_catchup(context: ContextTypes.DEFAULT_TYPE, header: str, content: str):
    chat_id = context.job.data
    if not chat_id:
        return
        
    safe_content = to_telegram_html(content)
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"📡 <b>CATCH-UP: {header}</b>\n\n{safe_content}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Failed to send catch-up '{header}': {e}")

async def catchup_brief(context: ContextTypes.DEFAULT_TYPE):
    row = load_today_lesson()
    content = row.get("vocab")
    if content:
        await _send_catchup(context, "0800 HRS BRIEFING", content)

async def catchup_idiom(context: ContextTypes.DEFAULT_TYPE):
    row = load_today_lesson()
    content = row.get("idiom")
    if content:
        await _send_catchup(context, "1000 HRS VOCAB DROP", content)

async def catchup_gk(context: ContextTypes.DEFAULT_TYPE):
    row = load_today_lesson()
    content = row.get("gk_fact")
    if content:
        await _send_catchup(context, "1200 HRS TACTICAL GK", content)

async def catchup_current_affairs(context: ContextTypes.DEFAULT_TYPE):
    row = load_today_lesson()
    content = row.get("current_affairs")
    if content:
        await _send_catchup(context, "1400 HRS CURRENT AFFAIRS", content)

async def catchup_warning(context: ContextTypes.DEFAULT_TYPE):
    await _send_catchup(
        context,
        "QUIZ REMINDER",
        "Quick heads up: We’ll send a short quiz at 1900 hrs based on today’s updates. Be ready!"
    )


async def broadcast_mission_brief(context, brief_text, is_manual=False, manual_chatid: int = None):
    brief_text_html = to_telegram_html(brief_text)
    audio_bytes, audio_type = await generate_tts_audio_once(brief_text)

    hour = get_ist_now().hour
    targets = get_target_users(manual_chatid)
    success = 0

    for user in targets:
        chat_id = user["telegram_id"]
        name = user.get("displayname") or "Officer"

        if 5 <= hour < 12:
            prefix = f"<b>GOOD MORNING, {html.escape(name).upper()}!</b>\n\n"
        elif 12 <= hour < 17:
            prefix = f"<b>GOOD AFTERNOON, {html.escape(name).upper()}!</b>\n\n"
        else:
            prefix = f"<b>GOOD EVENING, {html.escape(name).upper()}!</b>\n\n"

        safe_text = prefix + brief_text_html

        try:
            await context.bot.send_message(chat_id=chat_id, text=safe_text, parse_mode="HTML")
            if audio_bytes:
                stream = BytesIO(audio_bytes)
                caption = "🎙️ NEURAL MISSION BRIEF" if audio_type == "Neural" else "gTTS Fallback Brief"
                await context.bot.send_voice(chat_id=chat_id, voice=stream, caption=caption)
            else:
                await context.bot.send_message(chat_id=chat_id, text="<i>Audio offline.</i>", parse_mode="HTML")
            success += 1
        except Exception as e:
            logger.error(f"Delivery failed for {chat_id}: {e}")

async def send_vocab_shot(context, manual_chatid: int = None):
    now = get_ist_now()

    if not manual_chatid and (now.hour < 7 or now.hour >= 21):
        return

    try:
        current_date = now.strftime("%B %d, %Y")
        current_time = now.strftime("%H:%M")

        prompt = (
            f"Today is {current_date}. Generate a High-Yield Vocab Drill for AFCAT preparation.\n\n"
            "FORMAT:\n"
            "🌅 <b>MORNING DISPATCH: VOCAB DRILL</b>\n\n"
            "• <b>[Word 1]</b> - meaning.\n"
            "Synonyms: x, y; Antonyms: a, b\n"
            "<i>Ex: [Formal example sentence]</i>\n\n"
            "Generate exactly 3 words."
        )
        response_text = await generate_content_with_fallback_async(contents=prompt)
        
        get_or_init_today_lesson()
        update_today_lesson({"vocab": response_text})

        await broadcast_mission_brief(context, response_text, is_manual=bool(manual_chatid), manual_chatid=manual_chatid)
    except Exception as e:
        logger.error(f"Scheduled brief failed: {e}")

async def send_idiom_drop(context, manual_chatid: int = None):
    try:
        prompt = (
            "Provide three high-yield English idiom suitable for the AFCAT exam.\n"
            "FORMAT:\n"
            "🎯 <b>TACTICAL IDIOM</b>\n"
            "1) <b>[Idiom 1]</b> - Meaning.\nExample: <i>[Short example sentence]</i>\n\n"
        )
        response_text = await generate_content_with_fallback_async(contents=prompt)
        
        get_or_init_today_lesson()
        update_today_lesson({"idiom": response_text})

        await broadcast_mission_brief(context, response_text, is_manual=bool(manual_chatid), manual_chatid=manual_chatid)
    except Exception as e:
        logger.error(f"Idiom drop failed: {e}")

async def send_gk_shot(context, manual_chatid: int = None):
    try:
        prompt = (
            "Create a Static GK shot covering politics, static gk, geography, and history points for AFCAT.\n"
            "Use ONLY <b> tags, no markdown.\n"
            "FORMAT:\n"
            "🗺️ <b>STATIC GK DRILL</b>\n\n"
            "• <b>Politics:</b> [Fact]\n"
            "• <b>History:</b> [Fact]\n"
            "• <b>Geography:</b> [Fact]\n"
            "• <b>Misc:</b> [Fact]\n"
        )
        response_text = await generate_content_with_fallback_async(
            contents=prompt,
        )
        
        get_or_init_today_lesson()
        update_today_lesson({"gk_fact": response_text})

        raw_text = response_text
        audio_bytes, audio_type = await generate_tts_audio_once(raw_text)
        targets = get_target_users(manual_chatid)
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔍 Explain Context", callback_data="explaingk")]])

        safe_text = to_telegram_html(raw_text)

        for u in targets:
            chat_id = u["telegram_id"]
            try:
                await context.bot.send_message(chat_id=chat_id, text=safe_text, reply_markup=reply_markup, parse_mode="HTML")
                if audio_bytes:
                    stream = BytesIO(audio_bytes)
                    caption = "🎙️ NEURAL MISSION BRIEF" if audio_type == "Neural" else "gTTS Fallback Brief"
                    await context.bot.send_voice(chat_id=chat_id, voice=stream, caption=caption)
            except Exception: pass
            
    except Exception as e:
        logger.error(f"GK Shot failed: {e}")

async def send_current_affairs_shot(context, manual_chatid: int = None):
    try:
        prompt = (
            "Create a Daily Current Affairs drop for AFCAT. Focus on Defence, Sports, and National news.\n"
            "Use ONLY <b> tags, no markdown.\n"
            "FORMAT:\n"
            "📰 <b>CURRENT AFFAIRS SHOT</b>\n\n"
            "• <b>Defence:</b> [News]\n"
            "• <b>Sports:</b> [News]\n"
            "• <b>National:</b> [News]\n"
        )
        response_text = await generate_content_with_fallback_async(
            contents=prompt,
            config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
        )
        
        get_or_init_today_lesson()
        update_today_lesson({"current_affairs": response_text})

        raw_text = response_text
        audio_bytes, audio_type = await generate_tts_audio_once(raw_text)
        targets = get_target_users(manual_chatid)
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔍 Explain Context", callback_data="explaingk")]])

        safe_text = to_telegram_html(raw_text)

        for u in targets:
            chat_id = u["telegram_id"]
            try:
                await context.bot.send_message(chat_id=chat_id, text=safe_text, reply_markup=reply_markup, parse_mode="HTML")
                if audio_bytes:
                    stream = BytesIO(audio_bytes)
                    caption = "🎙️ NEURAL MISSION BRIEF" if audio_type == "Neural" else "gTTS Fallback Brief"
                    await context.bot.send_voice(chat_id=chat_id, voice=stream, caption=caption)
            except Exception: pass
            
    except Exception as e:
        logger.error(f"Current Affairs Shot failed: {e}")

async def send_pop_quiz(context, manual_chatid: int = None):
    lesson = load_today_lesson() or {}
    context_str = f"Vocab: {lesson.get('vocab')}\nIdiom: {lesson.get('idiom')}\nGK: {lesson.get('gk_fact')}\nCurrent Affairs: {lesson.get('current_affairs')}"

    prompt = (
        f"Based on today's content:\n{context_str}\n\n"
        "Generate 4 distinct multiple-choice questions (1 vocab, 1 idiom, 1 gk, 1 current affairs).\n"
        "STRICT FORMATTING RULE: Separate each field with a single pipe '|'.\n"
        "Question Text | Option A | Option B | Option C | Option D | Correct: Letter | Brief Explanation\n"
        "Separate each question with '###'.\n"
    )

    try:
        response_text = await generate_content_with_fallback_async(contents=prompt)
        raw_text = (response_text or "").strip()
        quiz_blocks = [b for b in re.split(r'###|\n\n\n', raw_text) if '|' in b]
        
        if not quiz_blocks:
            if manual_chatid:
                await context.bot.send_message(chat_id=manual_chatid, text="⚠️ <b>No intel available.</b>", parse_mode='HTML')
            return

        targets = get_target_users(manual_chatid)
        for u in targets:
            chat_id = u["telegram_id"]
            if chat_id not in QUIZ_SESSIONS:
                QUIZ_SESSIONS[chat_id] = {}
            user_session = QUIZ_SESSIONS[chat_id]
            user_session['quiz_batch'] = quiz_blocks
            user_session['quiz_index'] = 0
            user_session['quiz_score'] = 0
            
            await send_next_quiz_question(context, chat_id)
            
    except Exception as e:
        logger.error(f"Quiz Battery failed: {e}")

async def send_nightly_recap(context):
    targets = get_target_users()
    for u in targets:
        try:
            await context.bot.send_message(chat_id=u["telegram_id"], text="🌙 <b>MISSION DEBRIEF</b>\nRest well, Officer.", parse_mode="HTML")
        except: pass
