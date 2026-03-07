# ============================================================
# handlers/start.py — /start command handler
# Handles both plain /start and referral links (?start=refXXXX)
# ============================================================

import logging

from telegram import Update
from telegram.ext import ContextTypes

from services.checkin_service import get_or_create_user
from services.referral_service import process_referral
from utils.keyboard import main_menu_keyboard
from utils.helpers import rate_limited
from utils.i18n import detect_lang, t
import config

logger = logging.getLogger(__name__)


@rate_limited
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start [ref<telegram_id>]

    Flow:
    1. Get or create user in DB
    2. Auto-detect language from tg_user.language_code → save to user.language
    3. If payload starts with 'ref', process referral link
    4. Send welcome message with main menu keyboard
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

        # ── Auto-detect & persist language ───────────────────
        lang = detect_lang(tg_user.language_code)
        if user.language != lang:
            user.language = lang

        # ── Handle referral payload ───────────────────────────
        referral_text = ""
        if context.args:
            payload = context.args[0]
            if payload.startswith("ref"):
                try:
                    referrer_id = int(payload[3:])
                    referred = process_referral(db, referrer_id, user)
                    if referred:
                        referral_text = t(
                            "referral_bonus", lang, points=config.REFERRAL_REWARD
                        )
                        # Notify the referrer in their own language
                        try:
                            from models.user import User as UserModel
                            referrer = (
                                db.query(UserModel)
                                .filter(UserModel.telegram_id == referrer_id)
                                .first()
                            )
                            referrer_lang = referrer.language if referrer else "en"
                            await context.bot.send_message(
                                chat_id=referrer_id,
                                text=t(
                                    "new_referral_notify",
                                    referrer_lang,
                                    name=tg_user.first_name,
                                    points=config.REFERRAL_REWARD,
                                ),
                                parse_mode="HTML",
                            )
                        except Exception:
                            pass  # referrer may have blocked the bot

                except (ValueError, TypeError):
                    logger.warning("Invalid referral payload: %s", payload)

        db.commit()

        # ── Send welcome message ──────────────────────────────
        welcome_text = t("welcome", lang) + referral_text

        await update.message.reply_text(
            text=welcome_text,
            reply_markup=main_menu_keyboard(lang),
            parse_mode="HTML",
        )

    except Exception as exc:
        db.rollback()
        logger.error("start_handler error: %s", exc, exc_info=True)
        await update.message.reply_text(t("error_generic", "en"))
    finally:
        db.close()
