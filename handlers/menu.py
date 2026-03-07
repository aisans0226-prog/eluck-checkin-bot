# ============================================================
# handlers/menu.py — Central callback query dispatcher
# Handles all menu:* and task:* callbacks
# ============================================================

import logging

from telegram import Update
from telegram.ext import ContextTypes

from models.user import User
from services.reward_service import get_user_task_status, complete_task, get_active_tasks
from services.event_service import (
    log_event,
    EVT_BTN_HOME, EVT_BTN_PROFILE, EVT_BTN_TASKS,
    EVT_BTN_REFERRAL, EVT_BTN_LEADERBOARD, EVT_BTN_LANGUAGE,
    EVT_BTN_TASK_VIEW, EVT_BTN_TASK_DONE,
    EVT_TASK_COMPLETED, EVT_TASK_FAILED, EVT_LANG_CHANGED,
)
from utils.keyboard import (
    main_menu_keyboard,
    tasks_keyboard,
    task_detail_keyboard,
    back_to_menu_keyboard,
    language_keyboard,
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
    tid = update.effective_user.id

    db = context.bot_data["db_session"]()
    try:
        lang = _get_lang(db, tid)

        # ── Navigation dispatch ───────────────────────────────
        if data == "menu:home":
            log_event(db, tid, EVT_BTN_HOME)
            await query.edit_message_text(
                text=t("welcome", lang),
                reply_markup=main_menu_keyboard(lang),
                parse_mode="HTML",
            )

        elif data == "menu:profile":
            log_event(db, tid, EVT_BTN_PROFILE)
            from handlers.profile import _profile_impl
            await _profile_impl(update, context)

        elif data == "menu:checkin":
            # checkin_entry logs EVT_BTN_CHECKIN itself
            from handlers.checkin import checkin_entry
            await checkin_entry(update, context)

        elif data == "menu:leaderboard":
            log_event(db, tid, EVT_BTN_LEADERBOARD)
            from handlers.checkin import _leaderboard_impl
            await _leaderboard_impl(update, context)

        elif data == "menu:tasks":
            log_event(db, tid, EVT_BTN_TASKS)
            await _show_tasks(update, context, lang)

        elif data == "menu:referral":
            log_event(db, tid, EVT_BTN_REFERRAL)
            from handlers.profile import _referral_impl
            await _referral_impl(update, context)

        elif data.startswith("task:view:"):
            task_id = data.split(":", 2)[2]
            log_event(db, tid, EVT_BTN_TASK_VIEW, {"task_id": task_id})
            await _show_task_detail(update, context, task_id, lang)

        elif data.startswith("task:complete:"):
            task_id = data.split(":", 2)[2]
            log_event(db, tid, EVT_BTN_TASK_DONE, {"task_id": task_id})
            await _complete_task(update, context, task_id, lang)

        elif data == "menu:language":
            log_event(db, tid, EVT_BTN_LANGUAGE)
            await safe_edit_or_reply(
                update,
                t("language_menu_header", lang),
                reply_markup=language_keyboard(lang),
            )

        elif data.startswith("lang:set:"):
            new_lang = data.split(":", 2)[2]
            await _set_language(update, context, new_lang)

        else:
            logger.warning("Unhandled callback: %s", data)

    finally:
        db.close()


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
        tasks_list = get_active_tasks(db)
        total_tasks = len(tasks_list)
        done = len(completed_ids)

        text = (
            f"{t('tasks_header', lang, done=done, total=total_tasks)}\n"
            f"{'─' * 28}\n"
            f"{t('tasks_subtext', lang)}\n"
        )

        await safe_edit_or_reply(
            update,
            text,
            reply_markup=tasks_keyboard(tasks_list, completed_ids, lang),
        )
    finally:
        db.close()


async def _show_task_detail(
    update: Update, context: ContextTypes.DEFAULT_TYPE, task_id: str, lang: str
) -> None:
    tg_user = update.effective_user
    db = context.bot_data["db_session"]()
    try:
        tasks_list = get_active_tasks(db)
        task_def = next((t_ for t_ in tasks_list if t_["id"] == task_id), None)
        if not task_def:
            await safe_edit_or_reply(
                update, t("task_not_found", lang), reply_markup=back_to_menu_keyboard(lang)
            )
            return

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

        tasks_list = get_active_tasks(db)
        task_def = next((t_ for t_ in tasks_list if t_["id"] == task_id), {})

        if success:
            log_event(db, tg_user.id, EVT_TASK_COMPLETED,
                      {"task_id": task_id, "pts": pts})
            text = t(
                "task_done_msg",
                lang,
                name=task_def.get("name", task_id),
                pts=pts,
                total=user.points,
            )
        else:
            log_event(db, tg_user.id, EVT_TASK_FAILED, {"task_id": task_id})
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


# ─────────────────────────────────────────────────────────────
# Language selection
# ─────────────────────────────────────────────────────────────
_VALID_LANGS = {"en", "pt", "zh", "es", "mx"}


async def _set_language(
    update: Update, context: ContextTypes.DEFAULT_TYPE, new_lang: str
) -> None:
    """Save the chosen language to the user row and refresh the main menu."""
    if new_lang not in _VALID_LANGS:
        return

    tg_user = update.effective_user
    db = context.bot_data["db_session"]()
    try:
        user = db.query(User).filter(User.telegram_id == tg_user.id).first()
        if not user:
            await safe_edit_or_reply(update, t("start_first", "en"))
            return

        user.language = new_lang
        log_event(db, tg_user.id, EVT_LANG_CHANGED, {"lang": new_lang})
        db.commit()

        # Confirm change, then show the main menu in the new language
        confirmation = t("language_changed", new_lang)
        welcome = t("welcome", new_lang)
        await safe_edit_or_reply(
            update,
            f"{confirmation}\n\n{welcome}",
            reply_markup=main_menu_keyboard(new_lang),
        )

    except Exception as exc:
        db.rollback()
        logger.error("_set_language error: %s", exc, exc_info=True)
    finally:
        db.close()
