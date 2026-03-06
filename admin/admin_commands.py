# ============================================================
# admin/admin_commands.py — Admin-only bot commands
#
# Commands available:
#   /stats           — Bot statistics overview
#   /export          — Export users CSV via pandas
#   /broadcast       — Send message to all users
#   /addpoints       — Manually add / subtract points
#   /resetstreak     — Reset a user's streak
# ============================================================

import io
import logging
from datetime import date, datetime

import pandas as pd
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from models.user import User
from models.checkin import CheckinLog
from services.checkin_service import get_checkins_today
from services.reward_service import add_points
from utils.helpers import admin_only, format_points

logger = logging.getLogger(__name__)

# ConversationHandler states for /broadcast
BROADCAST_TEXT = 10


# ─────────────────────────────────────────────────────────────
# /stats
# ─────────────────────────────────────────────────────────────
@admin_only
async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return bot statistics to the admin."""
    db = context.bot_data["db_session"]()
    try:
        total_users = db.query(User).count()
        users_with_game_id = db.query(User).filter(User.game_id.isnot(None)).count()
        checkins_today = get_checkins_today(db)

        # Active users = checked in within last 7 days
        from datetime import timedelta
        cutoff = date.today() - timedelta(days=7)
        active_users = (
            db.query(User)
            .filter(User.last_checkin >= cutoff)
            .count()
        )

        # Streak stats
        avg_streak_result = db.query(User.streak).all()
        avg_streak = (
            sum(s[0] for s in avg_streak_result) / len(avg_streak_result)
            if avg_streak_result else 0
        )

        text = (
            f"📊 <b>BOT STATISTICS</b>\n"
            f"{'─' * 28}\n\n"
            f"👥 Total users:         <b>{total_users:,}</b>\n"
            f"🎮 With Game ID:        <b>{users_with_game_id:,}</b>\n"
            f"📅 Check-ins today:     <b>{checkins_today:,}</b>\n"
            f"🔥 Active (7d):         <b>{active_users:,}</b>\n"
            f"📈 Avg streak:          <b>{avg_streak:.1f} days</b>\n\n"
            f"🕐 Report time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )

        await update.message.reply_text(text, parse_mode="HTML")

    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# /export
# ─────────────────────────────────────────────────────────────
@admin_only
async def export_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export all users to a CSV file and send to admin."""
    db = context.bot_data["db_session"]()
    try:
        users = db.query(User).all()
        if not users:
            await update.message.reply_text("No users to export.")
            return

        data = [
            {
                "telegram_id": u.telegram_id,
                "username": u.username or "",
                "first_name": u.first_name or "",
                "game_id": u.game_id or "",
                "register_date": u.register_date,
                "last_checkin": u.last_checkin,
                "streak": u.streak,
                "total_checkin": u.total_checkin,
                "points": u.points,
                "referrer_id": u.referrer_id or "",
            }
            for u in users
        ]

        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        df.to_csv(buffer, index=False)
        buffer.seek(0)

        filename = f"users_export_{date.today().isoformat()}.csv"
        await update.message.reply_document(
            document=buffer,
            filename=filename,
            caption=f"📥 Users export — {len(users):,} records",
        )

    except Exception as exc:
        logger.error("export_handler error: %s", exc, exc_info=True)
        await update.message.reply_text("⚠️ Export failed.")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# /broadcast — Two-step conversation
# ─────────────────────────────────────────────────────────────
@admin_only
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start broadcast conversation — ask for message text."""
    await update.message.reply_text(
        "📢 <b>Broadcast</b>\n\n"
        "Send the message you want to broadcast to all users.\n"
        "Supports HTML formatting.\n\n"
        "Send /cancel to abort.",
        parse_mode="HTML",
    )
    return BROADCAST_TEXT


async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive the broadcast text and send to all users."""
    message_text = update.message.text or update.message.caption or ""
    if not message_text:
        await update.message.reply_text("⚠️ Empty message. Broadcast cancelled.")
        return ConversationHandler.END

    db = context.bot_data["db_session"]()
    try:
        users = db.query(User).all()
        total = len(users)

        await update.message.reply_text(
            f"📤 Sending broadcast to <b>{total:,}</b> users…",
            parse_mode="HTML",
        )

        sent, failed = 0, 0
        for user in users:
            try:
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text=f"📢 <b>Announcement</b>\n\n{message_text}",
                    parse_mode="HTML",
                )
                sent += 1
            except Exception:
                failed += 1

        await update.message.reply_text(
            f"✅ Broadcast complete!\n"
            f"   Sent: <b>{sent:,}</b>\n"
            f"   Failed: <b>{failed:,}</b>",
            parse_mode="HTML",
        )

    finally:
        db.close()

    return ConversationHandler.END


async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Broadcast cancelled.")
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────
# /addpoints <telegram_id> <points>
# Example: /addpoints 123456789 100
# ─────────────────────────────────────────────────────────────
@admin_only
async def addpoints_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add or subtract points for a user."""
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text(
            "Usage: <code>/addpoints &lt;telegram_id&gt; &lt;points&gt;</code>\n"
            "Example: <code>/addpoints 123456789 100</code>",
            parse_mode="HTML",
        )
        return

    try:
        target_id = int(args[0])
        delta = int(args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Invalid arguments. Both must be integers.")
        return

    db = context.bot_data["db_session"]()
    try:
        user = db.query(User).filter(User.telegram_id == target_id).first()
        if not user:
            await update.message.reply_text(f"❌ User {target_id} not found.")
            return

        new_total = add_points(db, user, delta, reason="admin_command")
        db.commit()

        sign = "+" if delta >= 0 else ""
        await update.message.reply_text(
            f"✅ Points updated for {user.display_name}\n"
            f"   Change: <b>{sign}{delta:,}</b>\n"
            f"   New total: <b>{format_points(new_total)}</b>",
            parse_mode="HTML",
        )

    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# /resetstreak <telegram_id>
# ─────────────────────────────────────────────────────────────
@admin_only
async def resetstreak_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset a user's streak to 0."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: <code>/resetstreak &lt;telegram_id&gt;</code>",
            parse_mode="HTML",
        )
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Invalid telegram_id.")
        return

    db = context.bot_data["db_session"]()
    try:
        user = db.query(User).filter(User.telegram_id == target_id).first()
        if not user:
            await update.message.reply_text(f"❌ User {target_id} not found.")
            return

        old_streak = user.streak
        user.streak = 0
        db.commit()

        await update.message.reply_text(
            f"✅ Streak reset for {user.display_name}\n"
            f"   Old streak: <b>{old_streak}</b>\n"
            f"   New streak: <b>0</b>",
            parse_mode="HTML",
        )

    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# /userinfo <telegram_id>  — detailed user lookup
# ─────────────────────────────────────────────────────────────
@admin_only
async def userinfo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Look up detailed info about a specific user."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: <code>/userinfo &lt;telegram_id&gt;</code>",
            parse_mode="HTML",
        )
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Invalid telegram_id.")
        return

    db = context.bot_data["db_session"]()
    try:
        user = db.query(User).filter(User.telegram_id == target_id).first()
        if not user:
            await update.message.reply_text(f"❌ User {target_id} not found.")
            return

        text = (
            f"🔍 <b>User Info</b>\n"
            f"{'─' * 28}\n"
            f"Telegram ID:  <code>{user.telegram_id}</code>\n"
            f"Username:     {user.display_name}\n"
            f"Game ID:      {user.game_id or 'Not set'}\n"
            f"Registered:   {user.register_date:%Y-%m-%d}\n"
            f"Last checkin: {user.last_checkin or 'Never'}\n"
            f"Streak:       {user.streak}\n"
            f"Total:        {user.total_checkin}\n"
            f"Points:       {format_points(user.points)}\n"
            f"Referrals:    {user.referral_count}"
        )
        await update.message.reply_text(text, parse_mode="HTML")

    finally:
        db.close()
