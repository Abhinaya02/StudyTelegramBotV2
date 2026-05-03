import logging
from telegram import Update
from telegram.ext import ContextTypes
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.client import supabase

async def add_xp(user_id: int, amount: int = 10) -> int:
    """Adds XP to user and returns their new total."""
    try:
        # First get current XP
        resp = supabase.table("users").select("xp, id").eq("telegram_id", user_id).execute()
        if not resp.data:
            return 0
            
        current_xp = resp.data[0].get("xp", 0)
        new_xp = current_xp + amount
        
        # Update XP
        supabase.table("users").update({"xp": new_xp}).eq("telegram_id", user_id).execute()
        
        # Create XP history entry
        supabase.table("xp_history").insert({
            "user_id": resp.data[0]['id'],
            "amount": amount,
            "reason": "daily_interaction"
        }).execute()
        
        return new_xp
    except Exception as e:
        logging.error(f"Failed to add XP: {e}")
        return 0

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        resp = supabase.table("users").select("role, xp").eq("role", "LEARNER").order("xp", desc=True).limit(5).execute()
        
        if not resp.data:
            await update.message.reply_text("🏆 Leaderboard is empty!")
            return
            
        msg = "🏆 *Top Learners* 🏆\n\n"
        for i, user in enumerate(resp.data):
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "⭐️"
            # Since we don't store names, we make it somewhat anonymous
            msg += f"{medal} Learner {i+1}: {user['xp']} XP\n"
            
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text("❌ Error fetching leaderboard.")
