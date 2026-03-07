# ============================================================
# services/ai_analytics_service.py — AI Analytics (Stub)
#
# Phase 1: All functions use rule-based logic only.
# Phase 2: Plug in your AI API by following the instructions
#          inside each function — no other files need changes.
#
# ── HOW TO CONNECT AI API ───────────────────────────────────
#
#  1. Add to .env:
#       AI_API_KEY=your_key_here
#       AI_MODEL=claude-sonnet-4-6   ← or any model you prefer
#
#  2. Install provider SDK, e.g.:
#       pip install anthropic          # for Claude
#       pip install openai             # for OpenAI / GPT
#
#  3. In each function below, locate the block:
#         # ── PLUG AI HERE ──────────────────────────────────
#         # ...example code...
#         # ──────────────────────────────────────────────────
#     Replace it with your API call.
#     The function signature and return format NEVER change.
#
#  4. Set AI_API_KEY in .env → _AI_ENABLED becomes True
#     → rule-based fallback is skipped automatically.
#
# ============================================================

import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Config from environment ──────────────────────────────────
_AI_API_KEY  = os.getenv("AI_API_KEY", "")
_AI_MODEL    = os.getenv("AI_MODEL", "claude-sonnet-4-6")
_AI_ENABLED  = bool(_AI_API_KEY)

if _AI_ENABLED:
    logger.info("ai_analytics_service: AI mode enabled (model=%s)", _AI_MODEL)
else:
    logger.info("ai_analytics_service: Running in rule-based mode (no AI_API_KEY).")


# ─────────────────────────────────────────────────────────────
# 1. Churn Risk Prediction
# ─────────────────────────────────────────────────────────────
def predict_churn_risk(user_data: dict) -> dict:
    """
    Estimate how likely a user is to stop using the bot.

    Input dict keys:
        streak          int   — current streak
        total_checkin   int   — total check-in count
        days_since_last int   — days since last interaction
        task_completion float — 0.0–1.0 fraction of tasks done
        has_referrals   bool  — whether user referred anyone

    Returns:
        {
          "risk":       "low" | "medium" | "high",
          "score":      float 0.0–1.0,
          "reason":     str,
          "ai_powered": bool
        }
    """
    if _AI_ENABLED:
        # ── PLUG AI HERE ──────────────────────────────────────
        # Example with Anthropic Claude:
        #
        # import anthropic, json
        # client = anthropic.Anthropic(api_key=_AI_API_KEY)
        # prompt = (
        #     "You are a user-retention analyst for a Telegram bot. "
        #     "Given the user profile below, estimate their churn risk. "
        #     "Respond ONLY with valid JSON: "
        #     '{"risk":"low|medium|high","score":0.0-1.0,"reason":"..."}\n\n'
        #     f"User profile: {json.dumps(user_data)}"
        # )
        # msg = client.messages.create(
        #     model=_AI_MODEL,
        #     max_tokens=200,
        #     messages=[{"role": "user", "content": prompt}],
        # )
        # return {**json.loads(msg.content[0].text), "ai_powered": True}
        # ─────────────────────────────────────────────────────
        logger.warning("predict_churn_risk: AI enabled but implementation not added yet.")

    # ── Rule-based fallback (Phase 1) ─────────────────────────
    days  = user_data.get("days_since_last", 0)
    streak = user_data.get("streak", 0)
    total  = user_data.get("total_checkin", 0)

    score, reasons = 0.0, []

    if days >= 7:
        score += 0.50; reasons.append(f"Inactive {days} days")
    elif days >= 3:
        score += 0.25; reasons.append(f"Missed {days} days")

    if streak == 0 and total > 0:
        score += 0.30; reasons.append("Streak broken")

    if total <= 2:
        score += 0.20; reasons.append("New user, low engagement")

    score = min(score, 1.0)
    risk  = "high" if score >= 0.65 else "medium" if score >= 0.35 else "low"

    return {
        "risk":       risk,
        "score":      round(score, 2),
        "reason":     "; ".join(reasons) if reasons else "Active user",
        "ai_powered": False,
    }


# ─────────────────────────────────────────────────────────────
# 2. Behavior Pattern Summary
# ─────────────────────────────────────────────────────────────
def summarize_behavior(events: list[dict]) -> dict:
    """
    Summarise a single user's interaction patterns.

    Input: list of dicts — each dict from UserEvent row:
        {"event_type": str, "created_at": datetime, "meta": dict}

    Returns:
        {
          "most_used_feature": str,
          "peak_hour":         int (0–23 UTC),
          "engagement_score":  float 0.0–1.0,
          "ai_powered":        bool
        }
    """
    if _AI_ENABLED:
        # ── PLUG AI HERE ──────────────────────────────────────
        # Send events list to AI for rich natural-language summary.
        # Example:
        #
        # import anthropic, json
        # client = anthropic.Anthropic(api_key=_AI_API_KEY)
        # payload = [{"type": e["event_type"], "at": str(e["created_at"])}
        #            for e in events[:50]]
        # prompt = (
        #     "You are a UX analyst. Summarise this user's Telegram bot behavior.\n"
        #     "Respond ONLY with valid JSON matching this shape:\n"
        #     '{"most_used_feature":"...","peak_hour":0,"engagement_score":0.0}\n\n'
        #     f"Events: {json.dumps(payload)}"
        # )
        # msg = client.messages.create(
        #     model=_AI_MODEL, max_tokens=200,
        #     messages=[{"role":"user","content": prompt}],
        # )
        # return {**json.loads(msg.content[0].text), "ai_powered": True}
        # ─────────────────────────────────────────────────────
        logger.warning("summarize_behavior: AI enabled but implementation not added yet.")

    if not events:
        return {"most_used_feature": "none", "peak_hour": 0,
                "engagement_score": 0.0, "ai_powered": False}

    counts: dict[str, int] = {}
    hours:  list[int] = []
    for ev in events:
        etype = ev.get("event_type", "unknown")
        counts[etype] = counts.get(etype, 0) + 1
        ts = ev.get("created_at")
        if isinstance(ts, datetime):
            hours.append(ts.hour)

    most_used = max(counts, key=counts.get, default="none")
    peak_hour = max(set(hours), key=hours.count, default=0) if hours else 0
    score     = min(sum(counts.values()) / 100.0, 1.0)

    return {
        "most_used_feature": most_used,
        "peak_hour":         peak_hour,
        "engagement_score":  round(score, 2),
        "ai_powered":        False,
    }


# ─────────────────────────────────────────────────────────────
# 3. Engagement Forecast
# ─────────────────────────────────────────────────────────────
def forecast_engagement(daily_counts: list[int]) -> dict:
    """
    Predict tomorrow's check-in count from recent daily totals.

    Input: [oldest, ..., day-2, day-1]  (most recent last)

    Returns:
        {
          "predicted_tomorrow": int,
          "trend":              "up" | "down" | "stable",
          "ai_powered":         bool
        }
    """
    if _AI_ENABLED:
        # ── PLUG AI HERE ──────────────────────────────────────
        # Example: time-series prediction via AI
        #
        # import anthropic, json
        # client = anthropic.Anthropic(api_key=_AI_API_KEY)
        # prompt = (
        #     "You are a data scientist. Given these daily active user counts "
        #     "(most recent last), predict tomorrow's count and the trend.\n"
        #     "Respond ONLY with valid JSON: "
        #     '{"predicted_tomorrow":0,"trend":"up|down|stable"}\n\n'
        #     f"Counts: {daily_counts}"
        # )
        # msg = client.messages.create(
        #     model=_AI_MODEL, max_tokens=100,
        #     messages=[{"role":"user","content": prompt}],
        # )
        # return {**json.loads(msg.content[0].text), "ai_powered": True}
        # ─────────────────────────────────────────────────────
        logger.warning("forecast_engagement: AI enabled but implementation not added yet.")

    if len(daily_counts) < 2:
        return {"predicted_tomorrow": 0, "trend": "stable", "ai_powered": False}

    recent = daily_counts[-7:]
    avg    = sum(recent) / len(recent)
    last   = daily_counts[-1]

    trend = "up" if last > avg * 1.10 else "down" if last < avg * 0.90 else "stable"
    mult  = 1.05 if trend == "up" else 0.95 if trend == "down" else 1.0

    return {
        "predicted_tomorrow": max(round(avg * mult), 0),
        "trend":              trend,
        "ai_powered":         False,
    }
