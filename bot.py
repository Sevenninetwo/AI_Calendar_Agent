import os
import json
import re
import logging
from datetime import datetime, timedelta
import pytz

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    ConversationHandler, MessageHandler, filters,
    CallbackQueryHandler,
)
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import anthropic

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SCOPES = ["https://www.googleapis.com/auth/calendar"]
SGT     = pytz.timezone("Asia/Singapore")
TZ_NAME = "Asia/Singapore"

# ConversationHandler states for /add
TITLE, DATE, TIME = range(3)

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

CONFIRM_KB = InlineKeyboardMarkup([[
    InlineKeyboardButton("✅ Yes, go ahead", callback_data="confirm_yes"),
    InlineKeyboardButton("❌ Cancel",        callback_data="confirm_no"),
]])


# ── Google Calendar ──────────────────────────────────────────────────────────

def get_calendar_service():
    token_path = os.path.join(os.path.dirname(__file__), "token.json")
    creds_path = os.path.join(os.path.dirname(__file__), "credentials.json")
    creds = None

    token_json_env = os.getenv("GOOGLE_TOKEN_JSON")
    if token_json_env:
        creds = Credentials.from_authorized_user_info(json.loads(token_json_env), SCOPES)
    elif os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds_json_env = os.getenv("GOOGLE_CREDENTIALS_JSON")
            if creds_json_env:
                flow = InstalledAppFlow.from_client_config(json.loads(creds_json_env), SCOPES)
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        if not token_json_env:
            with open(token_path, "w") as f:
                f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def fetch_events(days_ahead: int) -> list:
    service = get_calendar_service()
    now_sgt = datetime.now(tz=SGT)
    t_min   = now_sgt.replace(hour=0, minute=0, second=0, microsecond=0)
    t_max   = t_min + timedelta(days=days_ahead)
    result = service.events().list(
        calendarId="primary",
        timeMin=t_min.isoformat(),
        timeMax=t_max.isoformat(),
        maxResults=50,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    return result.get("items", [])


def fetch_events_for_date(date_str: str) -> list:
    """Fetch events for a single calendar day (midnight–midnight SGT)."""
    service = get_calendar_service()
    t_min = SGT.localize(datetime.strptime(date_str, "%Y-%m-%d"))
    t_max = t_min + timedelta(days=1)
    result = service.events().list(
        calendarId="primary",
        timeMin=t_min.isoformat(),
        timeMax=t_max.isoformat(),
        maxResults=50,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    return result.get("items", [])


def create_event(title: str, date: str, raw_time: str) -> None:
    service = get_calendar_service()
    if raw_time == "all day":
        body = {"summary": title, "start": {"date": date}, "end": {"date": date}}
    else:
        t = _parse_time(raw_time)
        h, m = map(int, t.split(":"))
        body = {
            "summary": title,
            "start": {"dateTime": f"{date}T{h:02d}:{m:02d}:00", "timeZone": TZ_NAME},
            "end":   {"dateTime": f"{date}T{h+1:02d}:{m:02d}:00" if h < 23 else f"{date}T23:59:00", "timeZone": TZ_NAME},
        }
    service.events().insert(calendarId="primary", body=body).execute()


def patch_event(event_id: str, patch_body: dict) -> None:
    service = get_calendar_service()
    service.events().patch(
        calendarId="primary", eventId=event_id, body=patch_body
    ).execute()


def delete_event_by_id(event_id: str) -> None:
    service = get_calendar_service()
    service.events().delete(calendarId="primary", eventId=event_id).execute()


def build_patch_body(event: dict, changes: dict) -> dict:
    """Translate a changes dict into a Calendar API patch body."""
    body = {}
    if changes.get("new_title"):
        body["summary"] = changes["new_title"]
    if changes.get("new_description"):
        body["description"] = changes["new_description"]

    new_date = changes.get("new_date")
    new_time = changes.get("new_time")

    if new_date or new_time:
        orig_start = event["start"]
        orig_end   = event["end"]
        is_timed   = "dateTime" in orig_start

        if not is_timed:
            # All-day: just shift the date
            d = new_date or orig_start.get("date", "")
            body["start"] = {"date": d}
            body["end"]   = {"date": d}
        else:
            orig_date       = orig_start["dateTime"][:10]
            orig_start_time = orig_start["dateTime"][11:16]  # HH:MM
            orig_end_time   = orig_end["dateTime"][11:16]
            tz              = orig_start.get("timeZone", TZ_NAME)
            target_date     = new_date or orig_date

            if new_time:
                # Preserve original duration
                sh, sm = map(int, orig_start_time.split(":"))
                eh, em = map(int, orig_end_time.split(":"))
                duration_mins = (eh * 60 + em) - (sh * 60 + sm)
                nh, nm = map(int, new_time.split(":"))
                end_total = nh * 60 + nm + duration_mins
                end_h, end_m = end_total // 60, end_total % 60
                if end_h >= 24:
                    end_h, end_m = 23, 59
                body["start"] = {"dateTime": f"{target_date}T{nh:02d}:{nm:02d}:00", "timeZone": tz}
                body["end"]   = {"dateTime": f"{target_date}T{end_h:02d}:{end_m:02d}:00", "timeZone": tz}
            else:
                # Date-only shift, keep same times
                body["start"] = {"dateTime": f"{target_date}T{orig_start_time}:00", "timeZone": tz}
                body["end"]   = {"dateTime": f"{target_date}T{orig_end_time}:00",   "timeZone": tz}
    return body


# ── Claude ───────────────────────────────────────────────────────────────────

def ask_claude(prompt: str, max_tokens: int = 300) -> str:
    msg = anthropic_client.messages.create(
        model="claude-opus-4-5",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return {}


def classify_intent(text: str) -> dict:
    today = datetime.now(tz=SGT)
    raw = ask_claude(
        f"Today: {today.strftime('%Y-%m-%d')} ({today.strftime('%A')}).\n"
        f"Message: \"{text}\"\n\n"
        "Return JSON only, no markdown. Fields:\n"
        "  intent: today|week|add|delete|edit|check_free|unknown\n"
        "  title: str|null          — event title (add/edit)\n"
        "  date: YYYY-MM-DD|null    — resolved event date\n"
        "  time: HH:MM|'all day'|null\n"
        "  search_term: str|null    — which event to find (delete/edit)\n"
        "  new_title: str|null      — replacement title (edit)\n"
        "  new_date: YYYY-MM-DD|null — replacement date (edit)\n"
        "  new_time: HH:MM|null     — replacement time (edit)",
        max_tokens=160,
    )
    return _parse_json(raw)


def _to_sgt_str(start: dict) -> str:
    """Return a human-readable SGT time string from a Calendar event start dict."""
    dt_str = start.get("dateTime")
    if not dt_str:
        return start.get("date", "")
    # Strip fractional seconds (Python 3.9 fromisoformat doesn't handle them)
    dt_str = re.sub(r'\.\d+', '', dt_str)
    dt_str = dt_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(SGT).strftime("%Y-%m-%d %H:%M")


def format_events(events: list, period: str) -> str:
    if not events:
        return f"Nothing on your calendar {period}."
    lines = [
        f"- {e.get('summary','Untitled')} @ {_to_sgt_str(e['start'])}"
        for e in events
    ]
    return ask_claude(
        f"Calendar events {period}:\n" + "\n".join(lines) +
        "\n\nFormat as a short Telegram message. Light emoji OK. No filler phrases. No bullet overload.",
        max_tokens=280,
    )


def parse_date(raw: str) -> str:
    today = datetime.now(tz=SGT).strftime("%Y-%m-%d")
    result = ask_claude(
        f"Today: {today}. Convert '{raw}' to YYYY-MM-DD. Reply ONLY the date.",
        max_tokens=15,
    )
    datetime.strptime(result, "%Y-%m-%d")  # validate
    return result


def _parse_time(raw: str) -> str:
    result = ask_claude(
        f"Convert '{raw}' to HH:MM (24h). Reply ONLY HH:MM.",
        max_tokens=10,
    )
    datetime.strptime(result, "%H:%M")  # validate
    return result


def parse_edit_instruction(text: str, event: dict) -> dict:
    summary = event.get("summary", "")
    start   = event["start"].get("dateTime", event["start"].get("date", ""))[:16]
    today   = datetime.now(tz=SGT).strftime("%Y-%m-%d")
    raw = ask_claude(
        f"Today: {today}. Editing event '{summary}' at {start}.\n"
        f"User request: '{text}'\n"
        "Return JSON only. Omit unchanged fields:\n"
        "  new_title: str|null\n"
        "  new_date: YYYY-MM-DD|null\n"
        "  new_time: HH:MM|null\n"
        "  new_description: str|null",
        max_tokens=100,
    )
    return _parse_json(raw)


# ── Confirmation helper ───────────────────────────────────────────────────────

def _describe_edit(event: dict, changes: dict) -> str:
    title = event.get("summary", "Untitled")
    parts = []
    if changes.get("new_title"):       parts.append(f"rename → '{changes['new_title']}'")
    if changes.get("new_date"):        parts.append(f"date → {changes['new_date']}")
    if changes.get("new_time"):        parts.append(f"time → {changes['new_time']}")
    if changes.get("new_description"): parts.append(f"description → '{changes['new_description']}'")
    return f"Edit *{title}*: {', '.join(parts) or 'no changes'}. Go ahead?"


def _event_label(event: dict) -> str:
    title = event.get("summary", "Untitled")
    return f"{title}  ({_to_sgt_str(event['start'])})"


# ── Menu helpers ──────────────────────────────────────────────────────────────

async def _show_delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, events: list):
    context.user_data["delete_events"] = events
    kb = [[InlineKeyboardButton(_event_label(e), callback_data=f"del_{i}")] for i, e in enumerate(events[:10])]
    kb.append([InlineKeyboardButton("❌ Cancel", callback_data="del_cancel")])
    await update.message.reply_text("Which event to delete?", reply_markup=InlineKeyboardMarkup(kb))


async def _show_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, events: list):
    context.user_data["edit_events"] = events
    kb = [[InlineKeyboardButton(_event_label(e), callback_data=f"editpick_{i}")] for i, e in enumerate(events[:10])]
    kb.append([InlineKeyboardButton("❌ Cancel", callback_data="editpick_cancel")])
    await update.message.reply_text("Which event to edit?", reply_markup=InlineKeyboardMarkup(kb))


def _filter_events(events: list, search: str, hint_date: str, hint_time: str = "") -> list:
    search = search.lower()
    filtered = [
        e for e in events
        if (not hint_date or hint_date in e["start"].get("dateTime", e["start"].get("date", "")))
        and (not search or any(w in e.get("summary", "").lower() for w in search.split()))
    ]
    if hint_time and not filtered:
        filtered = [e for e in events if hint_time[:5] in e["start"].get("dateTime", "")]
    return filtered or events


# ── Command handlers ──────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Calendar Bot. Talk naturally or use commands:\n"
        "/today · /week · /add · /edit · /delete"
    )


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        today_str = datetime.now(tz=SGT).strftime("%Y-%m-%d")
        await update.message.reply_text(format_events(fetch_events_for_date(today_str), "today"))
    except Exception as e:
        logger.error("today: %s", e)
        await update.message.reply_text("Couldn't fetch today's events.")


async def week_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(format_events(fetch_events(7), "this week"))
    except Exception as e:
        logger.error("week: %s", e)
        await update.message.reply_text("Couldn't fetch this week's events.")


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        events = fetch_events(30)
        if not events:
            await update.message.reply_text("No upcoming events.")
            return
        await _show_delete_menu(update, context, events)
    except Exception as e:
        logger.error("delete cmd: %s", e)
        await update.message.reply_text("Couldn't fetch events.")


async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        events = fetch_events(30)
        if not events:
            await update.message.reply_text("No upcoming events.")
            return
        await _show_edit_menu(update, context, events)
    except Exception as e:
        logger.error("edit cmd: %s", e)
        await update.message.reply_text("Couldn't fetch events.")


# ── /add ConversationHandler ──────────────────────────────────────────────────

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Event title?")
    return TITLE


async def add_receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text.strip()
    await update.message.reply_text("Date? (e.g. tomorrow, next Friday, 2025-06-20)")
    return DATE


async def add_receive_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["date"] = parse_date(update.message.text.strip())
        await update.message.reply_text("Time? (e.g. 2pm, 14:30, or 'all day')")
        return TIME
    except Exception:
        await update.message.reply_text("Couldn't parse that date. Try YYYY-MM-DD.")
        return DATE


async def add_receive_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title    = context.user_data.pop("title")
    date     = context.user_data.pop("date")
    raw_time = update.message.text.strip().lower()
    context.user_data["pending_action"] = {"type": "add", "title": title, "date": date, "time": raw_time}
    await update.message.reply_text(
        f"Add *{title}* on {date} at {raw_time}. Go ahead?",
        reply_markup=CONFIRM_KB,
    )
    return ConversationHandler.END


async def add_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


# ── Inline keyboard callbacks ─────────────────────────────────────────────────

async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = context.user_data.pop("pending_action", None)

    if query.data == "confirm_no" or not action:
        await query.edit_message_text("Cancelled.")
        return

    try:
        t = action["type"]
        if t == "add":
            create_event(action["title"], action["date"], action["time"])
            await query.edit_message_text(f"✅ '{action['title']}' added.")
        elif t == "delete":
            delete_event_by_id(action["event_id"])
            await query.edit_message_text(f"🗑️ '{action['event_title']}' deleted.")
        elif t == "edit":
            patch_event(action["event_id"], action["patch"])
            await query.edit_message_text(f"✏️ '{action['event_title']}' updated.")
    except Exception as e:
        logger.error("confirm execute: %s", e)
        await query.edit_message_text("Something went wrong. Please try again.")


async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "del_cancel":
        context.user_data.pop("delete_events", None)
        await query.edit_message_text("Cancelled.")
        return

    try:
        idx    = int(query.data.split("_", 1)[1])
        events = context.user_data.pop("delete_events", [])
        event  = events[idx]
        title  = event.get("summary", "Untitled")
        start  = _to_sgt_str(event["start"])
        context.user_data["pending_action"] = {
            "type": "delete", "event_id": event["id"], "event_title": title,
        }
        await query.edit_message_text(
            f"Delete *{title}* ({start}). Go ahead?", reply_markup=CONFIRM_KB,
        )
    except Exception as e:
        logger.error("delete_callback: %s", e)
        await query.edit_message_text("Couldn't process that.")


async def edit_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "editpick_cancel":
        context.user_data.pop("edit_events", None)
        context.user_data.pop("edit_new_values", None)
        await query.edit_message_text("Cancelled.")
        return

    try:
        idx    = int(query.data.split("_", 1)[1])
        events = context.user_data.pop("edit_events", [])
        event  = events[idx]

        new_values = context.user_data.pop("edit_new_values", None)

        if new_values and any(v for v in new_values.values() if v):
            patch = build_patch_body(event, new_values)
            if not patch:
                await query.edit_message_text("Nothing to change.")
                return
            context.user_data["pending_action"] = {
                "type": "edit", "event_id": event["id"],
                "event_title": event.get("summary", "Untitled"), "patch": patch,
            }
            await query.edit_message_text(_describe_edit(event, new_values), reply_markup=CONFIRM_KB)
        else:
            context.user_data["edit_event"] = event
            title = event.get("summary", "Untitled")
            await query.edit_message_text(
                f"Editing *{title}*. What would you like to change?\n"
                "(e.g. 'rename to X', 'move to 4pm', 'reschedule to Monday')"
            )
    except Exception as e:
        logger.error("edit_pick_callback: %s", e)
        await query.edit_message_text("Couldn't process that.")


# ── Natural language handler ──────────────────────────────────────────────────

async def handle_natural_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # — State 1: user typed what to change after picking an event to edit —
    edit_event = context.user_data.get("edit_event")
    if edit_event:
        try:
            changes = parse_edit_instruction(text, edit_event)
            if not changes or not any(v for v in changes.values() if v):
                await update.message.reply_text(
                    "Didn't catch that. Try 'rename to X', 'move to 4pm', or 'reschedule to Monday'."
                )
                return
            patch = build_patch_body(edit_event, changes)
            if not patch:
                await update.message.reply_text("Nothing to change there. Try again.")
                return
            context.user_data.pop("edit_event")
            context.user_data["pending_action"] = {
                "type": "edit", "event_id": edit_event["id"],
                "event_title": edit_event.get("summary", "Untitled"), "patch": patch,
            }
            await update.message.reply_text(_describe_edit(edit_event, changes), reply_markup=CONFIRM_KB)
        except Exception as e:
            logger.error("NL edit instruction: %s", e)
            await update.message.reply_text("Couldn't parse that. Try again.")
        return

    # — State 2: collecting missing fields for NL add —
    pending = context.user_data.get("nl_pending")
    if pending:
        missing = pending.get("missing")
        if missing == "title":
            pending["title"] = text
            pending.pop("missing")
        elif missing == "date":
            try:
                pending["date"] = parse_date(text)
                pending.pop("missing")
            except Exception:
                await update.message.reply_text("Couldn't parse that date. Try YYYY-MM-DD.")
                return
        elif missing == "time":
            pending["time"] = text
            pending.pop("missing")

        # Ask for the next missing field
        if not pending.get("title"):
            pending["missing"] = "title"
            await update.message.reply_text("What should I call this event?")
            return
        if not pending.get("date"):
            pending["missing"] = "date"
            await update.message.reply_text("What date?")
            return
        if not pending.get("time"):
            pending["missing"] = "time"
            await update.message.reply_text("What time? (or 'all day')")
            return

        # All fields collected — show confirmation
        title, date, time_val = pending["title"], pending["date"], pending["time"]
        context.user_data.pop("nl_pending")
        context.user_data["pending_action"] = {"type": "add", "title": title, "date": date, "time": time_val}
        await update.message.reply_text(
            f"Add *{title}* on {date} at {time_val}. Go ahead?", reply_markup=CONFIRM_KB,
        )
        return

    # — State 3: fresh message — classify intent —
    try:
        d = classify_intent(text)
    except Exception as e:
        logger.error("classify_intent: %s", e)
        await update.message.reply_text("Didn't understand that. Try /today, /week, /add, /edit, or /delete.")
        return

    intent = d.get("intent", "unknown")
    logger.info("NL intent=%s data=%s", intent, d)

    # READ — no confirmation needed
    if intent == "today":
        try:
            today_str = datetime.now(tz=SGT).strftime("%Y-%m-%d")
            resolved_date = d.get("date") or today_str
            if resolved_date != today_str:
                label = f"on {resolved_date}"
                await update.message.reply_text(format_events(fetch_events_for_date(resolved_date), label))
            else:
                await update.message.reply_text(format_events(fetch_events_for_date(today_str), "today"))
        except Exception as e:
            logger.error("NL today: %s", e)
            await update.message.reply_text("Couldn't fetch today's events.")

    elif intent == "week":
        try:
            await update.message.reply_text(format_events(fetch_events(7), "this week"))
        except Exception as e:
            logger.error("NL week: %s", e)
            await update.message.reply_text("Couldn't fetch this week's events.")

    elif intent == "check_free":
        try:
            date = d.get("date") or datetime.now(tz=SGT).strftime("%Y-%m-%d")
            events = fetch_events_for_date(date)
            if not events:
                reply = ask_claude(
                    f"User asked: '{text}'. No events on {date}. 1-sentence friendly reply.",
                    max_tokens=60,
                )
            else:
                lines = [f"- {e.get('summary','Untitled')} @ {_to_sgt_str(e['start'])}" for e in events]
                reply = ask_claude(
                    f"User asked: '{text}'. Events on {date}:\n" + "\n".join(lines) +
                    "\nAnswer in 1-2 sentences.",
                    max_tokens=80,
                )
            await update.message.reply_text(reply)
        except Exception as e:
            logger.error("NL check_free: %s", e)
            await update.message.reply_text("Couldn't check your availability.")

    # WRITE — confirmation required
    elif intent == "add":
        title    = d.get("title")
        date     = d.get("date")
        time_val = d.get("time")
        if title and date and time_val:
            context.user_data["pending_action"] = {"type": "add", "title": title, "date": date, "time": time_val}
            await update.message.reply_text(
                f"Add *{title}* on {date} at {time_val}. Go ahead?", reply_markup=CONFIRM_KB,
            )
        else:
            context.user_data["nl_pending"] = {"title": title, "date": date, "time": time_val}
            p = context.user_data["nl_pending"]
            if not title:
                p["missing"] = "title"
                await update.message.reply_text("What should I call this event?")
            elif not date:
                p["missing"] = "date"
                await update.message.reply_text("What date?")
            else:
                p["missing"] = "time"
                await update.message.reply_text("What time? (or 'all day')")

    elif intent == "delete":
        try:
            events = fetch_events(30)
            if not events:
                await update.message.reply_text("No upcoming events to delete.")
                return
            search    = d.get("search_term") or ""
            hint_date = d.get("date") or ""
            hint_time = d.get("time") or ""
            events = _filter_events(events, search, hint_date, hint_time)
            await _show_delete_menu(update, context, events)
        except Exception as e:
            logger.error("NL delete: %s", e)
            await update.message.reply_text("Couldn't fetch events.")

    elif intent == "edit":
        try:
            events = fetch_events(30)
            if not events:
                await update.message.reply_text("No upcoming events to edit.")
                return
            search    = d.get("search_term") or ""
            hint_date = d.get("date") or ""
            filtered  = _filter_events(events, search, hint_date)

            new_values = {
                "new_title": d.get("new_title"),
                "new_date":  d.get("new_date"),
                "new_time":  d.get("new_time"),
                "new_description": None,
            }
            has_new_values = any(v for v in new_values.values() if v)

            if len(filtered) == 1:
                event = filtered[0]
                if has_new_values:
                    patch = build_patch_body(event, new_values)
                    if not patch:
                        await update.message.reply_text("Nothing to change there.")
                        return
                    context.user_data["pending_action"] = {
                        "type": "edit", "event_id": event["id"],
                        "event_title": event.get("summary", "Untitled"), "patch": patch,
                    }
                    await update.message.reply_text(_describe_edit(event, new_values), reply_markup=CONFIRM_KB)
                else:
                    context.user_data["edit_event"] = event
                    await update.message.reply_text(
                        f"Editing *{event.get('summary','Untitled')}*. What would you like to change?\n"
                        "(e.g. 'rename to X', 'move to 4pm', 'reschedule to Monday')"
                    )
            else:
                if has_new_values:
                    context.user_data["edit_new_values"] = new_values
                await _show_edit_menu(update, context, filtered)
        except Exception as e:
            logger.error("NL edit: %s", e)
            await update.message.reply_text("Couldn't fetch events.")

    else:
        await update.message.reply_text(
            "Not sure what you mean. Try:\n"
            "• \"What's on today?\"\n"
            "• \"Add a call with Sarah on Monday at 10am\"\n"
            "• \"Edit my Friday meeting\"\n"
            "• \"Delete my 3pm tomorrow\"\n"
            "• \"Am I free Tuesday afternoon?\""
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN not set in .env")
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set in .env")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_receive_title)],
            DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_receive_date)],
            TIME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_receive_time)],
        },
        fallbacks=[CommandHandler("cancel", add_cancel)],
    )

    app.add_handler(CommandHandler("start",  start_command))
    app.add_handler(CommandHandler("today",  today_command))
    app.add_handler(CommandHandler("week",   week_command))
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(CommandHandler("edit",   edit_command))
    app.add_handler(add_conv)
    app.add_handler(CallbackQueryHandler(confirm_callback,   pattern=r"^confirm_"))
    app.add_handler(CallbackQueryHandler(delete_callback,    pattern=r"^del_"))
    app.add_handler(CallbackQueryHandler(edit_pick_callback, pattern=r"^editpick_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_natural_message))

    logger.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
