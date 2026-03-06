# ============================================================
# utils/i18n.py — Bot internationalisation (i18n)
# Supported languages: en (English), es (Spanish / Mexico)
# Language is auto-detected from tg_user.language_code on /start
# ============================================================

TRANSLATIONS: dict[str, dict[str, str]] = {
    # ─── ENGLISH ────────────────────────────────────────────
    "en": {
        # Welcome / start
        "welcome": (
            "🎰 <b>Welcome to Community Check-in Bot!</b>\n\n"
            "Check in every day to earn rewards and keep your streak alive 💎\n\n"
            "Use the menu below to get started:"
        ),
        "referral_bonus": (
            "\n\n🎁 <b>Referral bonus!</b> You were invited by a friend.\n"
            "They earned <b>+{points} points</b>!"
        ),
        "new_referral_notify": (
            "🎉 <b>New Referral!</b>\n\n"
            "<b>{name}</b> joined using your referral link!\n"
            "💰 You earned <b>+{points} points</b>."
        ),
        # Check-in
        "game_id_required": (
            "🎮 <b>Game ID Required</b>\n\n"
            "Please enter your <b>Game ID</b> to activate check-in.\n"
            "<i>Example: <code>12345678</code></i>\n\n"
            "⚠️ You only need to do this once!"
        ),
        "invalid_game_id": (
            "❌ <b>Invalid Game ID</b>\n\n"
            "Please enter a valid numeric Game ID (4–20 digits).\n"
            "<i>Example: <code>12345678</code></i>"
        ),
        "already_checkedin": (
            "⚠️ <b>Already Checked In</b>\n\n"
            "You already checked in today!\n"
            "Come back tomorrow 😊\n\n"
            "🔥 Current Streak: <b>{streak} days</b>"
        ),
        "checkin_success_title": "✅ <b>Check-in Successful!</b>",
        "game_id_registered": "\n✨ <i>Game ID registered successfully!</i>",
        "streak_line": "🔥 Streak: <b>{streak} {days}</b>  {bar}",
        "total_checkins_line": "📅 Total check-ins: <b>{total}</b>",
        "points_earned_line": "💰 Points earned: <b>+{pts} pts</b>",
        "milestone_bonus": (
            "\n🎉 <b>Milestone Bonus!</b> You reached a "
            "<b>{streak}-day streak!</b>\n"
            "   💰 Bonus: <b>+{bonus} pts</b>"
        ),
        "game_id_line": "🎮 Game ID: <code>{game_id}</code>",
        "day": "day",
        "days": "days",
        # Profile
        "profile_header": "👤 <b>USER PROFILE</b>",
        "telegram_label": "Telegram",
        "game_id_label": "🎮 Game ID",
        "game_id_notset": "<i>Not set — click Check-in to register</i>",
        "streak_label": "🔥 Current Streak",
        "total_checkins_label": "📅 Total Check-ins",
        "points_label": "💰 Points",
        "referrals_label": "👥 Referrals",
        "referral_points_label": "🎁 Referral Points",
        "profile_not_found": "⚠️ Profile not found. Please send /start first.",
        # Referral
        "referral_header": "🔗 <b>Your Referral Link</b>",
        "total_referrals_label": "👥 Total Referrals",
        "points_earned_label": "💰 Points Earned",
        "referral_tip": (
            "📌 <i>Share this link and earn "
            "<b>{reward} points</b> for every friend who joins!</i>"
        ),
        # Leaderboard
        "leaderboard_header": "🏆 <b>TOP CHECK-IN USERS</b>",
        "leaderboard_empty": "🏆 No leaderboard data yet. Be the first to check in!",
        # Tasks
        "tasks_header": "🎯 <b>TASKS</b>  ({done}/{total} completed)",
        "tasks_subtext": "Complete tasks to earn extra points!",
        "task_completed_badge": "✅ <b>COMPLETED</b>",
        "task_not_completed_badge": "🔲 <b>Not completed</b>",
        "task_reward_line": "💰 Reward: <b>+{reward} points</b>",
        "task_status_line": "Status: {status}",
        "task_done_msg": (
            "🎉 <b>Task Completed!</b>\n\n"
            "✅ {name}\n"
            "💰 <b>+{pts} points</b> awarded!\n\n"
            "Your new total: <b>{total:,} points</b>"
        ),
        "task_already_done": "⚠️ This task is already completed.",
        "task_requirements_not_met": (
            "⚠️ <b>Requirements not met.</b>\n\n"
            "Please complete the task requirements first!\n"
            "<i>{desc}</i>"
        ),
        "task_not_found": "Task not found.",
        "start_first": "Please send /start first.",
        # Keyboard buttons
        "btn_profile": "👤 My Profile",
        "btn_checkin": "✅ Daily Check-in",
        "btn_events": "🎟 Events",
        "btn_games": "🎮 Explore Games",
        "btn_leaderboard": "🏆 Big Wins",
        "btn_download": "📥 Download App",
        "btn_play": "▶️ Play Now",
        "btn_tasks": "🎯 Tasks",
        "btn_referral": "🔗 My Referral",
        "btn_home": "🏠 Main Menu",
        "btn_checkin_now": "✅ Check-in Now",
        "btn_referral_link": "🔗 Referral Link",
        "btn_my_tasks": "🎯 My Tasks",
        "btn_complete_tasks": "🎯 Complete Tasks",
        "btn_share_refer": "🔗 Share & Refer",
        "btn_back_tasks": "◀️ Back to Tasks",
        "btn_go_complete": "🚀 Go & Complete",
        "btn_mark_done": "✅ Mark as Done",
        "btn_yes": "✅ Yes",
        "btn_no": "❌ No",
        # General errors
        "error_generic": "⚠️ An error occurred. Please try again.",
    },

    # ─── SPANISH (Mexico / es-MX) ────────────────────────────
    "es": {
        # Welcome / start
        "welcome": (
            "🎰 <b>¡Bienvenido al Bot de Check-in de la Comunidad!</b>\n\n"
            "Haz check-in todos los días para ganar recompensas y mantener tu racha 💎\n\n"
            "Usa el menú de abajo para comenzar:"
        ),
        "referral_bonus": (
            "\n\n🎁 <b>¡Bono de referido!</b> Fuiste invitado por un amigo.\n"
            "¡Ellos ganaron <b>+{points} puntos</b>!"
        ),
        "new_referral_notify": (
            "🎉 <b>¡Nuevo Referido!</b>\n\n"
            "<b>{name}</b> se unió usando tu enlace de referido.\n"
            "💰 Ganaste <b>+{points} puntos</b>."
        ),
        # Check-in
        "game_id_required": (
            "🎮 <b>Se Requiere ID de Juego</b>\n\n"
            "Por favor ingresa tu <b>ID de Juego</b> para activar el check-in.\n"
            "<i>Ejemplo: <code>12345678</code></i>\n\n"
            "⚠️ ¡Solo necesitas hacer esto una vez!"
        ),
        "invalid_game_id": (
            "❌ <b>ID de Juego Inválido</b>\n\n"
            "Por favor ingresa un ID de Juego numérico válido (4–20 dígitos).\n"
            "<i>Ejemplo: <code>12345678</code></i>"
        ),
        "already_checkedin": (
            "⚠️ <b>Ya Hiciste Check-in</b>\n\n"
            "¡Ya hiciste check-in hoy!\n"
            "Vuelve mañana 😊\n\n"
            "🔥 Racha Actual: <b>{streak} días</b>"
        ),
        "checkin_success_title": "✅ <b>¡Check-in Exitoso!</b>",
        "game_id_registered": "\n✨ <i>¡ID de Juego registrado exitosamente!</i>",
        "streak_line": "🔥 Racha: <b>{streak} {days}</b>  {bar}",
        "total_checkins_line": "📅 Total check-ins: <b>{total}</b>",
        "points_earned_line": "💰 Puntos ganados: <b>+{pts} pts</b>",
        "milestone_bonus": (
            "\n🎉 <b>¡Bono de Hito!</b> ¡Alcanzaste una "
            "<b>racha de {streak} días!</b>\n"
            "   💰 Bono: <b>+{bonus} pts</b>"
        ),
        "game_id_line": "🎮 ID de Juego: <code>{game_id}</code>",
        "day": "día",
        "days": "días",
        # Profile
        "profile_header": "👤 <b>PERFIL DE USUARIO</b>",
        "telegram_label": "Telegram",
        "game_id_label": "🎮 ID de Juego",
        "game_id_notset": "<i>No configurado — haz Click en Check-in para registrar</i>",
        "streak_label": "🔥 Racha Actual",
        "total_checkins_label": "📅 Total Check-ins",
        "points_label": "💰 Puntos",
        "referrals_label": "👥 Referidos",
        "referral_points_label": "🎁 Puntos de Referido",
        "profile_not_found": "⚠️ Perfil no encontrado. Por favor envía /start primero.",
        # Referral
        "referral_header": "🔗 <b>Tu Enlace de Referido</b>",
        "total_referrals_label": "👥 Total de Referidos",
        "points_earned_label": "💰 Puntos Ganados",
        "referral_tip": (
            "📌 <i>Comparte este enlace y gana "
            "<b>{reward} puntos</b> por cada amigo que se una!</i>"
        ),
        # Leaderboard
        "leaderboard_header": "🏆 <b>TOP USUARIOS DE CHECK-IN</b>",
        "leaderboard_empty": "🏆 Aún no hay datos. ¡Sé el primero en hacer check-in!",
        # Tasks
        "tasks_header": "🎯 <b>TAREAS</b>  ({done}/{total} completadas)",
        "tasks_subtext": "¡Completa tareas para ganar puntos extra!",
        "task_completed_badge": "✅ <b>COMPLETADA</b>",
        "task_not_completed_badge": "🔲 <b>No completada</b>",
        "task_reward_line": "💰 Recompensa: <b>+{reward} puntos</b>",
        "task_status_line": "Estado: {status}",
        "task_done_msg": (
            "🎉 <b>¡Tarea Completada!</b>\n\n"
            "✅ {name}\n"
            "💰 ¡<b>+{pts} puntos</b> otorgados!\n\n"
            "Tu nuevo total: <b>{total:,} puntos</b>"
        ),
        "task_already_done": "⚠️ Esta tarea ya está completada.",
        "task_requirements_not_met": (
            "⚠️ <b>Requisitos no cumplidos.</b>\n\n"
            "¡Por favor completa primero los requisitos de la tarea!\n"
            "<i>{desc}</i>"
        ),
        "task_not_found": "Tarea no encontrada.",
        "start_first": "Por favor envía /start primero.",
        # Keyboard buttons
        "btn_profile": "👤 Mi Perfil",
        "btn_checkin": "✅ Check-in Diario",
        "btn_events": "🎟 Eventos",
        "btn_games": "🎮 Explorar Juegos",
        "btn_leaderboard": "🏆 Grandes Ganancias",
        "btn_download": "📥 Descargar App",
        "btn_play": "▶️ Jugar Ahora",
        "btn_tasks": "🎯 Tareas",
        "btn_referral": "🔗 Mi Referido",
        "btn_home": "🏠 Menú Principal",
        "btn_checkin_now": "✅ Check-in Ahora",
        "btn_referral_link": "🔗 Enlace de Referido",
        "btn_my_tasks": "🎯 Mis Tareas",
        "btn_complete_tasks": "🎯 Completar Tareas",
        "btn_share_refer": "🔗 Compartir y Referir",
        "btn_back_tasks": "◀️ Volver a Tareas",
        "btn_go_complete": "🚀 Ir y Completar",
        "btn_mark_done": "✅ Marcar como Hecho",
        "btn_yes": "✅ Sí",
        "btn_no": "❌ No",
        # General errors
        "error_generic": "⚠️ Ocurrió un error. Por favor intenta de nuevo.",
    },
}


def detect_lang(language_code: str | None) -> str:
    """
    Detect bot language from Telegram user.language_code.
    - Starts with 'es' (es, es-MX, es-419, es-ES …) → 'es'
    - Everything else → 'en'
    """
    if language_code and language_code.lower().startswith("es"):
        return "es"
    return "en"


def t(key: str, lang: str = "en", **kwargs) -> str:
    """
    Return translated string for *key* in *lang*.
    Falls back to English if the key is missing.
    Supports str.format() kwargs.
    """
    bucket = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    text = bucket.get(key) or TRANSLATIONS["en"].get(key, key)
    return text.format(**kwargs) if kwargs else text
