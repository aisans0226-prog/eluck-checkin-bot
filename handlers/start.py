# ============================================================
# handlers/start.py — /start command handler
# Handles both plain /start and referral links (?start=refXXXX)
# ============================================================

import logging

from telegram import Update
from telegram.ext import ContextTypes

from database import init_db
from services.checkin_service import get_or_create_user
from services.referral_service import process_referral
from utils.keyboard import main_menu_keyboard
from utils.helpers import rate_limited
import config

logger = logging.getLogger(__name__)


@rate_limited
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start [ref<telegram_id>]

    Flow:
    1. Get or create user in DB
    2. If payload starts with 'ref', process referral link
    3. Send welcome message with main menu keyboard
    """
    tg_user = update.effective_user
    if not tg_user:
        return

    db: object = context.bot_data["db_session"]()

    try:
        # ── Upsert user ───────────────────────────────────────
        user = get_or_create_user(
            db,
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
        )

        # ── Handle referral payload ───────────────────────────
        referral_text = ""
        if context.args:
            payload = context.args[0]
            if payload.startswith("ref"):
                try:
                    referrer_id = int(payload[3:])
                    referred = process_referral(db, referrer_id, user)
                    if referred:
                        referral_text = (
                            f"\n\n🎁 <b>Referral bonus!</b> You were invited by a friend.\n"
                            f"They earned <b>+{config.REFERRAL_REWARD} points</b>!"
                        )
                        # Notify the referrer
                        try:
                            await context.bot.send_message(
                                chat_id=referrer_id,
                                text=(
                                    f"🎉 <b>New Referral!</b>\n\n"
                                    f"<b>{tg_user.first_name}</b> joined using your referral link!\n"
                                    f"💰 You earned <b>+{config.REFERRAL_REWARD} points</b>."
                                ),
                                parse_mode="HTML",
                            )
                        except Exception:
                            pass  # referrer may have blocked the bot

                except (ValueError, TypeError):
                    logger.warning("Invalid referral payload: %s", payload)

        db.commit()

        # ── Send welcome message ──────────────────────────────
        welcome_text = config.MSG_WELCOME + referral_text

        await update.message.reply_text(
            text=welcome_text,
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )

    except Exception as exc:
        db.rollback()
        logger.error("start_handler error: %s", exc, exc_info=True)
        await update.message.reply_text("⚠️ An error occurred. Please try again.")
    finally:
        db.close()
