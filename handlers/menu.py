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

logger = logging.getLogger(__name__)


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

    # ── Navigation dispatch ───────────────────────────────────
    if data == "menu:home":
        await query.edit_message_text(
            text=config.MSG_WELCOME,
            reply_markup=main_menu_keyboard(),
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
        await _show_tasks(update, context)

    elif data == "menu:referral":
        from handlers.profile import referral_handler
        await referral_handler(update, context)

    elif data.startswith("task:view:"):
        task_id = data.split(":", 2)[2]
        await _show_task_detail(update, context, task_id)

    elif data.startswith("task:complete:"):
        task_id = data.split(":", 2)[2]
        await _complete_task(update, context, task_id)

    else:
        logger.warning("Unhandled callback: %s", data)


# ─────────────────────────────────────────────────────────────
# Task list
# ─────────────────────────────────────────────────────────────
async def _show_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    db = context.bot_data["db_session"]()
    try:
        user = db.query(User).filter(User.telegram_id == tg_user.id).first()
        if not user:
            await safe_edit_or_reply(update, "Please send /start first.")
            return

        completed_ids = get_user_task_status(db, user)
        total_tasks = len(config.TASKS)
        done = len(completed_ids)

        text = (
            f"🎯 <b>TASKS</b>  ({done}/{total_tasks} completed)\n"
            f"{'─' * 28}\n"
            f"Complete tasks to earn extra points!\n"
        )

        await safe_edit_or_reply(
            update,
            text,
            reply_markup=tasks_keyboard(config.TASKS, completed_ids),
        )
    finally:
        db.close()


async def _show_task_detail(
    update: Update, context: ContextTypes.DEFAULT_TYPE, task_id: str
) -> None:
    task_def = next((t for t in config.TASKS if t["id"] == task_id), None)
    if not task_def:
        await safe_edit_or_reply(update, "Task not found.", reply_markup=back_to_menu_keyboard())
        return

    tg_user = update.effective_user
    db = context.bot_data["db_session"]()
    try:
        user = db.query(User).filter(User.telegram_id == tg_user.id).first()
        completed_ids = get_user_task_status(db, user) if user else []
        is_done = task_def["id"] in completed_ids

        status_line = "✅ <b>COMPLETED</b>" if is_done else "🔲 <b>Not completed</b>"

        text = (
            f"🎯 <b>{task_def['name']}</b>\n"
            f"{'─' * 28}\n\n"
            f"{task_def['description']}\n\n"
            f"💰 Reward: <b>+{task_def['reward']} points</b>\n"
            f"Status: {status_line}"
        )

        await safe_edit_or_reply(
            update,
            text,
            reply_markup=task_detail_keyboard(task_def, is_done),
        )
    finally:
        db.close()


async def _complete_task(
    update: Update, context: ContextTypes.DEFAULT_TYPE, task_id: str
) -> None:
    tg_user = update.effective_user
    db = context.bot_data["db_session"]()
    try:
        user = db.query(User).filter(User.telegram_id == tg_user.id).first()
        if not user:
            await safe_edit_or_reply(update, "Please send /start first.")
            return

        success, pts = complete_task(db, user, task_id)
        db.commit()

        task_def = next((t for t in config.TASKS if t["id"] == task_id), {})

        if success:
            text = (
                f"🎉 <b>Task Completed!</b>\n\n"
                f"✅ {task_def.get('name', task_id)}\n"
                f"💰 <b>+{pts} points</b> awarded!\n\n"
                f"Your new total: <b>{user.points:,} points</b>"
            )
        else:
            completed_ids = get_user_task_status(db, user)
            if task_id in completed_ids:
                text = "⚠️ This task is already completed."
            else:
                text = (
                    "⚠️ <b>Requirements not met.</b>\n\n"
                    "Please complete the task requirements first!\n"
                    f"<i>{task_def.get('description', '')}</i>"
                )

        await safe_edit_or_reply(update, text, reply_markup=back_to_menu_keyboard())

    except Exception as exc:
        db.rollback()
        logger.error("_complete_task error: %s", exc, exc_info=True)
    finally:
        db.close()
