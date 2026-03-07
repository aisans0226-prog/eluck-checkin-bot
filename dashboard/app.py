# ============================================================
# dashboard/app.py — Admin Dashboard (Flask)
#
# Features:
#   - Multi-level admin: super_admin (full) + admin (per-permission)
#   - DB-based auth with werkzeug password hashing
#   - Full audit log for every state-changing action
#   - Overview stats & Chart.js charts
#   - User management (view, edit, add points, reset streak)
#   - Task management (CRUD task definitions in DB)
#   - Reward configuration (edit points values via DB)
#   - Broadcast to all/active users via Telegram Bot API
#   - Export CSV
#
# Run:  python dashboard/app.py
# First login: credentials from DASHBOARD_USERNAME / DASHBOARD_PASSWORD in .env
#              (auto-creates super_admin; env vars ignored after that)
# ============================================================

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import io
import json
import logging
import csv
import uuid
import atexit
from datetime import date, timedelta, datetime, timezone
from functools import wraps

import pytz
import requests
import pandas as pd
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from flask import (
    Flask, render_template, redirect, url_for,
    request, session, flash, jsonify, Response,
)
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func, text, create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session

import config
from database import init_db, Base
from models.user import User
from models.checkin import CheckinLog
from models.referral import Referral
from models.task import UserTask
from models.task_definition import TaskDefinition
from models.bot_config import BotConfig, get_config, set_config, DEFAULT_CONFIGS, DEFAULT_LINK_CONFIGS
from models.dashboard_user import DashboardUser
from models.audit_log import AuditLog
from models.scheduled_broadcast import ScheduledBroadcast
from models.user_event import UserEvent
from services.ai_analytics_service import (
    predict_churn_risk,
    summarize_behavior,
    forecast_engagement,
)

load_dotenv()

# ─────────────────────────────────────────────────────────────
# Flask app setup
# ─────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("DASHBOARD_SECRET_KEY", "change-me-in-production-secret-key")

# Initial super_admin seed credentials (only used once on first run)
_INIT_USERNAME = os.getenv("DASHBOARD_USERNAME", "admin")
_INIT_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "admin123")
TELEGRAM_API   = f"https://api.telegram.org/bot{config.BOT_TOKEN}"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Database — dedicated thread-safe engine for Flask
# ─────────────────────────────────────────────────────────────
_db_url = config.DATABASE_URL
if _db_url.startswith("sqlite"):
    from sqlalchemy.pool import NullPool
    _engine = create_engine(
        _db_url,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
        echo=False,
    )
    @event.listens_for(_engine, "connect")
    def set_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()
else:
    _engine = create_engine(_db_url, pool_pre_ping=True, pool_size=5, echo=False)

Base.metadata.create_all(bind=_engine)
_SessionLocal = scoped_session(sessionmaker(bind=_engine, autocommit=False, autoflush=False))


@app.teardown_appcontext
def remove_session(_exc=None):
    _SessionLocal.remove()


def db_session():
    return _SessionLocal()


# ─────────────────────────────────────────────────────────────
# Broadcast scheduling — constants & helpers
# ─────────────────────────────────────────────────────────────
BROADCAST_IMAGE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "broadcast_images")
)
os.makedirs(BROADCAST_IMAGE_DIR, exist_ok=True)

TIMEZONES = [
    ("UTC",                  "UTC — Coordinated Universal"),
    ("America/Mexico_City",  "UTC-6  Mexico City (CST/CDT)"),
    ("America/New_York",     "UTC-5  New York (EST/EDT)"),
    ("America/Chicago",      "UTC-6  Chicago (CST/CDT)"),
    ("America/Denver",       "UTC-7  Denver (MST/MDT)"),
    ("America/Los_Angeles",  "UTC-8  Los Angeles (PST/PDT)"),
    ("America/Sao_Paulo",    "UTC-3  São Paulo (BRT)"),
    ("Europe/London",        "UTC+0  London (GMT/BST)"),
    ("Europe/Paris",         "UTC+1  Paris (CET/CEST)"),
    ("Europe/Berlin",        "UTC+1  Berlin (CET/CEST)"),
    ("Europe/Moscow",        "UTC+3  Moscow (MSK)"),
    ("Africa/Cairo",         "UTC+2  Cairo (EET)"),
    ("Asia/Dubai",           "UTC+4  Dubai (GST)"),
    ("Asia/Kolkata",         "UTC+5:30 Mumbai / New Delhi (IST)"),
    ("Asia/Dhaka",           "UTC+6  Dhaka (BST)"),
    ("Asia/Bangkok",         "UTC+7  Bangkok (ICT)"),
    ("Asia/Ho_Chi_Minh",     "UTC+7  Ho Chi Minh City (ICT)"),
    ("Asia/Shanghai",        "UTC+8  Shanghai / Beijing (CST)"),
    ("Asia/Singapore",       "UTC+8  Singapore (SGT)"),
    ("Asia/Taipei",          "UTC+8  Taipei (CST)"),
    ("Asia/Seoul",           "UTC+9  Seoul (KST)"),
    ("Asia/Tokyo",           "UTC+9  Tokyo (JST)"),
    ("Australia/Sydney",     "UTC+10/11 Sydney (AEST/AEDT)"),
]


def _send_broadcast_to_users(bc: "ScheduledBroadcast", users_list: list) -> tuple[int, int]:
    """Send a broadcast (from DB model) to the given user list. Returns (sent, failed)."""
    image_data, image_content_type = None, "image/jpeg"
    if bc.image_filename:
        img_path = os.path.join(BROADCAST_IMAGE_DIR, bc.image_filename)
        if os.path.exists(img_path):
            with open(img_path, "rb") as fh:
                image_data = fh.read()
            ext = bc.image_filename.rsplit(".", 1)[-1].lower()
            image_content_type = {
                "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png", "gif": "image/gif", "webp": "image/webp",
            }.get(ext, "image/jpeg")

    sent = failed = 0
    for u in users_list:
        try:
            if image_data:
                caption = (
                    f"📢 <b>Announcement</b>\n\n{bc.message_text}"
                    if bc.message_text
                    else "📢 <b>Announcement</b>"
                )
                resp = requests.post(
                    f"{TELEGRAM_API}/sendPhoto",
                    data={"chat_id": u.telegram_id, "caption": caption[:1024], "parse_mode": "HTML"},
                    files={"photo": (bc.image_filename, image_data, image_content_type)},
                    timeout=10,
                )
            else:
                resp = requests.post(
                    f"{TELEGRAM_API}/sendMessage",
                    json={
                        "chat_id": u.telegram_id,
                        "text": f"📢 <b>Announcement</b>\n\n{bc.message_text}",
                        "parse_mode": "HTML",
                    },
                    timeout=5,
                )
            if resp.ok:
                sent += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    return sent, failed


def _execute_scheduled_broadcast(bc_id: int) -> None:
    """Worker called by APScheduler: send one pending scheduled broadcast."""
    db = _SessionLocal()
    try:
        bc = db.query(ScheduledBroadcast).filter(ScheduledBroadcast.id == bc_id).first()
        if not bc or bc.status != "pending":
            return
        bc.status = "sending"
        db.commit()

        week_ago = date.today() - timedelta(days=7)
        if bc.target == "active":
            users_list = db.query(User).filter(User.last_checkin >= week_ago).all()
        elif bc.target == "game_id":
            users_list = db.query(User).filter(User.game_id.isnot(None)).all()
        elif bc.target == "specific_ids":
            ids = [x.strip() for x in (bc.target_game_ids or "").replace("\n", ",").split(",") if x.strip()]
            users_list = db.query(User).filter(User.game_id.in_(ids)).all() if ids else []
        else:
            users_list = db.query(User).all()

        sent, failed = _send_broadcast_to_users(bc, users_list)
        bc.status = "sent"
        bc.sent_count = sent
        bc.failed_count = failed
        bc.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        logger.info("Scheduled broadcast %d sent: sent=%d failed=%d", bc_id, sent, failed)
    except Exception as exc:
        logger.error("Scheduled broadcast %d error: %s", bc_id, exc, exc_info=True)
        try:
            bc = db.query(ScheduledBroadcast).filter(ScheduledBroadcast.id == bc_id).first()
            if bc:
                bc.status = "failed"
                bc.error_message = str(exc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _check_pending_broadcasts() -> None:
    """APScheduler job: fire any broadcasts whose scheduled_at has passed."""
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    db = _SessionLocal()
    try:
        due = (
            db.query(ScheduledBroadcast)
            .filter(
                ScheduledBroadcast.status == "pending",
                ScheduledBroadcast.scheduled_at <= now_utc,
            )
            .all()
        )
        for bc in due:
            _execute_scheduled_broadcast(bc.id)
    except Exception as exc:
        logger.error("Broadcast scheduler check error: %s", exc)
    finally:
        db.close()


# Start the background scheduler (once per process)
_broadcast_scheduler = BackgroundScheduler(timezone="UTC", daemon=True)
_broadcast_scheduler.add_job(
    _check_pending_broadcasts,
    trigger="interval",
    minutes=1,
    id="check_scheduled_broadcasts",
    max_instances=1,
    coalesce=True,
)
_broadcast_scheduler.start()
atexit.register(lambda: _broadcast_scheduler.shutdown(wait=False))


# ─────────────────────────────────────────────────────────────
# Template context processor + filters
# ─────────────────────────────────────────────────────────────
@app.context_processor
def inject_globals():
    today    = date.today()
    week_ago = today - timedelta(days=7)
    return {
        "now":            today,
        "now_7d":         week_ago,
        "app_name":       "Eluck Check in bot",
        "current_role":   session.get("role", ""),
        "current_perms":  session.get("permissions", {}),
    }


@app.template_filter("format_number")
def format_number(value):
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return value


# ─────────────────────────────────────────────────────────────
# Auth decorators
# ─────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def super_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        if session.get("role") != "super_admin":
            flash("Super admin access required.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated


def permission_required(perm: str):
    """Allow super_admin through always; check perm key for admin role."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get("logged_in"):
                return redirect(url_for("login"))
            if session.get("role") == "super_admin":
                return f(*args, **kwargs)
            if not session.get("permissions", {}).get(perm, False):
                flash(f"You don't have permission to access this section.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated
    return decorator


# ─────────────────────────────────────────────────────────────
# Audit log helper
# ─────────────────────────────────────────────────────────────
def log_action(action: str, target: str = None, details: str = None):
    """Write an audit log entry for the current session user."""
    db = db_session()
    try:
        entry = AuditLog(
            admin_username=session.get("username", "unknown"),
            action=action,
            target=target,
            details=details,
            ip_address=request.remote_addr,
        )
        db.add(entry)
        db.commit()
    except Exception as exc:
        logger.error("audit log write failed: %s", exc)
        db.rollback()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# Seed helpers
# ─────────────────────────────────────────────────────────────
def ensure_super_admin():
    """Auto-create super_admin from .env if no dashboard users exist."""
    db = db_session()
    try:
        if db.query(DashboardUser).count() == 0:
            su = DashboardUser(
                username=_INIT_USERNAME,
                password_hash=generate_password_hash(_INIT_PASSWORD),
                role="super_admin",
                permissions={},
                created_by="system",
            )
            db.add(su)
            db.commit()
            logger.info("Super admin '%s' created from .env credentials.", _INIT_USERNAME)
    except Exception as exc:
        db.rollback()
        logger.error("ensure_super_admin error: %s", exc)
    finally:
        db.close()


def seed_defaults():
    db = db_session()
    try:
        for key, (value, desc) in DEFAULT_CONFIGS.items():
            if not db.query(BotConfig).filter(BotConfig.key == key).first():
                db.add(BotConfig(key=key, value=value, description=desc))

        if db.query(TaskDefinition).count() == 0:
            for t in config.TASKS:
                db.add(TaskDefinition(
                    task_key=t["id"],
                    name=t["name"],
                    description=t["description"],
                    reward_points=t["reward"],
                    task_type=t["type"],
                    url=t.get("url"),
                    required_count=t.get("required_count", 1),
                    is_active=True,
                ))
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("seed_defaults error: %s", exc)
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# Helper — reward config
# ─────────────────────────────────────────────────────────────
def get_reward_config(db) -> dict:
    return {
        "POINTS_PER_CHECKIN":   int(get_config(db, "POINTS_PER_CHECKIN",   config.POINTS_PER_CHECKIN)),
        "REFERRAL_REWARD":      int(get_config(db, "REFERRAL_REWARD",      config.REFERRAL_REWARD)),
        "STREAK_7_REWARD":      int(get_config(db, "STREAK_7_REWARD",      config.STREAK_REWARDS.get(7,   100))),
        "STREAK_30_REWARD":     int(get_config(db, "STREAK_30_REWARD",     config.STREAK_REWARDS.get(30,  500))),
        "STREAK_100_REWARD":    int(get_config(db, "STREAK_100_REWARD",    config.STREAK_REWARDS.get(100, 2000))),
        "STREAK_365_REWARD":    int(get_config(db, "STREAK_365_REWARD",    config.STREAK_REWARDS.get(365, 10000))),
        "LEADERBOARD_SIZE":     int(get_config(db, "LEADERBOARD_SIZE",     config.LEADERBOARD_SIZE)),
        "STREAK_REMINDER_HOUR": int(get_config(db, "STREAK_REMINDER_HOUR", 18)),
    }


# ─────────────────────────────────────────────────────────────
# ROUTES — Auth
# ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = db_session()
        try:
            user = db.query(DashboardUser).filter_by(username=username).first()
            if user and user.is_active and check_password_hash(user.password_hash, password):
                session["logged_in"]   = True
                session["username"]    = user.username
                session["role"]        = user.role
                session["permissions"] = user.permissions or {}
                user.last_login = datetime.utcnow()
                db.commit()
                log_action("login")
                return redirect(url_for("dashboard"))
            error = "Invalid credentials or account disabled."
        finally:
            db.close()
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    log_action("logout")
    session.clear()
    return redirect(url_for("login"))


# ─────────────────────────────────────────────────────────────
# ROUTES — Dashboard Overview
# ─────────────────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    db = db_session()
    try:
        today     = date.today()
        week_ago  = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        total_users     = db.query(User).count()
        users_with_game = db.query(User).filter(User.game_id.isnot(None)).count()
        checkins_today  = db.query(CheckinLog).filter(CheckinLog.checkin_date == today).count()
        active_7d       = db.query(User).filter(User.last_checkin >= week_ago).count()
        total_checkins  = db.query(CheckinLog).count()
        total_points    = db.query(func.sum(User.points)).scalar() or 0

        top5 = (
            db.query(User)
            .filter(User.game_id.isnot(None))
            .order_by(User.total_checkin.desc())
            .limit(5).all()
        )

        # Raw SQL to bypass Cython str_to_date in multi-threaded Flask
        recent_rows = db.execute(text("""
            SELECT u.username, u.first_name, u.telegram_id, u.game_id,
                   c.checkin_date, c.streak_at_checkin, c.points_earned
            FROM checkin_logs c JOIN users u ON u.id = c.user_id
            ORDER BY c.created_at DESC LIMIT 15
        """)).fetchall()
        recent_list = []
        for row in recent_rows:
            dname = f"@{row[0]}" if row[0] else (row[1] or f"User{row[2]}")
            recent_list.append({
                "username": dname, "game_id": row[3] or "—",
                "date": str(row[4]), "streak": row[5], "points": row[6],
            })

        rows = db.execute(text("""
            SELECT checkin_date, COUNT(*) AS cnt FROM checkin_logs
            WHERE checkin_date >= :d GROUP BY checkin_date ORDER BY checkin_date
        """), {"d": str(month_ago)}).fetchall()

        nu_rows = db.execute(text("""
            SELECT DATE(register_date) AS rd, COUNT(*) AS cnt FROM users
            WHERE register_date >= :d GROUP BY DATE(register_date) ORDER BY DATE(register_date)
        """), {"d": str(month_ago)}).fetchall()

        return render_template(
            "index.html",
            total_users=total_users, users_with_game=users_with_game,
            checkins_today=checkins_today, active_7d=active_7d,
            total_checkins=total_checkins, total_points=f"{total_points:,}",
            top5=top5, recent=recent_list,
            chart_dates=json.dumps([str(r[0]) for r in rows]),
            chart_counts=json.dumps([r[1] for r in rows]),
            nu_dates=json.dumps([str(r[0]) for r in nu_rows]),
            nu_counts=json.dumps([r[1] for r in nu_rows]),
        )
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# ROUTES — User Management
# ─────────────────────────────────────────────────────────────
@app.route("/users")
@permission_required("users")
def users():
    db = db_session()
    try:
        query = db.query(User)
        q     = request.args.get("q", "").strip()
        if q:
            query = query.filter(
                User.username.ilike(f"%{q}%") |
                User.game_id.ilike(f"%{q}%") |
                User.first_name.ilike(f"%{q}%")
            )
        filt        = request.args.get("filter", "all")
        sort        = request.args.get("sort", "total_checkin")
        order_dir   = request.args.get("order", "desc")
        lang_filter = request.args.get("lang", "")
        try:
            page = max(1, int(request.args.get("page", 1) or 1))
        except (ValueError, TypeError):
            page = 1
        per_page = 50
        today    = date.today()
        week_ago = today - timedelta(days=7)

        if filt == "active":
            query = query.filter(User.last_checkin >= week_ago)
        elif filt == "inactive":
            query = query.filter(
                (User.last_checkin < week_ago) | User.last_checkin.is_(None)
            )
        elif filt == "no_game_id":
            query = query.filter(User.game_id.is_(None))
        elif filt == "banned":
            query = query.filter(User.is_banned == True)
        elif filt == "blocked":
            query = query.filter(User.is_blocked == True)
        elif filt == "has_referrals":
            sub = db.query(Referral.referrer_id).distinct().subquery()
            query = query.filter(User.telegram_id.in_(sub))

        if lang_filter:
            query = query.filter(User.language == lang_filter)

        _sort_map = {
            "total_checkin": User.total_checkin,
            "streak":        User.streak,
            "points":        User.points,
            "register_date": User.register_date,
            "last_checkin":  User.last_checkin,
        }
        sort_col = _sort_map.get(sort, User.total_checkin)
        if order_dir == "asc":
            query = query.order_by(sort_col.asc().nullslast())
        else:
            query = query.order_by(sort_col.desc().nullslast())

        total_count = query.count()
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        page        = min(page, total_pages)
        users_list  = query.offset((page - 1) * per_page).limit(per_page).all()

        lang_rows = db.query(User.language).distinct().all()
        langs = sorted({r[0] for r in lang_rows if r[0]})

        return render_template(
            "users.html",
            users=users_list,
            q=q, filt=filt,
            sort=sort, order=order_dir,
            lang_filter=lang_filter,
            page=page, total_pages=total_pages, total_count=total_count,
            now_7d=week_ago,
            today=today,
            langs=langs,
        )
    finally:
        db.close()


@app.route("/users/<int:telegram_id>", methods=["GET", "POST"])
@permission_required("users")
def user_detail(telegram_id: int):
    db = db_session()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            flash("User not found", "danger")
            return redirect(url_for("users"))

        if request.method == "POST":
            action = request.form.get("action")

            if action == "update":
                old = user.game_id
                user.game_id = request.form.get("game_id", "").strip() or None
                db.commit()
                log_action("update_game_id", f"user:{telegram_id}", f"{old!r} → {user.game_id!r}")
                flash("Game ID updated.", "success")

            elif action == "add_points":
                try:
                    delta = int(request.form.get("delta", 0))
                    old   = user.points
                    user.points = max(0, user.points + delta)
                    db.commit()
                    sign = "+" if delta >= 0 else ""
                    log_action("add_points", f"user:{telegram_id}", f"{sign}{delta} ({old} → {user.points})")
                    flash(f"Points adjusted {sign}{delta}. New total: {user.points:,}", "success")
                except ValueError:
                    flash("Invalid point value.", "danger")

            elif action == "set_streak":
                try:
                    old = user.streak
                    user.streak = max(0, int(request.form.get("streak", 0)))
                    db.commit()
                    log_action("set_streak", f"user:{telegram_id}", f"{old} → {user.streak}")
                    flash(f"Streak set to {user.streak}.", "success")
                except ValueError:
                    flash("Invalid streak value.", "danger")

            elif action == "reset_streak":
                old = user.streak
                user.streak = 0
                db.commit()
                log_action("reset_streak", f"user:{telegram_id}", f"streak {old} → 0")
                flash("Streak reset to 0.", "warning")

            elif action == "ban_user":
                user.game_id = None
                user.streak  = 0
                db.commit()
                log_action("ban_user", f"user:{telegram_id}", "game_id cleared, streak reset")
                flash("User banned (game ID cleared, streak reset).", "warning")

            return redirect(url_for("user_detail", telegram_id=telegram_id))

        # ── Full checkin history (heatmap + charts + KPIs) ────────
        all_history = (
            db.query(CheckinLog).filter(CheckinLog.user_id == user.id)
            .order_by(CheckinLog.checkin_date.asc()).all()
        )
        history = list(reversed(all_history[-60:]))

        checkin_dates_json = json.dumps([str(h.checkin_date) for h in all_history])

        streak_chart = json.dumps([
            {"x": str(h.checkin_date), "y": h.streak_at_checkin}
            for h in all_history[-90:]
        ])

        cum = 0
        cum_pts_list = []
        for h in all_history:
            cum += h.points_earned
            cum_pts_list.append({"x": str(h.checkin_date), "y": cum})
        points_chart = json.dumps(cum_pts_list[-90:])

        # ── Referrals ──────────────────────────────────────────
        referrals = (
            db.query(Referral, User)
            .join(User, User.telegram_id == Referral.referred_id)
            .filter(Referral.referrer_id == telegram_id).all()
        )
        referred_by = None
        if user.referrer_id:
            referred_by = db.query(User).filter(
                User.telegram_id == user.referrer_id
            ).first()

        # ── Tasks ──────────────────────────────────────────────
        user_tasks_q = (
            db.query(UserTask, TaskDefinition)
            .outerjoin(TaskDefinition, TaskDefinition.task_key == UserTask.task_id)
            .filter(UserTask.user_id == user.id)
            .all()
        )

        # ── Events ────────────────────────────────────────────
        recent_events = (
            db.query(UserEvent)
            .filter(UserEvent.telegram_id == telegram_id)
            .order_by(UserEvent.created_at.desc())
            .limit(30).all()
        )
        behavior = summarize_behavior([
            {"event_type": e.event_type, "created_at": e.created_at, "meta": e.meta}
            for e in recent_events
        ])

        # ── KPIs ───────────────────────────────────────────────
        today_date          = date.today()
        days_since_register = max(1, (today_date - user.register_date.date()).days)
        consistency_pct     = round(user.total_checkin / days_since_register * 100, 1)
        avg_pts_per_day     = round(user.points / days_since_register, 1)
        days_inactive       = (
            (today_date - user.last_checkin).days
            if user.last_checkin else days_since_register
        )

        longest_streak = 0
        if all_history:
            cur_run = longest_streak = 1
            for i in range(1, len(all_history)):
                gap = (all_history[i].checkin_date - all_history[i - 1].checkin_date).days
                cur_run = cur_run + 1 if gap == 1 else 1
                if cur_run > longest_streak:
                    longest_streak = cur_run

        completed_tasks = sum(1 for t, _ in user_tasks_q if t.completed)
        total_tasks     = len(user_tasks_q)
        task_ratio      = completed_tasks / max(1, total_tasks)

        churn = predict_churn_risk({
            "streak":          user.streak,
            "total_checkin":   user.total_checkin,
            "days_since_last": days_inactive,
            "task_completion": task_ratio,
            "has_referrals":   len(referrals) > 0,
        })

        if days_since_register <= 7:
            segment = ("new",     "🆕 New",        "primary")
        elif days_inactive > 30:
            segment = ("churned", "💀 Churned",    "danger")
        elif days_inactive > 5:
            segment = ("at_risk", "⚠️ At Risk",    "warning")
        elif user.streak > 30 or user.total_checkin > 100:
            segment = ("power",   "⭐ Power User", "success")
        else:
            segment = ("regular", "✅ Regular",    "secondary")

        return render_template(
            "user_detail.html",
            user=user,
            history=history,
            referrals=referrals,
            referred_by=referred_by,
            user_tasks=user_tasks_q,
            recent_events=recent_events,
            behavior=behavior,
            checkin_dates_json=checkin_dates_json,
            streak_chart=streak_chart,
            points_chart=points_chart,
            days_since_register=days_since_register,
            consistency_pct=consistency_pct,
            avg_pts_per_day=avg_pts_per_day,
            longest_streak=longest_streak,
            days_inactive=days_inactive,
            completed_tasks=completed_tasks,
            total_tasks=total_tasks,
            segment=segment,
            churn=churn,
        )
    finally:
        db.close()


@app.route("/users/bulk-action", methods=["POST"])
@permission_required("users")
def users_bulk_action():
    db = db_session()
    try:
        action   = request.form.get("action", "")
        user_ids = request.form.getlist("user_ids")
        if not user_ids:
            flash("No users selected.", "warning")
            return redirect(url_for("users"))

        # Convert to int, drop invalid values
        try:
            telegram_ids = [int(x) for x in user_ids]
        except ValueError:
            flash("Invalid user selection.", "danger")
            return redirect(url_for("users"))

        affected = (
            db.query(User).filter(User.telegram_id.in_(telegram_ids)).all()
        )
        n = len(affected)

        if action == "reset_streak":
            for u in affected:
                u.streak = 0
            db.commit()
            log_action("bulk_reset_streak", f"{n} users", str(telegram_ids[:10]))
            flash(f"Streak reset for {n} user(s).", "success")

        elif action == "clear_game_id":
            for u in affected:
                u.game_id = None
            db.commit()
            log_action("bulk_clear_game_id", f"{n} users", str(telegram_ids[:10]))
            flash(f"Game ID cleared for {n} user(s).", "success")

        elif action == "add_points":
            try:
                delta = int(request.form.get("delta", 0))
            except ValueError:
                flash("Invalid point value.", "danger")
                return redirect(url_for("users"))
            for u in affected:
                u.points = max(0, u.points + delta)
            db.commit()
            sign = "+" if delta >= 0 else ""
            log_action("bulk_add_points", f"{n} users", f"{sign}{delta} | ids={telegram_ids[:10]}")
            flash(f"Points adjusted {sign}{delta} for {n} user(s).", "success")

        else:
            flash(f"Unknown bulk action: {action}", "danger")

    except Exception as exc:
        db.rollback()
        flash(f"Bulk action failed: {exc}", "danger")
    finally:
        db.close()

    return redirect(url_for("users"))


@app.route("/users/export")
@permission_required("export")
def export_users():
    db = db_session()
    try:
        users_list = db.query(User).order_by(User.total_checkin.desc()).all()
        data = [{
            "telegram_id": u.telegram_id, "username": u.username or "",
            "first_name": u.first_name or "", "game_id": u.game_id or "",
            "register_date": str(u.register_date), "last_checkin": str(u.last_checkin),
            "streak": u.streak, "total_checkin": u.total_checkin,
            "points": u.points, "referrals": u.referral_count, "referrer_id": u.referrer_id or "",
        } for u in users_list]
        buf = io.StringIO()
        pd.DataFrame(data).to_csv(buf, index=False)
        buf.seek(0)
        log_action("export_csv", "users", f"{len(data)} rows")
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=users_{date.today()}.csv"})
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# ROUTES — Task Definitions (CRUD)
# ─────────────────────────────────────────────────────────────
@app.route("/tasks")
@permission_required("tasks")
def tasks():
    db = db_session()
    try:
        return render_template("tasks.html", tasks=db.query(TaskDefinition).order_by(TaskDefinition.id).all())
    finally:
        db.close()


@app.route("/tasks/add", methods=["POST"])
@permission_required("tasks")
def task_add():
    db = db_session()
    try:
        key = request.form.get("task_key", "").strip().lower().replace(" ", "_")
        if not key:
            flash("Task key is required.", "danger")
            return redirect(url_for("tasks"))
        if db.query(TaskDefinition).filter(TaskDefinition.task_key == key).first():
            flash(f"Task key '{key}' already exists.", "danger")
            return redirect(url_for("tasks"))
        td = TaskDefinition(
            task_key=key,
            name=request.form.get("name", "").strip(),
            description=request.form.get("description", "").strip(),
            reward_points=int(request.form.get("reward_points", 10)),
            task_type=request.form.get("task_type", "manual"),
            url=request.form.get("url", "").strip() or None,
            required_count=int(request.form.get("required_count", 1)),
            is_active=bool(request.form.get("is_active")),
        )
        db.add(td)
        db.commit()
        log_action("add_task", f"task:{td.id}", f"key={key} name={td.name!r} pts={td.reward_points}")
        flash(f"Task '{td.name}' added.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Error: {exc}", "danger")
    finally:
        db.close()
    return redirect(url_for("tasks"))


@app.route("/tasks/<int:task_id>/edit", methods=["POST"])
@permission_required("tasks")
def task_edit(task_id: int):
    db = db_session()
    try:
        td = db.query(TaskDefinition).filter(TaskDefinition.id == task_id).first()
        if not td:
            flash("Task not found.", "danger")
            return redirect(url_for("tasks"))
        old_name = td.name
        td.name           = request.form.get("name", td.name).strip()
        td.description    = request.form.get("description", td.description).strip()
        td.reward_points  = int(request.form.get("reward_points", td.reward_points))
        td.task_type      = request.form.get("task_type", td.task_type)
        td.url            = request.form.get("url", "").strip() or None
        td.required_count = int(request.form.get("required_count", td.required_count))
        td.is_active      = request.form.get("is_active") == "on"
        td.updated_at     = datetime.utcnow()
        db.commit()
        new_name = td.name          # refresh while session still open
        new_pts  = td.reward_points
        log_action("edit_task", f"task:{task_id}", f"{old_name!r} → {new_name!r} pts={new_pts}")
        flash(f"Task '{new_name}' updated.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Error: {exc}", "danger")
    finally:
        db.close()
    return redirect(url_for("tasks"))


@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
@permission_required("tasks")
def task_delete(task_id: int):
    db = db_session()
    try:
        td = db.query(TaskDefinition).filter(TaskDefinition.id == task_id).first()
        if td:
            name = td.name
            db.delete(td)
            db.commit()
            log_action("delete_task", f"task:{task_id}", f"name={name!r}")
            flash(f"Task '{name}' deleted.", "warning")
    except Exception as exc:
        db.rollback()
        flash(f"Error: {exc}", "danger")
    finally:
        db.close()
    return redirect(url_for("tasks"))


@app.route("/tasks/<int:task_id>/toggle", methods=["POST"])
@permission_required("tasks")
def task_toggle(task_id: int):
    db = db_session()
    try:
        td = db.query(TaskDefinition).filter(TaskDefinition.id == task_id).first()
        if td:
            td.is_active = not td.is_active
            db.commit()
            status = "activated" if td.is_active else "deactivated"
            log_action("toggle_task", f"task:{task_id}", status)
            return jsonify({"success": True, "is_active": td.is_active, "status": status})
    finally:
        db.close()
    return jsonify({"success": False}), 404


# ─────────────────────────────────────────────────────────────
# ROUTES — Reward Configuration
# ─────────────────────────────────────────────────────────────
@app.route("/rewards", methods=["GET", "POST"])
@permission_required("rewards")
def rewards():
    db = db_session()
    try:
        if request.method == "POST":
            keys = [
                "POINTS_PER_CHECKIN", "REFERRAL_REWARD",
                "STREAK_7_REWARD", "STREAK_30_REWARD",
                "STREAK_100_REWARD", "STREAK_365_REWARD",
                "LEADERBOARD_SIZE", "STREAK_REMINDER_HOUR",
            ]
            changes = []
            for key in keys:
                val = request.form.get(key, "").strip()
                if val.isdigit():
                    old_val = get_config(db, key, "?")
                    set_config(db, key, int(val), DEFAULT_CONFIGS.get(key, ("", ""))[1])
                    changes.append(f"{key}: {old_val} → {val}")
            db.commit()
            log_action("update_rewards", "rewards", " | ".join(changes))
            flash("Reward configuration saved successfully!", "success")
            return redirect(url_for("rewards"))
        return render_template("rewards.html", cfg=get_reward_config(db))
    except Exception as exc:
        db.rollback()
        flash(f"Error: {exc}", "danger")
        return redirect(url_for("rewards"))
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# ROUTES — Bot Links / Mini App Configuration
# ─────────────────────────────────────────────────────────────
def get_link_config(db) -> dict:
    return {
        "PLAY_URL":       get_config(db, "PLAY_URL",       config.PLAY_URL),
        "GAME_URL":       get_config(db, "GAME_URL",       config.GAME_URL),
        "EVENT_URL":      get_config(db, "EVENT_URL",      config.EVENT_URL),
        "DOWNLOAD_URL":   get_config(db, "DOWNLOAD_URL",   config.DOWNLOAD_URL),
        "CHANNEL_URL":    get_config(db, "CHANNEL_URL",     config.CHANNEL_URL),
        "COMMUNITY_URL":  get_config(db, "COMMUNITY_URL",  config.COMMUNITY_URL),
        "PLAY_AS_WEBAPP": get_config(db, "PLAY_AS_WEBAPP",  str(config.PLAY_AS_WEBAPP).lower()),
        "GAME_AS_WEBAPP": get_config(db, "GAME_AS_WEBAPP",  str(config.GAME_AS_WEBAPP).lower()),
    }


@app.route("/links", methods=["GET", "POST"])
@permission_required("rewards")
def links():
    db = db_session()
    try:
        if request.method == "POST":
            url_keys = [
                "PLAY_URL", "GAME_URL", "EVENT_URL",
                "DOWNLOAD_URL", "CHANNEL_URL", "COMMUNITY_URL",
            ]
            bool_keys = ["PLAY_AS_WEBAPP", "GAME_AS_WEBAPP"]
            changes = []
            for key in url_keys:
                val = request.form.get(key, "").strip()
                old_val = get_config(db, key, "")
                if val != old_val:
                    set_config(db, key, val, DEFAULT_LINK_CONFIGS.get(key, ("", ""))[1])
                    changes.append(f"{key}: {old_val} → {val}")
            for key in bool_keys:
                val = "true" if request.form.get(key) else "false"
                old_val = get_config(db, key, "false")
                if val != old_val:
                    set_config(db, key, val, DEFAULT_LINK_CONFIGS.get(key, ("", ""))[1])
                    changes.append(f"{key}: {old_val} → {val}")
            db.commit()
            if changes:
                log_action("update_links", "links", " | ".join(changes))
            flash("Link configuration saved successfully!", "success")
            return redirect(url_for("links"))
        return render_template("links.html", cfg=get_link_config(db))
    except Exception as exc:
        db.rollback()
        flash(f"Error: {exc}", "danger")
        return redirect(url_for("links"))
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# ROUTES — Broadcast
# ─────────────────────────────────────────────────────────────
@app.route("/broadcast", methods=["GET", "POST"])
@permission_required("broadcast")
def broadcast():
    db = db_session()
    try:
        if request.method == "GET":
            total_users = db.query(User).count()
            active_7d   = db.query(User).filter(
                User.last_checkin >= date.today() - timedelta(days=7)
            ).count()
            game_id_count = db.query(User).filter(User.game_id.isnot(None)).count()
            schedules = (
                db.query(ScheduledBroadcast)
                .order_by(ScheduledBroadcast.scheduled_at.desc())
                .limit(100)
                .all()
            )
            pending_count = sum(1 for s in schedules if s.status == "pending")
            return render_template(
                "broadcast.html",
                total_users=total_users,
                active_7d=active_7d,
                game_id_count=game_id_count,
                schedules=schedules,
                pending_count=pending_count,
                timezones=TIMEZONES,
            )

        # ── POST ─────────────────────────────────────────────
        message_text     = request.form.get("message", "").strip()
        target           = request.form.get("target", "all")
        target_game_ids  = request.form.get("target_game_ids", "").strip()
        scheduled_at_str = request.form.get("scheduled_at", "").strip()
        tz_name          = request.form.get("timezone", "UTC").strip()

        image_file = request.files.get("image")
        image_data, image_filename, image_content_type = None, None, "image/jpeg"
        if image_file and image_file.filename:
            image_data         = image_file.read()
            image_filename     = image_file.filename
            image_content_type = image_file.content_type or "image/jpeg"

        if not message_text and not image_data:
            flash("Message cannot be empty.", "danger")
            return redirect(url_for("broadcast"))

        if target == "specific_ids" and not target_game_ids:
            flash("Please enter at least one Game ID to target.", "danger")
            return redirect(url_for("broadcast"))

        # ── Scheduled send ────────────────────────────────────
        if scheduled_at_str:
            try:
                tz       = pytz.timezone(tz_name)
                local_dt = datetime.strptime(scheduled_at_str, "%Y-%m-%dT%H:%M")
                local_dt = tz.localize(local_dt)
                utc_dt   = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
            except Exception as exc:
                flash(f"Invalid scheduled time: {exc}", "danger")
                return redirect(url_for("broadcast"))

            if utc_dt <= datetime.now(timezone.utc).replace(tzinfo=None):
                flash("Scheduled time must be in the future.", "danger")
                return redirect(url_for("broadcast"))

            saved_img = None
            if image_data:
                ext = (os.path.splitext(image_filename)[1] if image_filename else ".jpg").lower()
                saved_img = f"{uuid.uuid4().hex}{ext}"
                with open(os.path.join(BROADCAST_IMAGE_DIR, saved_img), "wb") as fh:
                    fh.write(image_data)

            bc = ScheduledBroadcast(
                message_text=message_text,
                target=target,
                target_game_ids=target_game_ids if target == "specific_ids" else None,
                image_filename=saved_img,
                scheduled_at=utc_dt,
                timezone_name=tz_name,
                status="pending",
                created_by=session.get("username", ""),
            )
            db.add(bc)
            db.commit()
            log_action(
                "schedule_broadcast", f"target:{target}",
                f"scheduled_at={scheduled_at_str} tz={tz_name} msg={message_text[:80]!r}",
            )
            flash(f"✅ Broadcast scheduled for {scheduled_at_str} ({tz_name}).", "success")
            return redirect(url_for("broadcast"))

        # ── Immediate send ─────────────────────────────────────
        week_ago = date.today() - timedelta(days=7)
        if target == "active":
            users_list = db.query(User).filter(User.last_checkin >= week_ago).all()
        elif target == "game_id":
            users_list = db.query(User).filter(User.game_id.isnot(None)).all()
        elif target == "specific_ids":
            ids = [x.strip() for x in target_game_ids.replace("\n", ",").split(",") if x.strip()]
            users_list = db.query(User).filter(User.game_id.in_(ids)).all() if ids else []
        else:
            users_list = db.query(User).all()

        sent, failed = 0, 0
        for u in users_list:
            try:
                if image_data:
                    caption = f"📢 <b>Announcement</b>\n\n{message_text}" if message_text else "📢 <b>Announcement</b>"
                    resp = requests.post(
                        f"{TELEGRAM_API}/sendPhoto",
                        data={"chat_id": u.telegram_id, "caption": caption[:1024], "parse_mode": "HTML"},
                        files={"photo": (image_filename, image_data, image_content_type)},
                        timeout=10,
                    )
                else:
                    resp = requests.post(
                        f"{TELEGRAM_API}/sendMessage",
                        json={"chat_id": u.telegram_id, "text": f"📢 <b>Announcement</b>\n\n{message_text}", "parse_mode": "HTML"},
                        timeout=5,
                    )
                sent   += 1 if resp.ok else 0
                failed += 0 if resp.ok else 1
            except Exception:
                failed += 1

        has_img_note = " [+image]" if image_data else ""
        extra = f" ids={target_game_ids[:80]!r}" if target == "specific_ids" else ""
        log_action("broadcast", f"target:{target}", f"sent={sent} failed={failed}{has_img_note}{extra} msg={message_text[:80]!r}")
        flash(f"Broadcast complete! Sent: {sent:,} | Failed: {failed:,}", "success")
        return redirect(url_for("broadcast"))
    finally:
        db.close()


@app.route("/broadcast/schedule/cancel/<int:bc_id>", methods=["POST"])
@permission_required("broadcast")
def broadcast_schedule_cancel(bc_id: int):
    db = db_session()
    try:
        bc = db.query(ScheduledBroadcast).filter(ScheduledBroadcast.id == bc_id).first()
        if bc and bc.status == "pending":
            bc.status = "cancelled"
            db.commit()
            log_action("cancel_scheduled_broadcast", f"id:{bc_id}", f"msg={bc.message_text[:80]!r}")
            flash(f"Scheduled broadcast #{bc_id} cancelled.", "success")
        else:
            flash("Broadcast not found or already processed.", "danger")
    finally:
        db.close()
    return redirect(url_for("broadcast") + "#tab-queue")


@app.route("/broadcast/schedule/delete/<int:bc_id>", methods=["POST"])
@permission_required("broadcast")
def broadcast_schedule_delete(bc_id: int):
    db = db_session()
    try:
        bc = db.query(ScheduledBroadcast).filter(ScheduledBroadcast.id == bc_id).first()
        if bc and bc.status != "pending":
            if bc.image_filename:
                img_path = os.path.join(BROADCAST_IMAGE_DIR, bc.image_filename)
                if os.path.exists(img_path):
                    os.remove(img_path)
            db.delete(bc)
            db.commit()
            log_action("delete_scheduled_broadcast", f"id:{bc_id}", "")
            flash(f"Broadcast #{bc_id} deleted.", "info")
        else:
            flash("Cannot delete a pending broadcast — cancel it first.", "danger")
    finally:
        db.close()
    return redirect(url_for("broadcast") + "#tab-queue")


@app.route("/broadcast/batch", methods=["POST"])
@permission_required("broadcast")
def broadcast_batch():
    """Schedule multiple text-only broadcasts at once from a JSON payload."""
    try:
        items = request.get_json(force=True)
        if not isinstance(items, list) or not items:
            return jsonify({"error": "Expected a non-empty JSON array"}), 400

        db = db_session()
        created, errors = 0, []
        try:
            for idx, item in enumerate(items):
                msg            = (item.get("message") or "").strip()
                target         = item.get("target", "all")
                sched_str      = (item.get("scheduled_at") or "").strip()
                tz_name        = (item.get("timezone") or "UTC").strip()

                if not msg:
                    errors.append(f"Item {idx+1}: empty message")
                    continue
                try:
                    tz       = pytz.timezone(tz_name)
                    local_dt = datetime.strptime(sched_str, "%Y-%m-%dT%H:%M")
                    utc_dt   = tz.localize(local_dt).astimezone(pytz.utc).replace(tzinfo=None)
                except Exception as exc:
                    errors.append(f"Item {idx+1}: invalid time — {exc}")
                    continue

                if utc_dt <= datetime.now(timezone.utc).replace(tzinfo=None):
                    errors.append(f"Item {idx+1}: time must be in the future")
                    continue

                db.add(ScheduledBroadcast(
                    message_text=msg,
                    target=target,
                    scheduled_at=utc_dt,
                    timezone_name=tz_name,
                    status="pending",
                    created_by=session.get("username", ""),
                ))
                created += 1

            db.commit()
            log_action("batch_schedule_broadcast", f"count:{created}", f"errors={len(errors)}")
        finally:
            db.close()

        return jsonify({"created": created, "errors": errors})
    except Exception as exc:
        logger.error("broadcast_batch error: %s", exc, exc_info=True)
        return jsonify({"error": str(exc)}), 500


@app.route("/broadcast/game_ids", methods=["GET"])
@permission_required("broadcast")
def broadcast_game_ids():
    """AJAX: return list of game_ids matching optional query string."""
    q = request.args.get("q", "").strip()
    db = db_session()
    try:
        query = db.query(User.game_id).filter(User.game_id.isnot(None))
        if q:
            query = query.filter(User.game_id.ilike(f"%{q}%"))
        rows = query.order_by(User.game_id).limit(50).all()
        return jsonify([r[0] for r in rows])
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# ROUTES — Admin Account Management  (super_admin only)
# ─────────────────────────────────────────────────────────────
ALL_PERMISSIONS = ["users", "tasks", "rewards", "broadcast", "export"]


@app.route("/admin-accounts")
@super_admin_required
def admin_accounts():
    db = db_session()
    try:
        admins = db.query(DashboardUser).order_by(DashboardUser.created_at).all()
        return render_template("admin_accounts.html", admins=admins, all_perms=ALL_PERMISSIONS)
    finally:
        db.close()


@app.route("/admin-accounts/add", methods=["POST"])
@super_admin_required
def admin_add():
    db = db_session()
    try:
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role     = request.form.get("role", "admin")

        if not username or not password:
            flash("Username and password are required.", "danger")
            return redirect(url_for("admin_accounts"))
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return redirect(url_for("admin_accounts"))
        if db.query(DashboardUser).filter_by(username=username).first():
            flash(f"Username '{username}' already exists.", "danger")
            return redirect(url_for("admin_accounts"))

        # Build permissions from checkboxes
        perms = {p: (request.form.get(f"perm_{p}") == "on") for p in ALL_PERMISSIONS}

        new_user = DashboardUser(
            username=username,
            password_hash=generate_password_hash(password),
            role=role if role == "super_admin" else "admin",
            permissions=perms,
            created_by=session.get("username"),
        )
        db.add(new_user)
        db.commit()
        log_action("create_admin", f"admin:{username}", f"role={new_user.role} perms={perms}")
        flash(f"Admin account '{username}' created.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Error: {exc}", "danger")
    finally:
        db.close()
    return redirect(url_for("admin_accounts"))


@app.route("/admin-accounts/<int:admin_id>/edit", methods=["POST"])
@super_admin_required
def admin_edit(admin_id: int):
    db = db_session()
    try:
        admin = db.query(DashboardUser).filter_by(id=admin_id).first()
        if not admin:
            flash("Admin not found.", "danger")
            return redirect(url_for("admin_accounts"))

        # Prevent editing own role/perms to avoid lock-out
        is_self = (admin.username == session.get("username"))

        changes = []
        new_role = request.form.get("role", admin.role)
        if not is_self and new_role in ("super_admin", "admin") and new_role != admin.role:
            changes.append(f"role {admin.role} → {new_role}")
            admin.role = new_role

        if admin.role == "admin":
            new_perms = {p: (request.form.get(f"perm_{p}") == "on") for p in ALL_PERMISSIONS}
            if new_perms != admin.permissions:
                changes.append(f"permissions → {new_perms}")
                admin.permissions = new_perms

        new_pw = request.form.get("new_password", "").strip()
        if new_pw:
            if len(new_pw) < 6:
                flash("New password must be at least 6 characters.", "danger")
                return redirect(url_for("admin_accounts"))
            admin.password_hash = generate_password_hash(new_pw)
            changes.append("password changed")

        db.commit()
        if changes:
            log_action("edit_admin", f"admin:{admin.username}", " | ".join(changes))
            flash(f"Account '{admin.username}' updated.", "success")
        else:
            flash("No changes made.", "info")
    except Exception as exc:
        db.rollback()
        flash(f"Error: {exc}", "danger")
    finally:
        db.close()
    return redirect(url_for("admin_accounts"))


@app.route("/admin-accounts/<int:admin_id>/toggle", methods=["POST"])
@super_admin_required
def admin_toggle(admin_id: int):
    db = db_session()
    try:
        admin = db.query(DashboardUser).filter_by(id=admin_id).first()
        if not admin:
            return jsonify({"success": False, "error": "Not found"}), 404
        if admin.username == session.get("username"):
            return jsonify({"success": False, "error": "Cannot disable your own account"}), 400
        admin.is_active = not admin.is_active
        db.commit()
        status = "enabled" if admin.is_active else "disabled"
        log_action("toggle_admin", f"admin:{admin.username}", status)
        return jsonify({"success": True, "is_active": admin.is_active, "status": status})
    finally:
        db.close()


@app.route("/admin-accounts/<int:admin_id>/delete", methods=["POST"])
@super_admin_required
def admin_delete(admin_id: int):
    db = db_session()
    try:
        admin = db.query(DashboardUser).filter_by(id=admin_id).first()
        if not admin:
            flash("Admin not found.", "danger")
            return redirect(url_for("admin_accounts"))
        if admin.username == session.get("username"):
            flash("You cannot delete your own account.", "danger")
            return redirect(url_for("admin_accounts"))
        username = admin.username
        db.delete(admin)
        db.commit()
        log_action("delete_admin", f"admin:{username}", "account deleted")
        flash(f"Admin account '{username}' deleted.", "warning")
    except Exception as exc:
        db.rollback()
        flash(f"Error: {exc}", "danger")
    finally:
        db.close()
    return redirect(url_for("admin_accounts"))


# ─────────────────────────────────────────────────────────────
# ROUTES — Audit Log
# ─────────────────────────────────────────────────────────────
@app.route("/audit-log")
@login_required
def audit_log():
    db = db_session()
    try:
        query = db.query(AuditLog)

        # Filters
        filter_admin  = request.args.get("admin", "").strip()
        filter_action = request.args.get("action", "").strip()
        filter_days   = request.args.get("days", "7")
        try:
            days = max(1, min(int(filter_days), 365))
        except ValueError:
            days = 7

        since = datetime.utcnow() - timedelta(days=days)
        query = query.filter(AuditLog.created_at >= since)

        if filter_admin:
            query = query.filter(AuditLog.admin_username == filter_admin)
        if filter_action:
            query = query.filter(AuditLog.action == filter_action)

        logs  = query.order_by(AuditLog.created_at.desc()).limit(500).all()

        # For filter dropdowns
        all_admins  = [r[0] for r in db.query(AuditLog.admin_username).distinct().all()]
        all_actions = [r[0] for r in db.query(AuditLog.action).distinct().all()]

        return render_template(
            "audit_log.html",
            logs=logs,
            all_admins=sorted(all_admins),
            all_actions=sorted(all_actions),
            filter_admin=filter_admin,
            filter_action=filter_action,
            filter_days=days,
        )
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# API — JSON endpoints
# ─────────────────────────────────────────────────────────────
@app.route("/api/stats")
@login_required
def api_stats():
    db = db_session()
    try:
        today    = date.today()
        week_ago = today - timedelta(days=7)
        return jsonify({
            "total_users":    db.query(User).count(),
            "active_7d":      db.query(User).filter(User.last_checkin >= week_ago).count(),
            "checkins_today": db.query(CheckinLog).filter(CheckinLog.checkin_date == today).count(),
            "total_checkins": db.query(CheckinLog).count(),
            "total_points":   db.query(func.sum(User.points)).scalar() or 0,
        })
    finally:
        db.close()


@app.route("/api/users/search")
@login_required
def api_user_search():
    db = db_session()
    try:
        q    = request.args.get("q", "").strip()
        page = max(1, int(request.args.get("page", 1)))
        per  = 20
        query = db.query(User)
        if q:
            query = query.filter(User.username.ilike(f"%{q}%") | User.game_id.ilike(f"%{q}%"))
        total = query.count()
        rows  = query.order_by(User.total_checkin.desc()).offset((page-1)*per).limit(per).all()
        return jsonify({
            "total": total,
            "users": [{
                "telegram_id": u.telegram_id, "display_name": u.display_name,
                "game_id": u.game_id or "—", "streak": u.streak,
                "total_checkin": u.total_checkin, "points": u.points,
                "last_checkin": str(u.last_checkin) if u.last_checkin else "Never",
            } for u in rows],
        })
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# ROUTES — User Behavior Analytics
# ─────────────────────────────────────────────────────────────
@app.route("/analytics")
@login_required
def analytics():
    db = db_session()
    try:
        days = max(1, min(int(request.args.get("days", 30)), 365))
        since = datetime.utcnow() - timedelta(days=days)

        # ── Summary counts ────────────────────────────────────
        total_events = db.query(UserEvent).filter(UserEvent.created_at >= since).count()
        unique_users = (
            db.query(func.count(func.distinct(UserEvent.telegram_id)))
            .filter(UserEvent.created_at >= since)
            .scalar() or 0
        )

        # ── Top event types ───────────────────────────────────
        top_events = (
            db.query(UserEvent.event_type, func.count(UserEvent.id).label("cnt"))
            .filter(UserEvent.created_at >= since)
            .group_by(UserEvent.event_type)
            .order_by(func.count(UserEvent.id).desc())
            .limit(12)
            .all()
        )

        # ── Hourly distribution (0–23 UTC) ────────────────────
        hourly_raw = (
            db.query(
                func.strftime("%H", UserEvent.created_at).label("hr"),
                func.count(UserEvent.id).label("cnt"),
            )
            .filter(UserEvent.created_at >= since)
            .group_by(func.strftime("%H", UserEvent.created_at))
            .all()
        )
        hourly = [0] * 24
        for row in hourly_raw:
            try:
                hourly[int(row.hr)] = row.cnt
            except (TypeError, ValueError):
                pass

        # ── Daily active users (last `days` days) ─────────────
        daily_raw = (
            db.query(
                func.date(UserEvent.created_at).label("day"),
                func.count(func.distinct(UserEvent.telegram_id)).label("users"),
            )
            .filter(UserEvent.created_at >= since)
            .group_by(func.date(UserEvent.created_at))
            .order_by(func.date(UserEvent.created_at))
            .all()
        )
        daily_labels = [r.day for r in daily_raw]
        daily_values = [r.users for r in daily_raw]

        # ── Check-in funnel ───────────────────────────────────
        from services.event_service import (
            EVT_BTN_CHECKIN, EVT_CMD_CHECKIN,
            EVT_CHECKIN_ABANDON, EVT_CHECKIN_SUCCESS, EVT_CHECKIN_ALREADY,
        )

        def _count(evt_type):
            return (
                db.query(UserEvent)
                .filter(UserEvent.event_type == evt_type, UserEvent.created_at >= since)
                .count()
            )

        funnel = {
            "started":  _count(EVT_BTN_CHECKIN) + _count(EVT_CMD_CHECKIN),
            "abandoned": _count(EVT_CHECKIN_ABANDON),
            "already":   _count(EVT_CHECKIN_ALREADY),
            "success":   _count(EVT_CHECKIN_SUCCESS),
        }

        # ── AI Forecast ───────────────────────────────────────
        forecast = forecast_engagement(daily_values) if daily_values else {
            "predicted_tomorrow": 0, "trend": "stable", "ai_powered": False
        }

        # ── High-churn users (rule-based, top 10) ────────────
        today = date.today()
        risk_users = []
        for u in db.query(User).filter(User.total_checkin > 0).all():
            days_since = (today - u.last_checkin).days if u.last_checkin else 999
            result = predict_churn_risk({
                "streak":          u.streak,
                "total_checkin":   u.total_checkin,
                "days_since_last": days_since,
            })
            if result["risk"] in ("high", "medium"):
                risk_users.append({
                    "display_name": u.display_name,
                    "telegram_id":  u.telegram_id,
                    "streak":       u.streak,
                    "days_since":   days_since,
                    "risk":         result["risk"],
                    "score":        result["score"],
                    "reason":       result["reason"],
                    "ai_powered":   result["ai_powered"],
                })
        risk_users.sort(key=lambda x: x["score"], reverse=True)
        risk_users = risk_users[:10]

        return render_template(
            "analytics.html",
            days=days,
            total_events=total_events,
            unique_users=unique_users,
            top_events=[(r.event_type, r.cnt) for r in top_events],
            hourly=hourly,
            daily_labels=daily_labels,
            daily_values=daily_values,
            funnel=funnel,
            forecast=forecast,
            risk_users=risk_users,
        )
    finally:
        db.close()


@app.route("/api/analytics")
@login_required
def api_analytics():
    """JSON endpoint — returns the same data as /analytics for AJAX refresh."""
    db = db_session()
    try:
        days = max(1, min(int(request.args.get("days", 30)), 365))
        since = datetime.utcnow() - timedelta(days=days)

        top_events = (
            db.query(UserEvent.event_type, func.count(UserEvent.id).label("cnt"))
            .filter(UserEvent.created_at >= since)
            .group_by(UserEvent.event_type)
            .order_by(func.count(UserEvent.id).desc())
            .limit(12)
            .all()
        )

        daily_raw = (
            db.query(
                func.date(UserEvent.created_at).label("day"),
                func.count(func.distinct(UserEvent.telegram_id)).label("users"),
            )
            .filter(UserEvent.created_at >= since)
            .group_by(func.date(UserEvent.created_at))
            .order_by(func.date(UserEvent.created_at))
            .all()
        )

        daily_counts = [r.users for r in daily_raw]
        forecast = forecast_engagement(daily_counts) if daily_counts else {
            "predicted_tomorrow": 0, "trend": "stable", "ai_powered": False
        }

        return jsonify({
            "top_events": [{"type": r.event_type, "count": r.cnt} for r in top_events],
            "daily_active": [{"day": r.day, "users": r.users} for r in daily_raw],
            "forecast": forecast,
            "total_events": db.query(UserEvent).filter(UserEvent.created_at >= since).count(),
        })
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    seed_defaults()
    ensure_super_admin()
    port  = int(os.getenv("DASHBOARD_PORT", "5000"))
    host  = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    debug = os.getenv("DASHBOARD_DEBUG", "false").lower() == "true"
    logger.info("Dashboard starting on http://%s:%d", host, port)
    app.run(host=host, port=port, debug=debug)
