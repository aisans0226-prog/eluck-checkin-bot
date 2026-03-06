# ============================================================
# utils/keyboard.py — Inline & ReplyKeyboard factory helpers
# ============================================================

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import config


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Build the main menu inline keyboard shown on /start and Home button.
    Matches the spec layout exactly.
    """
    buttons = [
        # Row 1
        [
            InlineKeyboardButton("👤 My Profile", callback_data="menu:profile"),
            InlineKeyboardButton("✅ Daily Check-in", callback_data="menu:checkin"),
        ],
        # Row 2
        [
            InlineKeyboardButton("🎟 Events", url=config.EVENT_URL),
        ],
        # Row 3
        [
            InlineKeyboardButton("🎮 Explore Games", url=config.GAME_URL),
            InlineKeyboardButton("🏆 Big Wins", callback_data="menu:leaderboard"),
        ],
        # Row 4
        [
            InlineKeyboardButton("📥 Download App", url=config.DOWNLOAD_URL),
            InlineKeyboardButton("▶️ Play Now", url=config.PLAY_URL),
        ],
        # Row 5 — extra utility
        [
            InlineKeyboardButton("🎯 Tasks", callback_data="menu:tasks"),
            InlineKeyboardButton("🔗 My Referral", callback_data="menu:referral"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def profile_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown below the profile card."""
    buttons = [
        [
            InlineKeyboardButton("✅ Check-in Now", callback_data="menu:checkin"),
            InlineKeyboardButton("🔗 Referral Link", callback_data="menu:referral"),
        ],
        [
            InlineKeyboardButton("🎯 My Tasks", callback_data="menu:tasks"),
            InlineKeyboardButton("🏆 Leaderboard", callback_data="menu:leaderboard"),
        ],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu:home")],
    ]
    return InlineKeyboardMarkup(buttons)


def checkin_success_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown after a successful check-in."""
    buttons = [
        [
            InlineKeyboardButton("👤 My Profile", callback_data="menu:profile"),
            InlineKeyboardButton("🏆 Leaderboard", callback_data="menu:leaderboard"),
        ],
        [
            InlineKeyboardButton("🎯 Complete Tasks", callback_data="menu:tasks"),
            InlineKeyboardButton("🔗 Share & Refer", callback_data="menu:referral"),
        ],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu:home")],
    ]
    return InlineKeyboardMarkup(buttons)


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Simple back-to-main-menu button."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🏠 Main Menu", callback_data="menu:home")]]
    )


def tasks_keyboard(tasks: list, completed_task_ids: list[str]) -> InlineKeyboardMarkup:
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
    rows.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


def task_detail_keyboard(task: dict, is_completed: bool) -> InlineKeyboardMarkup:
    """Keyboard for a single task detail view."""
    buttons = []
    if not is_completed:
        if task.get("url"):
            buttons.append([InlineKeyboardButton("🚀 Go & Complete", url=task["url"])])
        buttons.append(
            [InlineKeyboardButton("✅ Mark as Done", callback_data=f"task:complete:{task['id']}")]
        )
    buttons.append([InlineKeyboardButton("◀️ Back to Tasks", callback_data="menu:tasks")])
    return InlineKeyboardMarkup(buttons)


def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    """Yes/No confirmation keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes", callback_data=f"confirm:yes:{action}"),
            InlineKeyboardButton("❌ No", callback_data=f"confirm:no:{action}"),
        ]
    ])
