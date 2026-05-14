import asyncio
import datetime
import html
import logging
import re
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.client import load_user_progress, supabase
from services.gemini import client as gemini_client, generate_content_with_fallback_async
from utils.formatting import markdown_bold_to_html, to_telegram_html, split_by_length

# Global quiz session memory
QUIZ_SESSIONS = {}

async def send_next_quiz_question(context: ContextTypes.DEFAULT_TYPE, chat_id: int, edit_message=None):
    user_session = QUIZ_SESSIONS.get(chat_id)
    if not user_session:
        return

    idx = user_session.get("quiz_index", 0)
    batch = user_session.get("quiz_batch", [])
    total_q = len(batch)
    if not batch:
        return
    
    # strictly force IST
    ist_date = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d")
    
    if idx >= total_q:
        score = user_session.get("quiz_score", 0)
        final_text_1 = f"🎯MISSION COMPLETE!\n{score}/{total_q}"

        progress = load_user_progress(chat_id)
        if not progress:
            progress = {"user_id": chat_id}
            
        db_needs_update = False

        if user_session.get("logged_active_today") != ist_date:
            progress["last_active_date"] = ist_date
            user_session["logged_active_today"] = ist_date
            db_needs_update = True

        from handlers.gamification import add_xp
        
        earned_xp = score * 10
        total_xp = earned_xp
        try:
            if earned_xp > 0:
                total_xp = await add_xp(chat_id, amount=earned_xp)
        except Exception as e:
            logging.error(f"Failed to add XP: {e}")

        if score >= total_q - 1 and total_q > 0:
            last_date = progress.get("last_correct_date")
            
            if last_date != ist_date:
                new_streak = progress.get("streak", 0) + 1
                progress["streak"] = new_streak
                progress["last_correct_date"] = ist_date
                db_needs_update = True
            else:
                new_streak = progress.get("streak", 0)
                
            progress_text = f"\n\n🔥Excellent work, Officer.\nEarned XP: {earned_xp}\nStreak: {new_streak}!"
        else:
            progress_text = (
                f"\n\nEarned XP: {earned_xp}\nRevise today's shots to sharpen your sword.\n"
                "/revise to pull your revision sheet, or /testquiz to try again."
            )

        if db_needs_update:
            try:
                strict_payload = {
                    "last_correct_date": progress.get("last_correct_date"),
                }
                # update users table (V2 structure)
                supabase.table("users").update(strict_payload).eq("telegram_id", chat_id).execute()
                logging.info(f"🚨 COMPLETION UPSERT SENT: {strict_payload}")
            except Exception as e:
                logging.error(f"🚨 COMPLETION UPSERT FAILED: {e}")
                
        full_text = final_text_1 + progress_text

        if edit_message:
            await edit_message.edit_text(full_text, parse_mode="HTML")
        else:
            await context.bot.send_message(chat_id, full_text, parse_mode="HTML")

        await send_correction_key(context, chat_id, batch, total_q)
        return

    parts = [p.strip() for p in batch[idx].split("|")]
    if len(parts) < 6:
        user_session["quiz_index"] = idx + 1
        await send_next_quiz_question(context, chat_id, edit_message)
        return

    try:
        clean_target = (
            parts[5]
            .upper()
            .replace("CORRECT", "")
            .replace("ANSWER", "")
            .replace("OPTION", "")
            .strip()
        )
        correct_letter = re.search(r"[A-D]", clean_target).group(0)
    except Exception:
        correct_letter = "A"

    safe_question = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(parts[0]))

    keyboard = [
        [
            InlineKeyboardButton("A", callback_data=f"quizans|A|{correct_letter}"),
            InlineKeyboardButton("B", callback_data=f"quizans|B|{correct_letter}"),
        ],
        [
            InlineKeyboardButton("C", callback_data=f"quizans|C|{correct_letter}"),
            InlineKeyboardButton("D", callback_data=f"quizans|D|{correct_letter}"),
        ],
    ]

    text = (
        f"<b>QUESTION {idx+1}/{total_q}</b>\n{safe_question}\n\n"
        f"<b>A</b> {html.escape(parts[1])}\n"
        f"<b>B</b> {html.escape(parts[2])}\n"
        f"<b>C</b> {html.escape(parts[3])}\n"
        f"<b>D</b> {html.escape(parts[4])}"
    )

    if edit_message:
        await edit_message.edit_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    else:
        await context.bot.send_message(
            chat_id, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )


async def quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.message.chat_id
    user_session = QUIZ_SESSIONS.get(user_id, {})

    batch = user_session.get("quiz_batch")
    if not batch:
        return await query.edit_message_text(
            "⚠️ <b>Session Expired.</b>", parse_mode="HTML"
        )

    if query.data == "quiz_next":
        user_session["quiz_index"] = user_session.get("quiz_index", 0) + 1
        return await send_next_quiz_question(
            context, user_id, edit_message=query.message
        )

    await query.edit_message_reply_markup(reply_markup=None)

    ist_date = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d")
    
    if user_session.get("logged_active_today") != ist_date:
        try:
            supabase.table("users").update({"last_active_at": "now()"}).eq("telegram_id", user_id).execute()
            user_session["logged_active_today"] = ist_date
        except Exception as e:
            logging.error(f"Failed to update active status on first tap: {e}")

    try:
        data_parts = query.data.split("|")
        if len(data_parts) < 3:
            return

        selected_letter = data_parts[1]
        correct_letter = data_parts[2]

        idx = user_session.get("quiz_index", 0)
        current_q_parts = [p.strip() for p in batch[idx].split("|")]

        letter_map = {"A": 1, "B": 2, "C": 3, "D": 4}
        correct_text = current_q_parts[letter_map.get(correct_letter, 1)]

        raw_explanation = (
            current_q_parts[6] if len(current_q_parts) > 6
            else "Review today's briefing."
        )
        explanation = re.sub(
            r"^(brief\s+)?explanation\s*:\s*", "", raw_explanation,
            flags=re.IGNORECASE
        ).strip()
        explanation = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", explanation)

        is_correct_bool = (selected_letter == correct_letter)

        if is_correct_bool:
            user_session["quiz_score"] = user_session.get("quiz_score", 0) + 1
            header = "✅ <b>CORRECT!</b>"
        else:
            header = f"❌ <b>INCORRECT.</b> (You chose {selected_letter})"

        q_category = "Vocab" if idx in [0, 1] else ("Idiom" if idx == 2 else "GK")

        clean_question_ui = html.escape(current_q_parts[0]).replace("**", "")
        feedback_text = (
            f"{header}\n\n"
            f"<b>Q:</b> {clean_question_ui}\n"
            f"<b>Answer:</b> {correct_letter}) {html.escape(correct_text)}\n\n"
            f"<b>Explanation:</b> <i>{explanation}</i>"
        )

        keyboard = [[InlineKeyboardButton(
            "Next Question ➡️", callback_data="quiz_next"
        )]]

        await query.edit_message_text(
            text=feedback_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )

    except Exception as e:
        logging.error(f"Callback error: {e}")
        await query.message.reply_text("❌ Error processing answer.")


async def explain_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    original_text = query.message.text
    
    prompt = f"""Provide a SHORT, High-Yield Tactical Deep Dive into these GK/News items for an AFCAT aspirant.
🛠️ VERACITY PROTOCOL: Verify facts internally. Ensure accuracy of dates, names, and military terms.

🚨 CRITICAL FORMATTING RULES:
1. Use ONLY <b> for bold and <i> for italics.
2. ABSOLUTELY NO MARKDOWN (* or **). NO other HTML.
3. Keep it concise, professional, and skimmable for an officer candidate.

INPUT:
{original_text}

OUTPUT FORMAT (STRICT):
<b>🔍 GK TACTICAL DEEP DIVE</b>

1️⃣ <b>[Title/Subject]</b>
   - <i>Fact:</i> Concise explanation (max 15 words).
   - <i>Defense Relevance:</i> Why it matters for AFCAT (max 15 words).

Rules:
- Max 3-4 items if multiple found.
- No HTML tags other than <b> and <i>.
"""
    
    response_text = await generate_content_with_fallback_async(contents=prompt)
    deep_dive = to_telegram_html(response_text or "")
    
    full_text = f"<b>DEEP DIVE</b>\n\n{deep_dive}"
    
    for chunk in split_by_length(full_text):
        await query.message.reply_text(chunk, parse_mode="HTML")

async def send_correction_key(context: ContextTypes.DEFAULT_TYPE, chat_id: int, batch: list, total_q: int):
    lines = ["📋 <b>QUIZ CORRECTION KEY</b>"]
    letter_map = {"A": 1, "B": 2, "C": 3, "D": 4}

    for i, raw in enumerate(batch, start=1):
        parts = [p.strip() for p in raw.split("|")]
        if len(parts) < 6:
            continue

        raw_q = parts[0].replace("\n", " ")
        q_text = markdown_bold_to_html(raw_q)
        options = parts[1:5]

        try:
            clean_target = parts[5].upper().replace("CORRECT", "").replace("ANSWER", "").replace("OPTION", "").strip()
            correct_letter_match = re.search(r"[A-D]", clean_target)
            correct_letter = correct_letter_match.group(0) if correct_letter_match else "A"
        except Exception:
            correct_letter = "A"

        correct_index = letter_map.get(correct_letter, 1)
        correct_option = html.escape(options[correct_index - 1])

        raw_expl = parts[6] if len(parts) >= 7 else "Review today’s briefing."
        explanation = markdown_bold_to_html(raw_expl) 

        lines.append(
            f"\n<b>Q{i}</b> {q_text}\n"
            f"<b>Correct</b> {correct_letter}: {correct_option}\n"
            f"<b>Explanation</b> <i>{html.escape(explanation)}</i>"
        )

    if len(lines) <= 1:
        return

    header = lines[0]
    q_lines = lines[1:]

    group_size = 5
    total_groups = (len(q_lines) + group_size - 1) // group_size

    for g in range(total_groups):
        start = g * group_size
        end = start + group_size
        group = q_lines[start:end]

        text = header + "\n\n" + "\n\n".join(group)

        try:
            await context.bot.send_message(chat_id, text, parse_mode="HTML")
            logging.info(f"Correction key sent to {chat_id}")
        except Exception as e:
            logging.error(f"Failed to send correction key to {chat_id}: {e}")
            break
