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
    broadcast_cancel,
    addpoints_handler,
    resetstreak_handler,
    userinfo_handler,
    BROADCAST_TEXT,
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
    Runs at 18:00 UTC every day.
    Sends a nudge to users who haven't checked in yet today.
    """
    db = app.bot_data["db_session"]()
    try:
        today = today_mexico()
        # Find users who checked in yesterday but NOT today (active streamers at risk)
        yesterday = today - timedelta(days=1)
        at_risk = (
            db.query(User)
            .filter(
                User.last_checkin == yesterday,
                User.streak >= 3,
            )
            .all()
        )
        count = 0
        for user in at_risk:
            try:
                await app.bot.send_message(
                    chat_id=user.telegram_id,
                    text=(
                        f"⏰ <b>Don't break your streak!</b>\n\n"
                        f"🔥 You have a <b>{user.streak}-day streak</b>!\n"
                        f"Check in today to keep it alive!"
                    ),
                    parse_mode="HTML",
                )
                count += 1
            except Exception:
                pass
        logger.info("[Scheduler] Streak reminders sent to %d users.", count)
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
            BROADCAST_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)
            ],
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
    scheduler = AsyncIOScheduler(timezone="America/Mexico_City")

    # Daily reset at midnight
    scheduler.add_job(
        lambda: asyncio.ensure_future(job_reset_daily_stats(app)),
        trigger="cron",
        hour=0,
        minute=0,
        id="daily_reset",
    )

    # Streak reminder at 18:00
    scheduler.add_job(
        lambda: asyncio.ensure_future(job_streak_reminder(app)),
        trigger="cron",
        hour=18,
        minute=0,
        id="streak_reminder",
    )

    # Database backup at 03:00
    scheduler.add_job(
        lambda: asyncio.ensure_future(job_backup_db(app)),
        trigger="cron",
        hour=3,
        minute=0,
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
