# ============================================================
# dashboard/app.py — Admin Dashboard (Flask)
#
# Features:
#   - Overview stats & Chart.js charts
#   - User management (view, edit, add points, reset streak)
#   - Task management (CRUD task definitions in DB)
#   - Reward configuration (edit points values via DB)
#   - Broadcast to all/active users via Telegram Bot API
#   - Export CSV
#
# Run:  python dashboard/app.py
# Auth: DASHBOARD_USERNAME / DASHBOARD_PASSWORD from .env
# ============================================================

import sys, os

# Allow importing from parent project directory
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
from sqlalchemy import func, text

import config
from database import init_db
from models.user import User
from models.checkin import CheckinLog
from models.referral import Referral
from models.task_definition import TaskDefinition
from models.bot_config import BotConfig, get_config, set_config, DEFAULT_CONFIGS

load_dotenv()

# ─────────────────────────────────────────────────────────────
# Flask app setup
# ─────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("DASHBOARD_SECRET_KEY", "change-me-in-production-secret-key")

DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME", "admin")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "admin123")
TELEGRAM_API = f"https://api.telegram.org/bot{config.BOT_TOKEN}"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Template context processor + filters
# ─────────────────────────────────────────────────────────────
@app.context_processor
def inject_globals():
    """Inject common variables into every template context."""
    today    = date.today()
    week_ago = today - timedelta(days=7)
    return {
        "now":      today,
        "now_7d":   week_ago,
        "app_name": "Eluck Check-in Bot",
    }


@app.template_filter("format_number")
def format_number(value):
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return value


@app.teardown_appcontext
def remove_session(_exc=None):
    """Remove the scoped session at end of each request — prevents thread leaks."""
    _SessionLocal.remove()

# ─────────────────────────────────────────────────────────────
# Database — dedicated thread-safe engine for Flask
# (separate from bot's StaticPool engine)
# ─────────────────────────────────────────────────────────────
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session
from models.user import User          # noqa — triggers ORM registration
from models.checkin import CheckinLog  # noqa
from models.referral import Referral   # noqa
from models.task import UserTask        # noqa
from models.task_definition import TaskDefinition  # noqa
from models.bot_config import BotConfig             # noqa
from database import Base

# Build a fresh engine without StaticPool for multithreaded Flask
_db_url = config.DATABASE_URL
if _db_url.startswith("sqlite"):
    # NullPool: each thread/request gets its own connection — no cross-thread state
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

Base.metadata.create_all(bind=_engine)   # ensure new tables exist
# scoped_session: each thread receives its own session (thread-local registry)
_SessionLocal = scoped_session(sessionmaker(bind=_engine, autocommit=False, autoflush=False))


def get_db():
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


def db_session():
    return _SessionLocal()


# ─────────────────────────────────────────────────────────────
# Seed: populate default configs & tasks on first run
# ─────────────────────────────────────────────────────────────
def seed_defaults():
    db = db_session()
    try:
        # Seed BotConfig defaults
        for key, (value, desc) in DEFAULT_CONFIGS.items():
            existing = db.query(BotConfig).filter(BotConfig.key == key).first()
            if not existing:
                db.add(BotConfig(key=key, value=value, description=desc))

        # Seed TaskDefinitions from config.TASKS if table is empty
        if db.query(TaskDefinition).count() == 0:
            for t in config.TASKS:
                td = TaskDefinition(
                    task_key=t["id"],
                    name=t["name"],
                    description=t["description"],
                    reward_points=t["reward"],
                    task_type=t["type"],
                    url=t.get("url"),
                    required_count=t.get("required_count", 1),
                    is_active=True,
                )
                db.add(td)

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("seed_defaults error: %s", exc)
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# Auth guard
# ─────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────────
# Helper — read reward config from DB (int)
# ─────────────────────────────────────────────────────────────
def get_reward_config(db) -> dict:
    return {
        "POINTS_PER_CHECKIN":  int(get_config(db, "POINTS_PER_CHECKIN",  config.POINTS_PER_CHECKIN)),
        "REFERRAL_REWARD":     int(get_config(db, "REFERRAL_REWARD",     config.REFERRAL_REWARD)),
        "STREAK_7_REWARD":     int(get_config(db, "STREAK_7_REWARD",     config.STREAK_REWARDS.get(7,   100))),
        "STREAK_30_REWARD":    int(get_config(db, "STREAK_30_REWARD",    config.STREAK_REWARDS.get(30,  500))),
        "STREAK_100_REWARD":   int(get_config(db, "STREAK_100_REWARD",   config.STREAK_REWARDS.get(100, 2000))),
        "STREAK_365_REWARD":   int(get_config(db, "STREAK_365_REWARD",   config.STREAK_REWARDS.get(365, 10000))),
        "LEADERBOARD_SIZE":    int(get_config(db, "LEADERBOARD_SIZE",    config.LEADERBOARD_SIZE)),
        "STREAK_REMINDER_HOUR":int(get_config(db, "STREAK_REMINDER_HOUR", 18)),
    }


# ─────────────────────────────────────────────────────────────
# ROUTES — Auth
# ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == DASHBOARD_USERNAME and password == DASHBOARD_PASSWORD:
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("dashboard"))
        error = "Invalid credentials"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
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
        today = date.today()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        # ── Stat cards ────────────────────────────────────────
        total_users     = db.query(User).count()
        users_with_game = db.query(User).filter(User.game_id.isnot(None)).count()
        checkins_today  = db.query(CheckinLog).filter(CheckinLog.checkin_date == today).count()
        active_7d       = db.query(User).filter(User.last_checkin >= week_ago).count()
        total_checkins  = db.query(CheckinLog).count()
        total_points    = db.query(func.sum(User.points)).scalar() or 0

        # ── Top 5 leaderboard ─────────────────────────────────
        top5 = (
            db.query(User)
            .filter(User.game_id.isnot(None))
            .order_by(User.total_checkin.desc())
            .limit(5)
            .all()
        )

        # ── Recent check-ins (raw SQL bypasses Cython str_to_date) ──
        recent_sql = text("""
            SELECT u.username, u.first_name, u.telegram_id, u.game_id,
                   c.checkin_date, c.streak_at_checkin, c.points_earned
            FROM checkin_logs c
            JOIN users u ON u.id = c.user_id
            ORDER BY c.created_at DESC
            LIMIT 15
        """)
        recent_rows = db.execute(recent_sql).fetchall()
        recent_list = []
        for row in recent_rows:
            if row[0]:
                dname = f"@{row[0]}"
            elif row[1]:
                dname = row[1]
            else:
                dname = f"User{row[2]}"
            recent_list.append({
                "username": dname,
                "game_id":  row[3] or "—",
                "date":     str(row[4]),
                "streak":   row[5],
                "points":   row[6],
            })

        # ── Chart data: daily check-ins last 30 days (raw SQL) ──────────
        rows_sql = text("""
            SELECT checkin_date, COUNT(*) AS cnt
            FROM checkin_logs
            WHERE checkin_date >= :month_ago
            GROUP BY checkin_date
            ORDER BY checkin_date
        """)
        rows = db.execute(rows_sql, {"month_ago": str(month_ago)}).fetchall()
        chart_dates  = [str(r[0]) for r in rows]
        chart_counts = [r[1]      for r in rows]

        # ── New users per day chart (raw SQL) ──
        nu_sql = text("""
            SELECT DATE(register_date) AS reg_date, COUNT(*) AS cnt
            FROM users
            WHERE register_date >= :month_ago
            GROUP BY DATE(register_date)
            ORDER BY DATE(register_date)
        """)
        new_user_rows = db.execute(nu_sql, {"month_ago": str(month_ago)}).fetchall()
        nu_dates  = [str(r[0]) for r in new_user_rows]
        nu_counts = [r[1]      for r in new_user_rows]

        return render_template(
            "index.html",
            total_users=total_users,
            users_with_game=users_with_game,
            checkins_today=checkins_today,
            active_7d=active_7d,
            total_checkins=total_checkins,
            total_points=f"{total_points:,}",
            top5=top5,
            recent=recent_list,
            chart_dates=json.dumps(chart_dates),
            chart_counts=json.dumps(chart_counts),
            nu_dates=json.dumps(nu_dates),
            nu_counts=json.dumps(nu_counts),
        )
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# ROUTES — User Management
# ─────────────────────────────────────────────────────────────
@app.route("/users")
@login_required
def users():
    db = db_session()
    try:
        query = db.query(User)

        # Optional search
        q = request.args.get("q", "").strip()
        if q:
            query = query.filter(
                (User.username.ilike(f"%{q}%")) |
                (User.game_id.ilike(f"%{q}%")) |
                (User.first_name.ilike(f"%{q}%"))
            )

        # Optional filter
        filt = request.args.get("filter", "all")
        today = date.today()
        week_ago = today - timedelta(days=7)
        if filt == "active":
            query = query.filter(User.last_checkin >= week_ago)
        elif filt == "inactive":
            query = query.filter(
                (User.last_checkin < week_ago) | (User.last_checkin.is_(None))
            )
        elif filt == "no_game_id":
            query = query.filter(User.game_id.is_(None))

        all_users = query.order_by(User.total_checkin.desc()).all()
        return render_template("users.html", users=all_users, q=q, filt=filt)
    finally:
        db.close()


@app.route("/users/<int:telegram_id>", methods=["GET", "POST"])
@login_required
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
                new_game_id = request.form.get("game_id", "").strip() or None
                user.game_id = new_game_id
                db.commit()
                flash("Game ID updated.", "success")

            elif action == "add_points":
                try:
                    delta = int(request.form.get("delta", 0))
                    user.points = max(0, user.points + delta)
                    db.commit()
                    sign = "+" if delta >= 0 else ""
                    flash(f"Points adjusted {sign}{delta}. New total: {user.points:,}", "success")
                except ValueError:
                    flash("Invalid point value.", "danger")

            elif action == "set_streak":
                try:
                    new_streak = max(0, int(request.form.get("streak", 0)))
                    user.streak = new_streak
                    db.commit()
                    flash(f"Streak set to {new_streak}.", "success")
                except ValueError:
                    flash("Invalid streak value.", "danger")

            elif action == "reset_streak":
                user.streak = 0
                db.commit()
                flash("Streak reset to 0.", "warning")

            elif action == "ban_user":
                user.game_id = None
                user.streak = 0
                db.commit()
                flash("User banned (game ID cleared, streak reset).", "warning")

            return redirect(url_for("user_detail", telegram_id=telegram_id))

        # Check-in history (last 30)
        history = (
            db.query(CheckinLog)
            .filter(CheckinLog.user_id == user.id)
            .order_by(CheckinLog.checkin_date.desc())
            .limit(30)
            .all()
        )

        # Referrals made
        referrals = (
            db.query(Referral, User)
            .join(User, User.telegram_id == Referral.referred_id)
            .filter(Referral.referrer_id == telegram_id)
            .all()
        )

        return render_template(
            "user_detail.html",
            user=user,
            history=history,
            referrals=referrals,
        )
    finally:
        db.close()


@app.route("/users/export")
@login_required
def export_users():
    db = db_session()
    try:
        users_list = db.query(User).order_by(User.total_checkin.desc()).all()
        data = [
            {
                "telegram_id":  u.telegram_id,
                "username":     u.username or "",
                "first_name":   u.first_name or "",
                "game_id":      u.game_id or "",
                "register_date":str(u.register_date),
                "last_checkin": str(u.last_checkin),
                "streak":       u.streak,
                "total_checkin":u.total_checkin,
                "points":       u.points,
                "referrals":    u.referral_count,
                "referrer_id":  u.referrer_id or "",
            }
            for u in users_list
        ]
        df = pd.DataFrame(data)
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        return Response(
            buf.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=users_{date.today()}.csv"},
        )
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# ROUTES — Task Definitions (CRUD)
# ─────────────────────────────────────────────────────────────
@app.route("/tasks")
@login_required
def tasks():
    db = db_session()
    try:
        task_list = db.query(TaskDefinition).order_by(TaskDefinition.id).all()
        return render_template("tasks.html", tasks=task_list)
    finally:
        db.close()


@app.route("/tasks/add", methods=["POST"])
@login_required
def task_add():
    db = db_session()
    try:
        key = request.form.get("task_key", "").strip().lower().replace(" ", "_")
        if not key:
            flash("Task key is required.", "danger")
            return redirect(url_for("tasks"))

        # Check uniqueness
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
        flash(f"Task '{td.name}' added.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Error: {exc}", "danger")
    finally:
        db.close()
    return redirect(url_for("tasks"))


@app.route("/tasks/<int:task_id>/edit", methods=["POST"])
@login_required
def task_edit(task_id: int):
    db = db_session()
    try:
        td = db.query(TaskDefinition).filter(TaskDefinition.id == task_id).first()
        if not td:
            flash("Task not found.", "danger")
            return redirect(url_for("tasks"))

        td.name          = request.form.get("name", td.name).strip()
        td.description   = request.form.get("description", td.description).strip()
        td.reward_points = int(request.form.get("reward_points", td.reward_points))
        td.task_type     = request.form.get("task_type", td.task_type)
        td.url           = request.form.get("url", "").strip() or None
        td.required_count= int(request.form.get("required_count", td.required_count))
        td.is_active     = request.form.get("is_active") == "on"
        td.updated_at    = datetime.utcnow()

        db.commit()
        flash(f"Task '{td.name}' updated.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Error: {exc}", "danger")
    finally:
        db.close()
    return redirect(url_for("tasks"))


@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def task_delete(task_id: int):
    db = db_session()
    try:
        td = db.query(TaskDefinition).filter(TaskDefinition.id == task_id).first()
        if td:
            name = td.name
            db.delete(td)
            db.commit()
            flash(f"Task '{name}' deleted.", "warning")
    except Exception as exc:
        db.rollback()
        flash(f"Error: {exc}", "danger")
    finally:
        db.close()
    return redirect(url_for("tasks"))


@app.route("/tasks/<int:task_id>/toggle", methods=["POST"])
@login_required
def task_toggle(task_id: int):
    db = db_session()
    try:
        td = db.query(TaskDefinition).filter(TaskDefinition.id == task_id).first()
        if td:
            td.is_active = not td.is_active
            db.commit()
            status = "activated" if td.is_active else "deactivated"
            return jsonify({"success": True, "is_active": td.is_active, "status": status})
    finally:
        db.close()
    return jsonify({"success": False}), 404


# ─────────────────────────────────────────────────────────────
# ROUTES — Reward Configuration
# ─────────────────────────────────────────────────────────────
@app.route("/rewards", methods=["GET", "POST"])
@login_required
def rewards():
    db = db_session()
    try:
        if request.method == "POST":
            keys_to_save = [
                "POINTS_PER_CHECKIN", "REFERRAL_REWARD",
                "STREAK_7_REWARD", "STREAK_30_REWARD",
                "STREAK_100_REWARD", "STREAK_365_REWARD",
                "LEADERBOARD_SIZE", "STREAK_REMINDER_HOUR",
            ]
            for key in keys_to_save:
                val = request.form.get(key, "").strip()
                if val.isdigit():
                    set_config(db, key, int(val), DEFAULT_CONFIGS.get(key, ("", ""))[1])
            db.commit()
            flash("Reward configuration saved successfully!", "success")
            return redirect(url_for("rewards"))

        cfg = get_reward_config(db)
        return render_template("rewards.html", cfg=cfg)
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
@login_required
def broadcast():
    db = db_session()
    try:
        if request.method == "GET":
            total_users = db.query(User).count()
            active_7d   = db.query(User).filter(
                User.last_checkin >= date.today() - timedelta(days=7)
            ).count()
            return render_template(
                "broadcast.html",
                total_users=total_users,
                active_7d=active_7d,
            )

        message_text = request.form.get("message", "").strip()
        target       = request.form.get("target", "all")

        if not message_text:
            flash("Message cannot be empty.", "danger")
            return redirect(url_for("broadcast"))

        # Determine recipients
        today    = date.today()
        week_ago = today - timedelta(days=7)
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
                    json={
                        "chat_id":    u.telegram_id,
                        "text":       f"📢 <b>Announcement</b>\n\n{message_text}",
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

        flash(f"Broadcast complete! Sent: {sent:,} | Failed: {failed:,}", "success")
        return redirect(url_for("broadcast"))
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# API — JSON endpoints for AJAX / charts
# ─────────────────────────────────────────────────────────────
@app.route("/api/stats")
@login_required
def api_stats():
    db = db_session()
    try:
        today    = date.today()
        week_ago = today - timedelta(days=7)
        return jsonify({
            "total_users":     db.query(User).count(),
            "active_7d":       db.query(User).filter(User.last_checkin >= week_ago).count(),
            "checkins_today":  db.query(CheckinLog).filter(CheckinLog.checkin_date == today).count(),
            "total_checkins":  db.query(CheckinLog).count(),
            "total_points":    db.query(func.sum(User.points)).scalar() or 0,
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
            query = query.filter(
                (User.username.ilike(f"%{q}%")) |
                (User.game_id.ilike(f"%{q}%"))
            )
        total = query.count()
        rows  = query.order_by(User.total_checkin.desc()).offset((page-1)*per).limit(per).all()
        return jsonify({
            "total": total,
            "users": [
                {
                    "telegram_id":  u.telegram_id,
                    "display_name": u.display_name,
                    "game_id":      u.game_id or "—",
                    "streak":       u.streak,
                    "total_checkin":u.total_checkin,
                    "points":       u.points,
                    "last_checkin": str(u.last_checkin) if u.last_checkin else "Never",
                }
                for u in rows
            ],
        })
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    seed_defaults()
    port = int(os.getenv("DASHBOARD_PORT", "5000"))
    host = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    debug = os.getenv("DASHBOARD_DEBUG", "false").lower() == "true"
    logger.info("Dashboard starting on http://%s:%d", host, port)
    app.run(host=host, port=port, debug=debug)
