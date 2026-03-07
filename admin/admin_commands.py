# ============================================================
# admin/admin_commands.py — Admin-only bot commands
#
# Commands available:
#   /stats           — Bot statistics overview
#   /export          — Export users CSV via pandas
#   /broadcast       — Send message to all users (with preview+confirm)
#   /addpoints       — Manually add / subtract points
#   /resetstreak     — Reset a user's streak
#   /userinfo        — Detailed user lookup
#   /ban             — Ban a user (blocks check-in + checkin)
#   /unban           — Unban a user
#   /deleteuser      — Permanently delete a user record (GDPR)
# ============================================================

import asyncio
import io
import logging
from datetime import date, datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import func
from telegram import Update
from telegram.error import Forbidden, BadRequest
from telegram.ext import ContextTypes, ConversationHandler

from models.user import User
from models.checkin import CheckinLog
from services.checkin_service import get_checkins_today
from services.reward_service import add_points
from services.event_service import (
    log_event, EVT_ADMIN_BAN, EVT_ADMIN_UNBAN, EVT_ADMIN_POINTS,
    EVT_ADMIN_STREAK, EVT_ADMIN_BROADCAST, EVT_ADMIN_DELETE,
)
from utils.helpers import admin_only, format_points, today_mexico

logger = logging.getLogger(__name__)

# ConversationHandler states for /broadcast
BROADCAST_TEXT    = 10
BROADCAST_CONFIRM = 11


# ─────────────────────────────────────────────────────────────
# /stats
# ─────────────────────────────────────────────────────────────
@admin_only
async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return bot statistics to the admin."""
    db = context.bot_data["db_session"]()
    try:
        total_users        = db.query(User).count()
        users_with_game_id = db.query(User).filter(User.game_id.isnot(None)).count()
        banned_users       = db.query(User).filter(User.is_banned == True).count()  # noqa: E712
        blocked_users      = db.query(User).filter(User.is_blocked == True).count()  # noqa: E712
        checkins_today     = get_checkins_today(db)

        cutoff_7d  = today_mexico() - timedelta(days=7)
        cutoff_30d = today_mexico() - timedelta(days=30)
        active_7d  = db.query(User).filter(User.last_checkin >= cutoff_7d).count()
        active_30d = db.query(User).filter(User.last_checkin >= cutoff_30d).count()

        # SQL-side average — does not load all rows into memory
        avg_streak = db.query(func.avg(User.streak)).scalar() or 0.0
        max_streak = db.query(func.max(User.streak)).scalar() or 0
        total_pts  = db.query(func.sum(User.points)).scalar() or 0

        # New users today
        today_start = datetime.combine(today_mexico(), datetime.min.time()).replace(
            tzinfo=timezone.utc
        )
        new_today = db.query(User).filter(User.register_date >= today_start).count()

        text = (
            f"<b>BOT STATISTICS</b>\n"
            f"{'─' * 28}\n\n"
            f"<b>Users</b>\n"
            f"  Total:             <b>{total_users:,}</b>\n"
            f"  With Game ID:      <b>{users_with_game_id:,}</b>\n"
            f"  New today:         <b>{new_today:,}</b>\n"
            f"  Active (7d):       <b>{active_7d:,}</b>\n"
            f"  Active (30d):      <b>{active_30d:,}</b>\n"
            f"  Banned:            <b>{banned_users:,}</b>\n"
            f"  Blocked bot:       <b>{blocked_users:,}</b>\n\n"
            f"<b>Check-ins</b>\n"
            f"  Today:             <b>{checkins_today:,}</b>\n"
            f"  Avg streak:        <b>{avg_streak:.1f} days</b>\n"
            f"  Max streak:        <b>{max_streak} days</b>\n\n"
            f"<b>Economy</b>\n"
            f"  Total pts issued:  <b>{format_points(total_pts)}</b>\n\n"
            f"<i>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>"
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
        # Use yield_per to avoid loading entire table into memory
        users = db.query(User).yield_per(500).all()
        if not users:
            await update.message.reply_text("No users to export.")
            return

        data = [
            {
                "telegram_id":   u.telegram_id,
                "username":      u.username or "",
                "first_name":    u.first_name or "",
                "game_id":       u.game_id or "",
                "language":      u.language,
                "register_date": u.register_date,
                "last_checkin":  u.last_checkin,
                "streak":        u.streak,
                "total_checkin": u.total_checkin,
                "points":        u.points,
                "referrer_id":   u.referrer_id or "",
                "is_banned":     u.is_banned,
                "is_blocked":    u.is_blocked,
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
            caption=f"Users export — {len(data):,} records",
        )

    except Exception as exc:
        logger.error("export_handler error: %s", exc, exc_info=True)
        await update.message.reply_text("Export failed.")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# /broadcast — Three-step conversation with preview + confirm
# ─────────────────────────────────────────────────────────────
@admin_only
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start broadcast conversation — ask for message text."""
    await update.message.reply_text(
        "<b>Broadcast</b>\n\n"
        "Send the message you want to broadcast to all users.\n"
        "Supports HTML formatting.\n\n"
        "Send /cancel to abort.",
        parse_mode="HTML",
    )
    return BROADCAST_TEXT


async def broadcast_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive broadcast text, show preview, ask for confirmation."""
    message_text = update.message.text or update.message.caption or ""
    if not message_text:
        await update.message.reply_text("Empty message. Broadcast cancelled.")
        return ConversationHandler.END

    # Store the message for the confirm step
    context.user_data["broadcast_text"] = message_text

    db = context.bot_data["db_session"]()
    try:
        # Count reachable users (not blocked, not banned)
        reachable = db.query(User).filter(
            User.is_blocked == False,  # noqa: E712
            User.is_banned == False,   # noqa: E712
        ).count()
    finally:
        db.close()

    preview_text = (
        f"<b>Broadcast Preview</b>\n"
        f"{'─' * 28}\n\n"
        f"<b>Message:</b>\n"
        f"<blockquote>{message_text}</blockquote>\n\n"
        f"Will be sent to <b>{reachable:,}</b> users.\n\n"
        f"Reply <b>yes</b> to confirm, anything else to cancel."
    )
    await update.message.reply_text(preview_text, parse_mode="HTML")
    return BROADCAST_CONFIRM


async def broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirm and execute broadcast with rate-limit friendly sending."""
    answer = (update.message.text or "").strip().lower()
    if answer != "yes":
        await update.message.reply_text("Broadcast cancelled.")
        context.user_data.pop("broadcast_text", None)
        return ConversationHandler.END

    message_text = context.user_data.pop("broadcast_text", "")
    if not message_text:
        await update.message.reply_text("No message stored. Broadcast cancelled.")
        return ConversationHandler.END

    db = context.bot_data["db_session"]()
    try:
        users = db.query(User).filter(
            User.is_blocked == False,  # noqa: E712
            User.is_banned == False,   # noqa: E712
        ).all()
        total = len(users)

        progress_msg = await update.message.reply_text(
            f"Sending to <b>{total:,}</b> users…",
            parse_mode="HTML",
        )

        sent, failed, blocked_now = 0, 0, 0

        for i, user in enumerate(users):
            try:
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text=f"<b>Announcement</b>\n\n{message_text}",
                    parse_mode="HTML",
                )
                sent += 1
            except Forbidden:
                # User blocked the bot — mark is_blocked in DB
                failed += 1
                blocked_now += 1
                try:
                    u = db.query(User).filter(User.telegram_id == user.telegram_id).first()
                    if u:
                        u.is_blocked = True
                except Exception:
                    pass
            except Exception:
                failed += 1

            # Telegram rate limit: max ~30 messages/sec — we use 25 to be safe
            await asyncio.sleep(0.04)

            # Update progress every 100 messages
            if (i + 1) % 100 == 0:
                try:
                    await progress_msg.edit_text(
                        f"Progress: <b>{i + 1:,}/{total:,}</b>…",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass

        db.commit()

        log_event(db, update.effective_user.id, EVT_ADMIN_BROADCAST, {
            "sent": sent, "failed": failed, "blocked_now": blocked_now,
        })

        await update.message.reply_text(
            f"Broadcast complete!\n"
            f"  Sent:       <b>{sent:,}</b>\n"
            f"  Failed:     <b>{failed:,}</b>\n"
            f"  Newly blocked: <b>{blocked_now:,}</b>",
            parse_mode="HTML",
        )

    finally:
        db.close()

    return ConversationHandler.END


async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("broadcast_text", None)
    await update.message.reply_text("Broadcast cancelled.")
    return ConversationHandler.END


# Keep old name for backward compatibility in bot.py import
broadcast_send = broadcast_preview


# ─────────────────────────────────────────────────────────────
# /addpoints <telegram_id> <points>
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
        await update.message.reply_text("Invalid arguments. Both must be integers.")
        return

    db = context.bot_data["db_session"]()
    try:
        user = db.query(User).filter(User.telegram_id == target_id).first()
        if not user:
            await update.message.reply_text(f"User {target_id} not found.")
            return

        new_total = add_points(db, user, delta, reason="admin_command",
                               admin_id=update.effective_user.id)
        db.commit()

        sign = "+" if delta >= 0 else ""
        await update.message.reply_text(
            f"Points updated for {user.display_name}\n"
            f"  Change: <b>{sign}{delta:,}</b>\n"
            f"  New total: <b>{format_points(new_total)}</b>",
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
        await update.message.reply_text("Invalid telegram_id.")
        return

    db = context.bot_data["db_session"]()
    try:
        user = db.query(User).filter(User.telegram_id == target_id).first()
        if not user:
            await update.message.reply_text(f"User {target_id} not found.")
            return

        old_streak = user.streak
        user.streak = 0
        log_event(db, target_id, EVT_ADMIN_STREAK, {
            "old_streak": old_streak, "admin_id": update.effective_user.id,
        })
        db.commit()

        await update.message.reply_text(
            f"Streak reset for {user.display_name}\n"
            f"  Old streak: <b>{old_streak}</b> → <b>0</b>",
            parse_mode="HTML",
        )

    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# /userinfo <telegram_id>
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
        await update.message.reply_text("Invalid telegram_id.")
        return

    db = context.bot_data["db_session"]()
    try:
        user = db.query(User).filter(User.telegram_id == target_id).first()
        if not user:
            await update.message.reply_text(f"User {target_id} not found.")
            return

        flags = []
        if user.is_banned:   flags.append("BANNED")
        if user.is_blocked:  flags.append("BLOCKED BOT")
        flag_str = " | ".join(flags) if flags else "Active"

        text = (
            f"<b>User Info</b>\n"
            f"{'─' * 28}\n"
            f"Telegram ID:  <code>{user.telegram_id}</code>\n"
            f"Username:     {user.display_name}\n"
            f"Game ID:      {user.game_id or 'Not set'}\n"
            f"Language:     {user.language}\n"
            f"Registered:   {user.register_date:%Y-%m-%d}\n"
            f"Last checkin: {user.last_checkin or 'Never'}\n"
            f"Streak:       {user.streak}\n"
            f"Total:        {user.total_checkin}\n"
            f"Points:       {format_points(user.points)}\n"
            f"Referrals:    {user.referral_count}\n"
            f"Status:       <b>{flag_str}</b>"
        )
        await update.message.reply_text(text, parse_mode="HTML")

    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# /ban <telegram_id> [reason]
# ─────────────────────────────────────────────────────────────
@admin_only
async def ban_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ban a user — blocks check-in and all bot interactions."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: <code>/ban &lt;telegram_id&gt; [reason]</code>",
            parse_mode="HTML",
        )
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Invalid telegram_id.")
        return

    reason = " ".join(args[1:]) if len(args) > 1 else "No reason given"

    db = context.bot_data["db_session"]()
    try:
        user = db.query(User).filter(User.telegram_id == target_id).first()
        if not user:
            await update.message.reply_text(f"User {target_id} not found.")
            return

        if user.is_banned:
            await update.message.reply_text(f"{user.display_name} is already banned.")
            return

        user.is_banned = True
        log_event(db, target_id, EVT_ADMIN_BAN, {
            "reason": reason, "admin_id": update.effective_user.id,
        })
        db.commit()

        await update.message.reply_text(
            f"Banned {user.display_name}\n"
            f"  Reason: {reason}",
            parse_mode="HTML",
        )

    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# /unban <telegram_id>
# ─────────────────────────────────────────────────────────────
@admin_only
async def unban_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unban a previously banned user."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: <code>/unban &lt;telegram_id&gt;</code>",
            parse_mode="HTML",
        )
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Invalid telegram_id.")
        return

    db = context.bot_data["db_session"]()
    try:
        user = db.query(User).filter(User.telegram_id == target_id).first()
        if not user:
            await update.message.reply_text(f"User {target_id} not found.")
            return

        if not user.is_banned:
            await update.message.reply_text(f"{user.display_name} is not banned.")
            return

        user.is_banned = False
        log_event(db, target_id, EVT_ADMIN_UNBAN, {"admin_id": update.effective_user.id})
        db.commit()

        await update.message.reply_text(f"Unbanned {user.display_name}.")

    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# /deleteuser <telegram_id>
# ─────────────────────────────────────────────────────────────
@admin_only
async def deleteuser_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Permanently delete a user and all their data.
    Intended for GDPR deletion requests.
    """
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: <code>/deleteuser &lt;telegram_id&gt;</code>\n"
            "<i>Warning: this is irreversible.</i>",
            parse_mode="HTML",
        )
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Invalid telegram_id.")
        return

    db = context.bot_data["db_session"]()
    try:
        user = db.query(User).filter(User.telegram_id == target_id).first()
        if not user:
            await update.message.reply_text(f"User {target_id} not found.")
            return

        display = user.display_name
        log_event(db, target_id, EVT_ADMIN_DELETE, {"admin_id": update.effective_user.id})
        db.flush()
        db.delete(user)
        db.commit()

        await update.message.reply_text(
            f"User {display} (<code>{target_id}</code>) and all their data permanently deleted.",
            parse_mode="HTML",
        )

    except Exception as exc:
        db.rollback()
        logger.error("deleteuser_handler error: %s", exc, exc_info=True)
        await update.message.reply_text("Delete failed. Check logs.")
    finally:
        db.close()
