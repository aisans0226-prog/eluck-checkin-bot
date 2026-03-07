# ============================================================
# utils/keyboard.py — Inline & ReplyKeyboard factory helpers
# ============================================================

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from utils.i18n import t
import config
import database
from models.bot_config import get_config


def _get_link(key: str, fallback: str) -> str:
    """Read a link from DB config, falling back to config.py value."""
    try:
        if database.SessionLocal is None:
            return fallback
        db = database.SessionLocal()
        val = get_config(db, key)
        db.close()
        return val if val else fallback
    except Exception:
        return fallback


def _get_bool(key: str, fallback: bool) -> bool:
    """Read a boolean flag from DB config."""
    try:
        if database.SessionLocal is None:
            return fallback
        db = database.SessionLocal()
        val = get_config(db, key)
        db.close()
        return val.lower() == "true" if val else fallback
    except Exception:
        return fallback


def main_menu_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """
    Build the main menu inline keyboard shown on /start and Home button.
    Matches the spec layout exactly.
    """
    play_url      = _get_link("PLAY_URL",     config.PLAY_URL)
    game_url      = _get_link("GAME_URL",     config.GAME_URL)
    event_url     = _get_link("EVENT_URL",    config.EVENT_URL)
    download_url  = _get_link("DOWNLOAD_URL", config.DOWNLOAD_URL)
    play_webapp   = _get_bool("PLAY_AS_WEBAPP", config.PLAY_AS_WEBAPP)
    game_webapp   = _get_bool("GAME_AS_WEBAPP", config.GAME_AS_WEBAPP)

    buttons = [
        # Row 1
        [
            InlineKeyboardButton(t("btn_profile", lang), callback_data="menu:profile"),
            InlineKeyboardButton(t("btn_checkin", lang), callback_data="menu:checkin"),
        ],
        # Row 2
        [
            InlineKeyboardButton(t("btn_events", lang), url=event_url),
        ],
        # Row 3
        [
            InlineKeyboardButton(
                t("btn_games", lang),
                web_app=WebAppInfo(url=game_url) if game_webapp else None,
                url=game_url if not game_webapp else None,
            ),
            InlineKeyboardButton(t("btn_leaderboard", lang), callback_data="menu:leaderboard"),
        ],
        # Row 4
        [
            InlineKeyboardButton(t("btn_download", lang), url=download_url),
            InlineKeyboardButton(
                t("btn_play", lang),
                web_app=WebAppInfo(url=play_url) if play_webapp else None,
                url=play_url if not play_webapp else None,
            ),
        ],
        # Row 5 — extra utility
        [
            InlineKeyboardButton(t("btn_tasks", lang), callback_data="menu:tasks"),
            InlineKeyboardButton(t("btn_referral", lang), callback_data="menu:referral"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def profile_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Keyboard shown below the profile card."""
    buttons = [
        [
            InlineKeyboardButton(t("btn_checkin_now", lang), callback_data="menu:checkin"),
            InlineKeyboardButton(t("btn_referral_link", lang), callback_data="menu:referral"),
        ],
        [
            InlineKeyboardButton(t("btn_my_tasks", lang), callback_data="menu:tasks"),
            InlineKeyboardButton(t("btn_leaderboard", lang), callback_data="menu:leaderboard"),
        ],
        [InlineKeyboardButton(t("btn_home", lang), callback_data="menu:home")],
    ]
    return InlineKeyboardMarkup(buttons)


def checkin_success_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Keyboard shown after a successful check-in."""
    buttons = [
        [
            InlineKeyboardButton(t("btn_profile", lang), callback_data="menu:profile"),
            InlineKeyboardButton(t("btn_leaderboard", lang), callback_data="menu:leaderboard"),
        ],
        [
            InlineKeyboardButton(t("btn_complete_tasks", lang), callback_data="menu:tasks"),
            InlineKeyboardButton(t("btn_share_refer", lang), callback_data="menu:referral"),
        ],
        [InlineKeyboardButton(t("btn_home", lang), callback_data="menu:home")],
    ]
    return InlineKeyboardMarkup(buttons)


def back_to_menu_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Simple back-to-main-menu button."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(t("btn_home", lang), callback_data="menu:home")]]
    )


def tasks_keyboard(
    tasks: list, completed_task_ids: list[str], lang: str = "en"
) -> InlineKeyboardMarkup:
    """
    Dynamically build task list keyboard.
    Completed tasks show a ✅ prefix.
    """
    rows = []
    for task in tasks:
        done = task["id"] in completed_task_ids
        label = f"{'✅' if done else '🔲'} {task['name']} (+{task['reward']} pts)"
        cb = f"task:view:{task['id']}"
        rows.append([InlineKeyboardButton(label, callback_data=cb)])
    rows.append([InlineKeyboardButton(t("btn_home", lang), callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


def task_detail_keyboard(
    task: dict, is_completed: bool, lang: str = "en"
) -> InlineKeyboardMarkup:
    """Keyboard for a single task detail view."""
    buttons = []
    if not is_completed:
        if task.get("url"):
            buttons.append(
                [InlineKeyboardButton(t("btn_go_complete", lang), url=task["url"])]
            )
        buttons.append(
            [
                InlineKeyboardButton(
                    t("btn_mark_done", lang),
                    callback_data=f"task:complete:{task['id']}",
                )
            ]
        )
    buttons.append(
        [InlineKeyboardButton(t("btn_back_tasks", lang), callback_data="menu:tasks")]
    )
    return InlineKeyboardMarkup(buttons)


def confirm_keyboard(action: str, lang: str = "en") -> InlineKeyboardMarkup:
    """Yes/No confirmation keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("btn_yes", lang), callback_data=f"confirm:yes:{action}"),
            InlineKeyboardButton(t("btn_no", lang), callback_data=f"confirm:no:{action}"),
        ]
    ])
