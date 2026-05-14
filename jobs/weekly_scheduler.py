import logging
import datetime
from io import BytesIO
import requests
from telegram.ext import ContextTypes

from database.client import supabase
from services.gemini import client

logger = logging.getLogger(__name__)

import subprocess
import tempfile
import os

def build_weekly_pdf_cloud(html_content: str) -> BytesIO:
    full_html = f"""<!DOCTYPE html>
<html>
<head>
<style>
body {{
    font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    color: #1a202c;
    line-height: 1.6;
    padding: 40px;
    background-color: #ffffff;
}}
h1 {{
    color: #2b6cb0;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 10px;
    font-size: 28px;
}}
h2 {{
    color: #2d3748;
    margin-top: 30px;
    font-size: 20px;
}}
ul {{
    background: #f7fafc;
    padding: 20px 20px 20px 40px;
    border-radius: 8px;
    border: 1px solid #edf2f7;
}}
li {{
    margin-bottom: 12px;
    font-size: 15px;
}}
strong {{
    color: #c53030;
}}
</style>
</head>
<body>
{html_content}
</body>
</html>
"""

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as html_file:
        html_file.write(full_html.encode('utf-8'))
        html_temp_path = html_file.name

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as pdf_file:
        pdf_temp_path = pdf_file.name

    try:
        script_path = os.path.join(os.path.dirname(__file__), "generate_pdf.js")
        
        result = subprocess.run(
            ["node", script_path, html_temp_path, pdf_temp_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"Playwright PDF Error: {result.stderr}")

        with open(pdf_temp_path, "rb") as f:
            pdf_bytes = f.read()

        return BytesIO(pdf_bytes)
    finally:
        if os.path.exists(html_temp_path):
            os.remove(html_temp_path)
        if os.path.exists(pdf_temp_path):
            os.remove(pdf_temp_path)

async def send_weekly_notes(context: ContextTypes.DEFAULT_TYPE, manual_chatid: int = None):
    # Fetch last 7 days of lessons
    try:
        response = supabase.table("daily_shots").select("*").order("lesson_date", desc=True).limit(7).execute()
        rows = response.data
    except Exception as e:
        logger.error(f"Failed to fetch weekly lessons: {e}")
        return

    if not rows:
        return

    blocks = [
        f"{r.get('lesson_date')} {r.get('vocab', '')} {r.get('idiom', '')} {r.get('gk_fact', '')}"
        for r in reversed(rows)
    ]
    context_str = "\\n\\n".join(blocks)

    prompt = (
        "Create concise, beautiful WEEKLY STUDY NOTES for an AFCAT aspirant from the content below.\\n"
        "Output ONLY raw HTML. Do not use Markdown, do not wrap in ```html blocks. Just start with <h1>.\\n"
        "Use emojis generously. Use <h1> for the main title, <h2> for sections, and <ul>/<li> for lists. Use <strong> to highlight key words.\\n\\n"
        "FORMAT EXAMPLE:\\n"
        "<h1>📒 WEEKLY AFCAT INTELLIGENCE REPORT</h1>\\n"
        "<h2>🧠 Key Vocabulary</h2>\\n"
        "<ul><li><strong>Prudent:</strong> careful, future-focused</li></ul>\\n\\n"
        "Now generate the HTML notes based on this content:\\n"
        f"{context_str}"
    )

    try:
        from services.gemini import generate_content_with_fallback
        
        raw_html = generate_content_with_fallback(contents=prompt)
        raw_html = raw_html.strip().replace("```html", "").replace("```", "")

        pdf_bytes = build_weekly_pdf_cloud(raw_html).getvalue()
        
        # Decide targets
        if manual_chatid:
             targets = [{"telegram_id": manual_chatid}]
        else:
             target_res = supabase.table("users").select("telegram_id, role").eq("role", "LEARNER").execute()
             targets = target_res.data
             
        today = datetime.date.today()

        for u in targets:
            chat_id = u["telegram_id"]
            try:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=BytesIO(pdf_bytes),
                    filename=f"AFCAT_Notes_{today.strftime('%b%d')}.pdf",
                    caption="<b>Your Weekly AFCAT Intelligence Report is ready.</b>",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to send weekly PDF to {chat_id}: {e}")

    except Exception as e:
        logger.error(f"Weekly PDF Error: {e}")
        if manual_chatid:
            try:
                await context.bot.send_message(
                    chat_id=manual_chatid,
                    text="<b>PDF Generation Failed</b> - API offline.",
                    parse_mode="HTML"
                )
            except:
                pass
