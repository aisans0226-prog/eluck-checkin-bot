# ============================================================
# utils/i18n.py — Bot internationalisation (i18n)
# Supported languages:
#   en  — English
#   pt  — Português (Brasil)
#   zh  — 中文 (Chinese Simplified)
#   es  — Español (legacy)
#   mx  — Español (México)
# Language can be changed via the in-bot language picker.
# Auto-detected from tg_user.language_code on first /start.
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
        # Language
        "language_menu_header": (
            "🌐 <b>Choose your language</b>\n\n"
            "Select the language you want to use:"
        ),
        "btn_language": "🌐 Language",
        "language_changed": "✅ Language changed to <b>English</b>.",
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
        # Scheduler messages
        "streak_reminder": (
            "⏰ <b>Don't break your streak!</b>\n\n"
            "🔥 You have a <b>{streak}-day streak</b>!\n"
            "Check in today to keep it alive!"
        ),
    },

    # ─── PORTUGUESE (Brazil / pt-BR) ─────────────────────────
    "pt": {
        # Welcome / start
        "welcome": (
            "🎰 <b>Bem-vindo ao Bot de Check-in da Comunidade!</b>\n\n"
            "Faça check-in todos os dias para ganhar recompensas e manter sua sequência 💎\n\n"
            "Use o menu abaixo para começar:"
        ),
        "referral_bonus": (
            "\n\n🎁 <b>Bônus de indicação!</b> Você foi convidado por um amigo.\n"
            "Ele ganhou <b>+{points} pontos</b>!"
        ),
        "new_referral_notify": (
            "🎉 <b>Nova Indicação!</b>\n\n"
            "<b>{name}</b> entrou usando seu link de indicação!\n"
            "💰 Você ganhou <b>+{points} pontos</b>."
        ),
        # Check-in
        "game_id_required": (
            "🎮 <b>ID do Jogo Necessário</b>\n\n"
            "Por favor, insira seu <b>ID do Jogo</b> para ativar o check-in.\n"
            "<i>Exemplo: <code>12345678</code></i>\n\n"
            "⚠️ Você só precisa fazer isso uma vez!"
        ),
        "invalid_game_id": (
            "❌ <b>ID do Jogo Inválido</b>\n\n"
            "Por favor, insira um ID do Jogo numérico válido (4–20 dígitos).\n"
            "<i>Exemplo: <code>12345678</code></i>"
        ),
        "already_checkedin": (
            "⚠️ <b>Check-in Já Realizado</b>\n\n"
            "Você já fez check-in hoje!\n"
            "Volte amanhã 😊\n\n"
            "🔥 Sequência Atual: <b>{streak} dias</b>"
        ),
        "checkin_success_title": "✅ <b>Check-in Realizado com Sucesso!</b>",
        "game_id_registered": "\n✨ <i>ID do Jogo registrado com sucesso!</i>",
        "streak_line": "🔥 Sequência: <b>{streak} {days}</b>  {bar}",
        "total_checkins_line": "📅 Total de check-ins: <b>{total}</b>",
        "points_earned_line": "💰 Pontos ganhos: <b>+{pts} pts</b>",
        "milestone_bonus": (
            "\n🎉 <b>Bônus de Marco!</b> Você atingiu uma "
            "<b>sequência de {streak} dias!</b>\n"
            "   💰 Bônus: <b>+{bonus} pts</b>"
        ),
        "game_id_line": "🎮 ID do Jogo: <code>{game_id}</code>",
        "day": "dia",
        "days": "dias",
        # Profile
        "profile_header": "👤 <b>PERFIL DO USUÁRIO</b>",
        "telegram_label": "Telegram",
        "game_id_label": "🎮 ID do Jogo",
        "game_id_notset": "<i>Não definido — clique em Check-in para registrar</i>",
        "streak_label": "🔥 Sequência Atual",
        "total_checkins_label": "📅 Total de Check-ins",
        "points_label": "💰 Pontos",
        "referrals_label": "👥 Indicações",
        "referral_points_label": "🎁 Pontos de Indicação",
        "profile_not_found": "⚠️ Perfil não encontrado. Por favor envie /start primeiro.",
        # Referral
        "referral_header": "🔗 <b>Seu Link de Indicação</b>",
        "total_referrals_label": "👥 Total de Indicações",
        "points_earned_label": "💰 Pontos Ganhos",
        "referral_tip": (
            "📌 <i>Compartilhe este link e ganhe "
            "<b>{reward} pontos</b> por cada amigo que entrar!</i>"
        ),
        # Leaderboard
        "leaderboard_header": "🏆 <b>TOP USUÁRIOS DE CHECK-IN</b>",
        "leaderboard_empty": "🏆 Ainda não há dados. Seja o primeiro a fazer check-in!",
        # Tasks
        "tasks_header": "🎯 <b>TAREFAS</b>  ({done}/{total} concluídas)",
        "tasks_subtext": "Conclua tarefas para ganhar pontos extras!",
        "task_completed_badge": "✅ <b>CONCLUÍDA</b>",
        "task_not_completed_badge": "🔲 <b>Não concluída</b>",
        "task_reward_line": "💰 Recompensa: <b>+{reward} pontos</b>",
        "task_status_line": "Status: {status}",
        "task_done_msg": (
            "🎉 <b>Tarefa Concluída!</b>\n\n"
            "✅ {name}\n"
            "💰 <b>+{pts} pontos</b> concedidos!\n\n"
            "Seu novo total: <b>{total:,} pontos</b>"
        ),
        "task_already_done": "⚠️ Esta tarefa já foi concluída.",
        "task_requirements_not_met": (
            "⚠️ <b>Requisitos não atendidos.</b>\n\n"
            "Por favor, complete os requisitos da tarefa primeiro!\n"
            "<i>{desc}</i>"
        ),
        "task_not_found": "Tarefa não encontrada.",
        "start_first": "Por favor envie /start primeiro.",
        # Language
        "language_menu_header": (
            "🌐 <b>Escolha seu idioma</b>\n\n"
            "Selecione o idioma que deseja usar:"
        ),
        "btn_language": "🌐 Idioma",
        "language_changed": "✅ Idioma alterado para <b>Português (Brasil)</b>.",
        # Keyboard buttons
        "btn_profile": "👤 Meu Perfil",
        "btn_checkin": "✅ Check-in Diário",
        "btn_events": "🎟 Eventos",
        "btn_games": "🎮 Explorar Jogos",
        "btn_leaderboard": "🏆 Grandes Vitórias",
        "btn_download": "📥 Baixar App",
        "btn_play": "▶️ Jogar Agora",
        "btn_tasks": "🎯 Tarefas",
        "btn_referral": "🔗 Minha Indicação",
        "btn_home": "🏠 Menu Principal",
        "btn_checkin_now": "✅ Fazer Check-in",
        "btn_referral_link": "🔗 Link de Indicação",
        "btn_my_tasks": "🎯 Minhas Tarefas",
        "btn_complete_tasks": "🎯 Concluir Tarefas",
        "btn_share_refer": "🔗 Compartilhar e Indicar",
        "btn_back_tasks": "◀️ Voltar às Tarefas",
        "btn_go_complete": "🚀 Ir e Concluir",
        "btn_mark_done": "✅ Marcar como Feito",
        "btn_yes": "✅ Sim",
        "btn_no": "❌ Não",
        # General errors
        "error_generic": "⚠️ Ocorreu um erro. Por favor tente novamente.",
        # Scheduler messages
        "streak_reminder": (
            "⏰ <b>Não quebre sua sequência!</b>\n\n"
            "🔥 Você tem uma sequência de <b>{streak} dias</b>!\n"
            "Faça check-in hoje para mantê-la!"
        ),
    },

    # ─── CHINESE (Simplified / zh-Hans) ──────────────────────
    "zh": {
        # Welcome / start
        "welcome": (
            "🎰 <b>欢迎来到社区签到机器人！</b>\n\n"
            "每天签到以赚取奖励并保持您的连续记录 💎\n\n"
            "使用下方菜单开始："
        ),
        "referral_bonus": (
            "\n\n🎁 <b>推荐奖励！</b> 您是由朋友邀请的。\n"
            "他们获得了 <b>+{points} 积分</b>！"
        ),
        "new_referral_notify": (
            "🎉 <b>新推荐！</b>\n\n"
            "<b>{name}</b> 通过您的推荐链接加入了！\n"
            "💰 您获得了 <b>+{points} 积分</b>。"
        ),
        # Check-in
        "game_id_required": (
            "🎮 <b>需要游戏ID</b>\n\n"
            "请输入您的<b>游戏ID</b>以激活签到。\n"
            "<i>示例：<code>12345678</code></i>\n\n"
            "⚠️ 您只需执行一次此操作！"
        ),
        "invalid_game_id": (
            "❌ <b>游戏ID无效</b>\n\n"
            "请输入有效的数字游戏ID（4–20位数字）。\n"
            "<i>示例：<code>12345678</code></i>"
        ),
        "already_checkedin": (
            "⚠️ <b>已签到</b>\n\n"
            "您今天已经签到了！\n"
            "明天再来 😊\n\n"
            "🔥 当前连续天数：<b>{streak} 天</b>"
        ),
        "checkin_success_title": "✅ <b>签到成功！</b>",
        "game_id_registered": "\n✨ <i>游戏ID注册成功！</i>",
        "streak_line": "🔥 连续：<b>{streak} {days}</b>  {bar}",
        "total_checkins_line": "📅 总签到次数：<b>{total}</b>",
        "points_earned_line": "💰 获得积分：<b>+{pts} 分</b>",
        "milestone_bonus": (
            "\n🎉 <b>里程碑奖励！</b> 您达到了 "
            "<b>{streak} 天连续签到！</b>\n"
            "   💰 奖励：<b>+{bonus} 分</b>"
        ),
        "game_id_line": "🎮 游戏ID：<code>{game_id}</code>",
        "day": "天",
        "days": "天",
        # Profile
        "profile_header": "👤 <b>用户资料</b>",
        "telegram_label": "Telegram",
        "game_id_label": "🎮 游戏ID",
        "game_id_notset": "<i>未设置 — 点击签到以注册</i>",
        "streak_label": "🔥 当前连续天数",
        "total_checkins_label": "📅 总签到次数",
        "points_label": "💰 积分",
        "referrals_label": "👥 推荐人数",
        "referral_points_label": "🎁 推荐积分",
        "profile_not_found": "⚠️ 未找到个人资料。请先发送 /start。",
        # Referral
        "referral_header": "🔗 <b>您的推荐链接</b>",
        "total_referrals_label": "👥 总推荐人数",
        "points_earned_label": "💰 已获积分",
        "referral_tip": (
            "📌 <i>分享此链接，每位加入的朋友可获得 "
            "<b>{reward} 积分</b>！</i>"
        ),
        # Leaderboard
        "leaderboard_header": "🏆 <b>签到排行榜</b>",
        "leaderboard_empty": "🏆 暂无排行数据，快来第一个签到吧！",
        # Tasks
        "tasks_header": "🎯 <b>任务</b>  ({done}/{total} 已完成)",
        "tasks_subtext": "完成任务以获取额外积分！",
        "task_completed_badge": "✅ <b>已完成</b>",
        "task_not_completed_badge": "🔲 <b>未完成</b>",
        "task_reward_line": "💰 奖励：<b>+{reward} 积分</b>",
        "task_status_line": "状态：{status}",
        "task_done_msg": (
            "🎉 <b>任务完成！</b>\n\n"
            "✅ {name}\n"
            "💰 已奖励 <b>+{pts} 积分</b>！\n\n"
            "您的新总积分：<b>{total:,} 分</b>"
        ),
        "task_already_done": "⚠️ 该任务已完成。",
        "task_requirements_not_met": (
            "⚠️ <b>未满足要求。</b>\n\n"
            "请先完成任务要求！\n"
            "<i>{desc}</i>"
        ),
        "task_not_found": "未找到任务。",
        "start_first": "请先发送 /start。",
        # Language
        "language_menu_header": (
            "🌐 <b>选择您的语言</b>\n\n"
            "请选择您想使用的语言："
        ),
        "btn_language": "🌐 语言",
        "language_changed": "✅ 语言已切换为<b>中文</b>。",
        # Keyboard buttons
        "btn_profile": "👤 我的资料",
        "btn_checkin": "✅ 每日签到",
        "btn_events": "🎟 活动",
        "btn_games": "🎮 探索游戏",
        "btn_leaderboard": "🏆 大赢家",
        "btn_download": "📥 下载应用",
        "btn_play": "▶️ 立即游玩",
        "btn_tasks": "🎯 任务",
        "btn_referral": "🔗 我的推荐",
        "btn_home": "🏠 主菜单",
        "btn_checkin_now": "✅ 立即签到",
        "btn_referral_link": "🔗 推荐链接",
        "btn_my_tasks": "🎯 我的任务",
        "btn_complete_tasks": "🎯 完成任务",
        "btn_share_refer": "🔗 分享与推荐",
        "btn_back_tasks": "◀️ 返回任务",
        "btn_go_complete": "🚀 前往完成",
        "btn_mark_done": "✅ 标记完成",
        "btn_yes": "✅ 是",
        "btn_no": "❌ 否",
        # General errors
        "error_generic": "⚠️ 发生错误，请重试。",
        # Scheduler messages
        "streak_reminder": (
            "⏰ <b>不要中断您的连续签到！</b>\n\n"
            "🔥 您已连续签到 <b>{streak} 天</b>！\n"
            "今天签到以保持记录！"
        ),
    },

    # ─── SPANISH (kept for backward compat with existing users)
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
        # Language
        "language_menu_header": (
            "🌐 <b>Elige tu idioma</b>\n\n"
            "Selecciona el idioma que deseas usar:"
        ),
        "btn_language": "🌐 Idioma",
        "language_changed": "✅ Idioma cambiado a <b>Español</b>.",
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
        # Scheduler messages
        "streak_reminder": (
            "⏰ <b>¡No rompas tu racha!</b>\n\n"
            "🔥 ¡Tienes una racha de <b>{streak} días</b>!\n"
            "¡Haz check-in hoy para mantenerla!"
        ),
    },

    # ─── SPANISH — México (🇲🇽 es-MX) ────────────────────────
    "mx": {
        # Welcome / start
        "welcome": (
            "🎰 <b>¡Bienvenido al Bot de Check-in de la Comunidad!</b>\n\n"
            "Haz check-in todos los días para ganar recompensas y mantener tu racha 💎\n\n"
            "¡Usa el menú de abajo para empezar!"
        ),
        "referral_bonus": (
            "\n\n🎁 <b>¡Bono por referido!</b> Un amigo te invitó.\n"
            "¡Ganaron <b>+{points} puntos</b>!"
        ),
        "new_referral_notify": (
            "🎉 <b>¡Nuevo Referido!</b>\n\n"
            "<b>{name}</b> se unió con tu enlace de referido.\n"
            "💰 Ganaste <b>+{points} puntos</b>."
        ),
        # Check-in
        "game_id_required": (
            "🎮 <b>Se Necesita ID de Juego</b>\n\n"
            "Por favor ingresa tu <b>ID de Juego</b> para activar el check-in.\n"
            "<i>Ejemplo: <code>12345678</code></i>\n\n"
            "⚠️ ¡Solo necesitas hacerlo una vez!"
        ),
        "invalid_game_id": (
            "❌ <b>ID de Juego Inválido</b>\n\n"
            "Ingresa un ID de Juego numérico válido (4–20 dígitos).\n"
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
            "\n🎉 <b>¡Bono de Logro!</b> ¡Alcanzaste una "
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
        "game_id_notset": "<i>No configurado — haz Check-in para registrar</i>",
        "streak_label": "🔥 Racha Actual",
        "total_checkins_label": "📅 Total Check-ins",
        "points_label": "💰 Puntos",
        "referrals_label": "👥 Referidos",
        "referral_points_label": "🎁 Puntos por Referidos",
        "profile_not_found": "⚠️ Perfil no encontrado. Por favor envía /start primero.",
        # Referral
        "referral_header": "🔗 <b>Tu Enlace de Referido</b>",
        "total_referrals_label": "👥 Total Referidos",
        "points_earned_label": "💰 Puntos Ganados",
        "referral_tip": (
            "📌 <i>Comparte este enlace y gana "
            "<b>{reward} puntos</b> por cada amigo que se una!</i>"
        ),
        # Leaderboard
        "leaderboard_header": "🏆 <b>TOP USUARIOS DE CHECK-IN</b>",
        "leaderboard_empty": "🏆 Sin datos aún. ¡Sé el primero en hacer check-in!",
        # Tasks
        "tasks_header": "🎯 <b>TAREAS</b>  ({done}/{total} completadas)",
        "tasks_subtext": "¡Completa tareas para ganar puntos extra!",
        "task_completed_badge": "✅ <b>COMPLETADA</b>",
        "task_not_completed_badge": "🔲 <b>Sin completar</b>",
        "task_reward_line": "💰 Recompensa: <b>+{reward} puntos</b>",
        "task_status_line": "Estado: {status}",
        "task_done_msg": (
            "🎉 <b>¡Tarea Completada!</b>\n\n"
            "✅ {name}\n"
            "💰 ¡<b>+{pts} puntos</b> otorgados!\n\n"
            "Tu nuevo total: <b>{total:,} puntos</b>"
        ),
        "task_already_done": "⚠️ Esta tarea ya fue completada.",
        "task_requirements_not_met": (
            "⚠️ <b>Requisitos no cumplidos.</b>\n\n"
            "¡Primero completa los requisitos de la tarea!\n"
            "<i>{desc}</i>"
        ),
        "task_not_found": "Tarea no encontrada.",
        "start_first": "Por favor envía /start primero.",
        # Language
        "language_menu_header": (
            "🌐 <b>Elige tu idioma</b>\n\n"
            "Selecciona el idioma que quieres usar:"
        ),
        "btn_language": "🌐 Idioma",
        "language_changed": "✅ Idioma cambiado a <b>Español (México) 🇲🇽</b>.",
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
        "btn_referral_link": "🔗 Enlace Referido",
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
        # Scheduler messages
        "streak_reminder": (
            "⏰ <b>¡No rompas tu racha!</b>\n\n"
            "🔥 ¡Tienes una racha de <b>{streak} días</b>!\n"
            "¡Haz check-in hoy para mantenerla!"
        ),
    },
}


def detect_lang(language_code: str | None) -> str:
    """
    Detect bot language from Telegram user.language_code.
    - Starts with 'pt'        (pt, pt-BR, pt-PT …)  → 'pt'
    - Starts with 'zh'        (zh, zh-hans, zh-hant) → 'zh'
    - Exactly 'es-mx' / 'es-419'                    → 'mx'  (Mexican Spanish)
    - Starts with 'es'        (generic Spanish)      → 'es'  (legacy)
    - Everything else                                → 'en'
    """
    if not language_code:
        return "en"
    lc = language_code.lower()
    if lc.startswith("pt"):
        return "pt"
    if lc.startswith("zh"):
        return "zh"
    if lc in ("es-mx", "es_mx", "es-419"):
        return "mx"
    if lc.startswith("es"):
        return "es"
    return "en"


def t(key: str, lang: str = "en", **kwargs) -> str:
    """
    Return translated string for *key* in *lang*.
    Falls back to English if the key is missing in the chosen language.
    Supports str.format() kwargs.
    """
    bucket = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    text = bucket.get(key) or TRANSLATIONS["en"].get(key, key)
    return text.format(**kwargs) if kwargs else text
