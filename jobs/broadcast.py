import asyncio
import logging
from telegram import Bot
from telegram.error import RetryAfter
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.client import supabase

async def trigger_broadcast(bot: Bot, content_id: str):
    """Sends the approved content to all active learners."""
    
    # 1. Fetch the content
    content_resp = supabase.table("content_queue").select("raw_generated_text").eq("id", content_id).execute()
    if not content_resp.data:
        logging.error("Broadcast failed: Content not found.")
        return
        
    text_to_send = content_resp.data[0]['raw_generated_text']
    
    # 2. Add to Broadcasts table
    new_broadcast = {
        "content_id": content_id,
        "status": "SENDING",
        "target_audience": "ALL"
    }
    b_resp = supabase.table("broadcasts").insert(new_broadcast).execute()
    b_id = b_resp.data[0]['id'] if b_resp.data else None
    
    # 3. Fetch users
    users_resp = supabase.table("users").select("telegram_id").eq("role", "LEARNER").execute()
    users = users_resp.data or []
    
    success_count = 0
    # 4. Loop with safe rate limits (Telegram: ~30 msg/sec limit)
    for user in users:
        try:
            await bot.send_message(
                chat_id=user['telegram_id'], 
                text=text_to_send, 
                parse_mode="Markdown"
            )
            success_count += 1
        except RetryAfter as e:
            logging.warning(f"Rate limited. Sleeping for {e.retry_after}")
            await asyncio.sleep(e.retry_after)
            # Retry once
            try:
                await bot.send_message(chat_id=user['telegram_id'], text=text_to_send, parse_mode="Markdown")
                success_count += 1
            except: pass
        except Exception as e:
            logging.error(f"Failed to send to {user['telegram_id']}: {e}")
            
        # Hard sleep to prevent ban
        await asyncio.sleep(0.05)
        
    # 5. Mark Complete
    if b_id:
        supabase.table("broadcasts").update({"status": "COMPLETED", "success_count": success_count}).eq("id", b_id).execute()
    
    # Let Admin know it finished
    from config import ADMIN_ID
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=f"📢 Broadcast finished.\nSent to: {success_count} users.")
    except:
        pass
