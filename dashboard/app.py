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
from datetime import date, timedelta, datetime
from functools import wraps

import requests
import pandas as pd
from dotenv import load_dotenv
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
from models.bot_config import BotConfig, get_config, set_config, DEFAULT_CONFIGS
from models.dashboard_user import DashboardUser
from models.audit_log import AuditLog

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
# Template context processor + filters
# ─────────────────────────────────────────────────────────────
@app.context_processor
def inject_globals():
    today    = date.today()
    week_ago = today - timedelta(days=7)
    return {
        "now":            today,
        "now_7d":         week_ago,
        "app_name":       "Eluck Check-in Bot",
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
        filt     = request.args.get("filter", "all")
        today    = date.today()
        week_ago = today - timedelta(days=7)
        if filt == "active":
            query = query.filter(User.last_checkin >= week_ago)
        elif filt == "inactive":
            query = query.filter((User.last_checkin < week_ago) | User.last_checkin.is_(None))
        elif filt == "no_game_id":
            query = query.filter(User.game_id.is_(None))
        return render_template("users.html", users=query.order_by(User.total_checkin.desc()).all(), q=q, filt=filt)
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

        history = (
            db.query(CheckinLog).filter(CheckinLog.user_id == user.id)
            .order_by(CheckinLog.checkin_date.desc()).limit(30).all()
        )
        referrals = (
            db.query(Referral, User)
            .join(User, User.telegram_id == Referral.referred_id)
            .filter(Referral.referrer_id == telegram_id).all()
        )
        return render_template("user_detail.html", user=user, history=history, referrals=referrals)
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
        log_action("edit_task", f"task:{task_id}", f"{old_name!r} → {td.name!r} pts={td.reward_points}")
        flash(f"Task '{td.name}' updated.", "success")
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
            return render_template("broadcast.html", total_users=total_users, active_7d=active_7d)

        message_text = request.form.get("message", "").strip()
        target       = request.form.get("target", "all")
        if not message_text:
            flash("Message cannot be empty.", "danger")
            return redirect(url_for("broadcast"))

        week_ago = date.today() - timedelta(days=7)
        if target == "active":
            users_list = db.query(User).filter(User.last_checkin >= week_ago).all()
        elif target == "game_id":
            users_list = db.query(User).filter(User.game_id.isnot(None)).all()
        else:
            users_list = db.query(User).all()

        sent, failed = 0, 0
        for u in users_list:
            try:
                resp = requests.post(
                    f"{TELEGRAM_API}/sendMessage",
                    json={"chat_id": u.telegram_id, "text": f"📢 <b>Announcement</b>\n\n{message_text}", "parse_mode": "HTML"},
                    timeout=5,
                )
                sent += 1 if resp.ok else 0
                failed += 0 if resp.ok else 1
            except Exception:
                failed += 1

        log_action("broadcast", f"target:{target}", f"sent={sent} failed={failed} msg={message_text[:80]!r}")
        flash(f"Broadcast complete! Sent: {sent:,} | Failed: {failed:,}", "success")
        return redirect(url_for("broadcast"))
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
