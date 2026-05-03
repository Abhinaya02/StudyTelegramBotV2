import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from config import ADMIN_ID
import os
import sys

# Ensure services can be imported based on app structure
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.document import extract_text_from_pdf, download_telegram_file
from services.gemini import generate_daily_content, save_to_content_queue
from database.client import supabase
from jobs.broadcast import trigger_broadcast

async def process_generation(update: Update, context: ContextTypes.DEFAULT_TYPE, source_text: str = None):
    # Depending if this is from a CallbackQuery or Command
    message = update.callback_query.message if update.callback_query else update.message
    
    # Generate content
    await message.reply_text("⚙️ Generating draft. This might take a few seconds...")
    draft = generate_daily_content(source_text)
    
    if draft.startswith("❌"):
        await message.reply_text(draft)
        return
        
    # Save to Queue as PENDING
    content_id = save_to_content_queue(ADMIN_ID, draft)
    
    if not content_id:
        await message.reply_text("❌ Failed to save draft to DB. Please ensure your Telegram ID is registered in the users table.")
        return
        
    # Send draft for review
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve & Broadcast", callback_data=f"content_approve_{content_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"content_reject_{content_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        f"📝 **DRAFT READY (ID: {content_id[:6]}...)**\n\n{draft}",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("content_approve_"):
        content_id = query.data.replace("content_approve_", "")
        
        # 1. Update DB Status
        try:
            supabase.table("content_queue").update({"status": "APPROVED"}).eq("id", content_id).execute()
        except Exception as e:
            await query.edit_message_text(f"❌ DB Error: {e}")
            return
            
        await query.edit_message_text(f"✅ Approved content {content_id[:6]}... Starting broadcast!")
        
        # 2. Trigger Broadcast Task (non-blocking)
        asyncio.create_task(trigger_broadcast(context.bot, content_id))
        
    elif query.data.startswith("content_reject_"):
        content_id = query.data.replace("content_reject_", "")
        try:
            supabase.table("content_queue").update({"status": "REJECTED"}).eq("id", content_id).execute()
        except:
            pass
        await query.edit_message_text(f"❌ Rejected content {content_id[:6]}...")
    
    elif query.data == "generate_from_file":
        source_text = context.user_data.get('latest_upload') if hasattr(context, 'user_data') else None
        await query.edit_message_text("⚙️ Starting generation based on the uploaded file...")
        await process_generation(update, context, source_text)

async def admin_document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle PDF or Text file uploads from Admin."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
        
    doc = update.message.document
    if doc.mime_type != 'application/pdf':
        await update.message.reply_text("⚠️ Currently only accepting PDF notes.")
        return
        
    await update.message.reply_text(f"📥 Downloading and parsing '{doc.file_name}'...")
    
    # Download file (use a secure temp path in production)
    file_path = f"/tmp/{doc.file_name}"
    await download_telegram_file(doc.file_id, context.bot, file_path)
    
    # Extract text
    raw_text = extract_text_from_pdf(file_path)
    try:
        os.remove(file_path) # Cleanup
    except OSError:
        pass
    
    if not raw_text:
        await update.message.reply_text("❌ Failed to extract text from the document.")
        return
        
    # Store the extracted context temporarily in Bot Context or DB
    if not hasattr(context, 'user_data'):
        context.user_data = {}
    context.user_data['latest_upload'] = raw_text
    
    keyboard = [[InlineKeyboardButton("🚀 Generate AI Content", callback_data="generate_from_file")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Extraction complete! Length: {len(raw_text)} chars.\n\nWould you like to generate today's content using this as source material?",
        reply_markup=reply_markup
    )

async def admin_generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trigger daily generation (Autonomous if no file provided)."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Unauthorized. Admin-only command.")
        return
        
    await update.message.reply_text("🛠️ Triggering AUTONOMOUS Generation (No source file provided)...")
    await process_generation(update, context)