# ============================================================
# handlers/menu.py — Central callback query dispatcher
# Handles all menu:* and task:* callbacks
# ============================================================

import logging

from telegram import Update
from telegram.ext import ContextTypes

import config
from models.user import User
from services.reward_service import get_user_task_status, complete_task
from utils.keyboard import (
    main_menu_keyboard,
    tasks_keyboard,
    task_detail_keyboard,
    back_to_menu_keyboard,
)
from utils.helpers import safe_edit_or_reply, rate_limited
from utils.i18n import t

logger = logging.getLogger(__name__)


def _get_lang(db, telegram_id: int) -> str:
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    return user.language if user else "en"


@rate_limited
async def menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Dispatch inline keyboard callbacks.

    Patterns handled:
      menu:home
      menu:profile
      menu:checkin
      menu:leaderboard
      menu:tasks
      menu:referral
      task:view:<task_id>
      task:complete:<task_id>
    """
    query = update.callback_query
    if not query:
        return

    await query.answer()

    data: str = query.data or ""

    db = context.bot_data["db_session"]()
    try:
        lang = _get_lang(db, update.effective_user.id)
    finally:
        db.close()

    # ── Navigation dispatch ───────────────────────────────────
    if data == "menu:home":
        await query.edit_message_text(
            text=t("welcome", lang),
            reply_markup=main_menu_keyboard(lang),
            parse_mode="HTML",
        )

    elif data == "menu:profile":
        from handlers.profile import profile_handler
        await profile_handler(update, context)

    elif data == "menu:checkin":
        from handlers.checkin import checkin_entry
        await checkin_entry(update, context)

    elif data == "menu:leaderboard":
        from handlers.checkin import leaderboard_handler
        await leaderboard_handler(update, context)

    elif data == "menu:tasks":
        await _show_tasks(update, context, lang)

    elif data == "menu:referral":
        from handlers.profile import referral_handler
        await referral_handler(update, context)

    elif data.startswith("task:view:"):
        task_id = data.split(":", 2)[2]
        await _show_task_detail(update, context, task_id, lang)

    elif data.startswith("task:complete:"):
        task_id = data.split(":", 2)[2]
        await _complete_task(update, context, task_id, lang)

    else:
        logger.warning("Unhandled callback: %s", data)


# ─────────────────────────────────────────────────────────────
# Task list
# ─────────────────────────────────────────────────────────────
async def _show_tasks(
    update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str
) -> None:
    tg_user = update.effective_user
    db = context.bot_data["db_session"]()
    try:
        user = db.query(User).filter(User.telegram_id == tg_user.id).first()
        if not user:
            await safe_edit_or_reply(update, t("start_first", lang))
            return

        completed_ids = get_user_task_status(db, user)
        total_tasks = len(config.TASKS)
        done = len(completed_ids)

        text = (
            f"{t('tasks_header', lang, done=done, total=total_tasks)}\n"
            f"{'─' * 28}\n"
            f"{t('tasks_subtext', lang)}\n"
        )

        await safe_edit_or_reply(
            update,
            text,
            reply_markup=tasks_keyboard(config.TASKS, completed_ids, lang),
        )
    finally:
        db.close()


async def _show_task_detail(
    update: Update, context: ContextTypes.DEFAULT_TYPE, task_id: str, lang: str
) -> None:
    task_def = next((t_ for t_ in config.TASKS if t_["id"] == task_id), None)
    if not task_def:
        await safe_edit_or_reply(
            update, t("task_not_found", lang), reply_markup=back_to_menu_keyboard(lang)
        )
        return

    tg_user = update.effective_user
    db = context.bot_data["db_session"]()
    try:
        user = db.query(User).filter(User.telegram_id == tg_user.id).first()
        completed_ids = get_user_task_status(db, user) if user else []
        is_done = task_def["id"] in completed_ids

        status_badge = (
            t("task_completed_badge", lang)
            if is_done
            else t("task_not_completed_badge", lang)
        )

        text = (
            f"🎯 <b>{task_def['name']}</b>\n"
            f"{'─' * 28}\n\n"
            f"{task_def['description']}\n\n"
            f"{t('task_reward_line', lang, reward=task_def['reward'])}\n"
            f"{t('task_status_line', lang, status=status_badge)}"
        )

        await safe_edit_or_reply(
            update,
            text,
            reply_markup=task_detail_keyboard(task_def, is_done, lang),
        )
    finally:
        db.close()


async def _complete_task(
    update: Update, context: ContextTypes.DEFAULT_TYPE, task_id: str, lang: str
) -> None:
    tg_user = update.effective_user
    db = context.bot_data["db_session"]()
    try:
        user = db.query(User).filter(User.telegram_id == tg_user.id).first()
        if not user:
            await safe_edit_or_reply(update, t("start_first", lang))
            return

        success, pts = complete_task(db, user, task_id)
        db.commit()

        task_def = next((t_ for t_ in config.TASKS if t_["id"] == task_id), {})

        if success:
            text = t(
                "task_done_msg",
                lang,
                name=task_def.get("name", task_id),
                pts=pts,
                total=user.points,
            )
        else:
            completed_ids = get_user_task_status(db, user)
            if task_id in completed_ids:
                text = t("task_already_done", lang)
            else:
                text = t(
                    "task_requirements_not_met",
                    lang,
                    desc=task_def.get("description", ""),
                )

        await safe_edit_or_reply(update, text, reply_markup=back_to_menu_keyboard(lang))

    except Exception as exc:
        db.rollback()
        logger.error("_complete_task error: %s", exc, exc_info=True)
    finally:
        db.close()
