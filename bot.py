# ============================================================
# bot.py — Main entry point
#
# Responsibilities:
#   1. Initialise logging
#   2. Init database (create tables if needed)
#   3. Register all handlers with ApplicationBuilder
#   4. Set up APScheduler for daily jobs
#   5. Start polling or webhook based on config
# ============================================================

import logging
import sys
import asyncio
import warnings
from datetime import timedelta

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from database import init_db
from utils.helpers import today_mexico
from utils.i18n import t
from models.user import User

# ── Handlers ─────────────────────────────────────────────────
from handlers.start import start_handler
from handlers.checkin import (
    checkin_entry,
    receive_game_id,
    leaderboard_handler,
    WAITING_GAME_ID,
)
from handlers.profile import profile_handler, referral_handler
from handlers.menu import menu_callback_handler
from admin.admin_commands import (
    stats_handler,
    export_handler,
    broadcast_start,
    broadcast_send,
    broadcast_confirm,
    broadcast_cancel,
    addpoints_handler,
    resetstreak_handler,
    userinfo_handler,
    ban_handler,
    unban_handler,
    deleteuser_handler,
    BROADCAST_TEXT,
    BROADCAST_CONFIRM,
)

# ─────────────────────────────────────────────────────────────
# Logging setup
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/bot.log", encoding="utf-8"),
    ],
)
# Silence overly verbose libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Suppress PTB per_message warning — we use per_chat=True intentionally
warnings.filterwarnings("ignore", message=".*per_message.*", category=UserWarning)


# ─────────────────────────────────────────────────────────────
# Scheduled Jobs
# ─────────────────────────────────────────────────────────────
async def job_reset_daily_stats(app: Application) -> None:
    """
    Runs at midnight UTC.
    Currently just a hook — add any per-day reset logic here.
    """
    logger.info("[Scheduler] Daily reset job triggered.")


async def job_streak_reminder(app: Application) -> None:
    """
    Runs at STREAK_REMINDER_HOUR every day.
    Sends a nudge to users who haven't checked in yet today.
    Automatically marks users as is_blocked when Forbidden error occurs.
    """
    from telegram.error import Forbidden as TGForbidden

    db = app.bot_data["db_session"]()
    try:
        today = today_mexico()
        yesterday = today - timedelta(days=1)
        at_risk = (
            db.query(User)
            .filter(
                User.last_checkin == yesterday,
                User.streak >= config.STREAK_REMINDER_MIN,
                User.is_blocked == False,  # noqa: E712
                User.is_banned == False,   # noqa: E712
            )
            .all()
        )
        count, blocked_now = 0, 0
        for user in at_risk:
            try:
                await app.bot.send_message(
                    chat_id=user.telegram_id,
                    text=t(
                        "streak_reminder",
                        user.language or "en",
                        streak=user.streak,
                    ),
                    parse_mode="HTML",
                )
                count += 1
            except TGForbidden:
                user.is_blocked = True
                blocked_now += 1
            except Exception:
                pass
        db.commit()
        logger.info("[Scheduler] Streak reminders sent: %d ok, %d newly blocked.", count, blocked_now)
    finally:
        db.close()


async def job_daily_digest(app: Application) -> None:
    """
    Runs at DAILY_DIGEST_HOUR every day.
    Sends a daily stats summary to all admin IDs.
    """
    if not config.ADMIN_IDS:
        return

    db = app.bot_data["db_session"]()
    try:
        from sqlalchemy import func as sqlfunc
        from models.checkin import CheckinLog
        from datetime import timedelta

        today       = today_mexico()
        yesterday   = today - timedelta(days=1)
        week_ago    = today - timedelta(days=7)

        checkins_today     = db.query(CheckinLog).filter(CheckinLog.checkin_date == today).count()
        checkins_yesterday = db.query(CheckinLog).filter(CheckinLog.checkin_date == yesterday).count()
        total_users        = db.query(User).count()
        active_7d          = db.query(User).filter(User.last_checkin >= week_ago).count()
        new_today          = db.query(User).filter(
            User.register_date >= today_mexico()
        ).count()

        delta = checkins_today - checkins_yesterday
        delta_str = f"+{delta}" if delta >= 0 else str(delta)

        text = (
            f"<b>Daily Digest — {today.isoformat()}</b>\n"
            f"{'─' * 28}\n\n"
            f"Check-ins today:   <b>{checkins_today:,}</b> ({delta_str} vs yesterday)\n"
            f"Active 7d:         <b>{active_7d:,}</b>\n"
            f"New users today:   <b>{new_today:,}</b>\n"
            f"Total users:       <b>{total_users:,}</b>"
        )

        for admin_id in config.ADMIN_IDS:
            try:
                await app.bot.send_message(admin_id, text=text, parse_mode="HTML")
            except Exception:
                pass

        logger.info("[Scheduler] Daily digest sent to %d admins.", len(config.ADMIN_IDS))
    finally:
        db.close()


async def job_churn_alert(app: Application) -> None:
    """
    Runs at CHURN_ALERT_HOUR every day.
    Finds high-churn-risk users and notifies admins.
    """
    if not config.ADMIN_IDS:
        return

    db = app.bot_data["db_session"]()
    try:
        from datetime import timedelta
        from services.ai_analytics_service import predict_churn_risk

        cutoff = today_mexico() - timedelta(days=config.CHURN_ALERT_DAYS_INACTIVE)
        at_risk_users = (
            db.query(User)
            .filter(
                User.last_checkin.isnot(None),
                User.last_checkin < cutoff,
                User.is_banned == False,   # noqa: E712
                User.is_blocked == False,  # noqa: E712
            )
            .order_by(User.last_checkin.asc())
            .limit(50)
            .all()
        )

        high_risk = []
        for user in at_risk_users:
            days_since = (today_mexico() - user.last_checkin).days if user.last_checkin else 999
            result = predict_churn_risk({
                "streak":        user.streak,
                "total_checkin": user.total_checkin,
                "days_since_last": days_since,
                "task_completion": 0.0,
                "has_referrals": user.referral_count > 0,
            })
            if result["risk"] == "high":
                high_risk.append((user, days_since, result))

        if not high_risk:
            return

        lines = [f"<b>Churn Alert — {len(high_risk)} high-risk users</b>\n"]
        for user, days, r in high_risk[:20]:
            lines.append(
                f"  {user.display_name} (streak={user.streak}, inactive {days}d) — {r['reason']}"
            )
        if len(high_risk) > 20:
            lines.append(f"  ... and {len(high_risk) - 20} more")

        text = "\n".join(lines)
        for admin_id in config.ADMIN_IDS:
            try:
                await app.bot.send_message(admin_id, text=text, parse_mode="HTML")
            except Exception:
                pass

        logger.info("[Scheduler] Churn alert sent: %d high-risk users.", len(high_risk))
    finally:
        db.close()


async def job_backup_db(_app: Application) -> None:
    """
    Runs at 03:00 UTC — simple SQLite file copy as backup.
    For PostgreSQL, replace with pg_dump call.
    """
    import shutil, os
    src = "data/database.db"
    dst = f"data/backup_{today_mexico().isoformat()}.db"
    if os.path.exists(src):
        shutil.copy2(src, dst)
        logger.info("[Scheduler] Database backed up to %s", dst)


# ─────────────────────────────────────────────────────────────
# Application factory
# ─────────────────────────────────────────────────────────────
def build_application() -> Application:
    """Build and configure the Telegram Application."""
    # ── Init database ─────────────────────────────────────────
    engine, SessionLocal = init_db(config.DATABASE_URL)

    # ── post_init: runs inside the running event loop ─────────
    async def post_init(app: Application) -> None:
        app.bot_data["db_session"] = SessionLocal
        app.bot_data["referral_reward"] = config.REFERRAL_REWARD
        # Start APScheduler here — event loop is already running
        scheduler = setup_scheduler(app)
        scheduler.start()
        app.bot_data["scheduler"] = scheduler
        logger.info("Scheduler started with %d jobs.", len(scheduler.get_jobs()))

    async def post_shutdown(app: Application) -> None:
        scheduler = app.bot_data.get("scheduler")
        if scheduler and scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped.")

    # ── Build app ─────────────────────────────────────────────
    app = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # ── Conversation: daily check-in (game-id registration) ───
    # per_message=False — entry via command only, callback goes through menu_callback_handler
    checkin_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("checkin", checkin_entry),
            CallbackQueryHandler(checkin_entry, pattern="^menu:checkin$"),
        ],
        states={
            WAITING_GAME_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_game_id)
            ],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_message=False,
        per_chat=True,
    )

    # ── Conversation: admin broadcast ─────────────────────────
    broadcast_conversation = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start)],
        states={
            BROADCAST_TEXT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)],
            BROADCAST_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_confirm)],
        },
        fallbacks=[CommandHandler("cancel", broadcast_cancel)],
        per_message=False,
        per_chat=True,
    )

    # ── Register handlers ─────────────────────────────────────

    # Core commands
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("leaderboard", leaderboard_handler))
    app.add_handler(CommandHandler("profile", profile_handler))
    app.add_handler(CommandHandler("referral", referral_handler))

    # Conversations (must come before loose handlers)
    app.add_handler(checkin_conversation)
    app.add_handler(broadcast_conversation)

    # Admin commands
    app.add_handler(CommandHandler("stats", stats_handler))
    app.add_handler(CommandHandler("export", export_handler))
    app.add_handler(CommandHandler("addpoints", addpoints_handler))
    app.add_handler(CommandHandler("resetstreak", resetstreak_handler))
    app.add_handler(CommandHandler("userinfo", userinfo_handler))
    app.add_handler(CommandHandler("ban", ban_handler))
    app.add_handler(CommandHandler("unban", unban_handler))
    app.add_handler(CommandHandler("deleteuser", deleteuser_handler))

    # Inline keyboard callback dispatcher (catch-all)
    app.add_handler(CallbackQueryHandler(menu_callback_handler))

    # Error handler
    async def error_handler(update: object, context) -> None:
        logger.error("Unhandled exception: %s", context.error, exc_info=True)
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ An unexpected error occurred. Please try again later."
            )

    app.add_error_handler(error_handler)

    return app


# ─────────────────────────────────────────────────────────────
# Scheduler setup
# ─────────────────────────────────────────────────────────────
def setup_scheduler(app: Application) -> AsyncIOScheduler:
    """Configure APScheduler jobs and attach them to the app."""
    scheduler = AsyncIOScheduler(timezone=config.BOT_TIMEZONE)

    # Daily reset at midnight
    scheduler.add_job(
        lambda: asyncio.ensure_future(job_reset_daily_stats(app)),
        trigger="cron", hour=0, minute=0,
        id="daily_reset",
    )

    # Streak reminder
    scheduler.add_job(
        lambda: asyncio.ensure_future(job_streak_reminder(app)),
        trigger="cron", hour=config.STREAK_REMINDER_HOUR, minute=0,
        id="streak_reminder",
    )

    # Daily digest to admins
    scheduler.add_job(
        lambda: asyncio.ensure_future(job_daily_digest(app)),
        trigger="cron", hour=config.DAILY_DIGEST_HOUR, minute=0,
        id="daily_digest",
    )

    # Churn risk alert to admins
    scheduler.add_job(
        lambda: asyncio.ensure_future(job_churn_alert(app)),
        trigger="cron", hour=config.CHURN_ALERT_HOUR, minute=0,
        id="churn_alert",
    )

    # Database backup at 03:00
    scheduler.add_job(
        lambda: asyncio.ensure_future(job_backup_db(app)),
        trigger="cron", hour=3, minute=0,
        id="db_backup",
    )

    return scheduler


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
def main() -> None:
    logger.info("Starting Community Check-in Bot…")
    logger.info("Admin IDs: %s", config.ADMIN_IDS)
    logger.info("Database: %s", config.DATABASE_URL)

    app = build_application()

    if config.WEBHOOK_URL:
        # ── Webhook mode (production) ─────────────────────────
        logger.info("Running in WEBHOOK mode: %s", config.WEBHOOK_URL)
        app.run_webhook(
            listen="0.0.0.0",
            port=config.WEBHOOK_PORT,
            url_path=config.BOT_TOKEN,
            webhook_url=f"{config.WEBHOOK_URL}/{config.BOT_TOKEN}",
            drop_pending_updates=True,
        )
    else:
        # ── Polling mode (development / small VPS) ────────────
        logger.info("Running in POLLING mode.")
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )


if __name__ == "__main__":
    main()
