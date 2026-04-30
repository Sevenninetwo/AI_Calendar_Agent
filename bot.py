Skip to content
Sevenninetwo
AI_Calendar_Agent
Repository navigation
Code
Issues
Pull requests
Actions
Projects
Wiki
Security and quality
Insights
Settings
Commit e7db9dd
Sevenninetwo
Sevenninetwo
authored
last week
·
·
Verified
Update bot.py
main
1 parent 
a7ba4fd
 commit 
e7db9dd
1 file changed

+226
-58
Lines changed: 226 additions & 58 deletions
File tree
Filter files…
bot.py
Search within code
 
‎bot.py‎
+226
-58
Lines changed: 226 additions & 58 deletions
Original file line number	Diff line number	Diff line change
@@ -7,6 +7,7 @@

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    ConversationHandler, MessageHandler, filters,
@@ -308,14 +309,22 @@ async def _show_delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE,
    context.user_data["delete_events"] = events
    kb = [[InlineKeyboardButton(_event_label(e), callback_data=f"del_{i}")] for i, e in enumerate(events[:10])]
    kb.append([InlineKeyboardButton("❌ Cancel", callback_data="del_cancel")])
    await update.message.reply_text("Which event to delete?", reply_markup=InlineKeyboardMarkup(kb))
    await update.message.reply_text(
        "Which event to delete?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def _show_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, events: list):
    context.user_data["edit_events"] = events
    kb = [[InlineKeyboardButton(_event_label(e), callback_data=f"editpick_{i}")] for i, e in enumerate(events[:10])]
    kb.append([InlineKeyboardButton("❌ Cancel", callback_data="editpick_cancel")])
    await update.message.reply_text("Which event to edit?", reply_markup=InlineKeyboardMarkup(kb))
    await update.message.reply_text(
        "Which event to edit?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb),
    )


def _filter_events(events: list, search: str, hint_date: str, hint_time: str = "") -> list:
@@ -335,72 +344,109 @@ def _filter_events(events: list, search: str, hint_date: str, hint_time: str = "
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Calendar Bot. Talk naturally or use commands:\n"
        "/today · /week · /add · /edit · /delete"
        "/today · /week · /add · /edit · /delete",
        parse_mode=ParseMode.MARKDOWN,
    )


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        today_str = datetime.now(tz=SGT).strftime("%Y-%m-%d")
        await update.message.reply_text(format_events(fetch_events_for_date(today_str), "today"))
        await update.message.reply_text(
            format_events(fetch_events_for_date(today_str), "today"),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.error("today: %s", e)
        await update.message.reply_text("Couldn't fetch today's events.")
        await update.message.reply_text(
            "Couldn't fetch today's events.",
            parse_mode=ParseMode.MARKDOWN,
        )


async def week_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(format_events(fetch_events(7), "this week"))
        await update.message.reply_text(
            format_events(fetch_events(7), "this week"),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.error("week: %s", e)
        await update.message.reply_text("Couldn't fetch this week's events.")
        await update.message.reply_text(
            "Couldn't fetch this week's events.",
            parse_mode=ParseMode.MARKDOWN,
        )


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        events = fetch_events(30)
        if not events:
            await update.message.reply_text("No upcoming events.")
            await update.message.reply_text(
                "No upcoming events.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        await _show_delete_menu(update, context, events)
    except Exception as e:
        logger.error("delete cmd: %s", e)
        await update.message.reply_text("Couldn't fetch events.")
        await update.message.reply_text(
            "Couldn't fetch events.",
            parse_mode=ParseMode.MARKDOWN,
        )


async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        events = fetch_events(30)
        if not events:
            await update.message.reply_text("No upcoming events.")
            await update.message.reply_text(
                "No upcoming events.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        await _show_edit_menu(update, context, events)
    except Exception as e:
        logger.error("edit cmd: %s", e)
        await update.message.reply_text("Couldn't fetch events.")
        await update.message.reply_text(
            "Couldn't fetch events.",
            parse_mode=ParseMode.MARKDOWN,
        )


# ── /add ConversationHandler ──────────────────────────────────────────────────

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Event title?")
    await update.message.reply_text(
        "Event title?",
        parse_mode=ParseMode.MARKDOWN,
    )
    return TITLE


async def add_receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text.strip()
    await update.message.reply_text("Date? (e.g. tomorrow, next Friday, 2025-06-20)")
    await update.message.reply_text(
        "Date? (e.g. tomorrow, next Friday, 2025-06-20)",
        parse_mode=ParseMode.MARKDOWN,
    )
    return DATE


async def add_receive_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["date"] = parse_date(update.message.text.strip())
        await update.message.reply_text("Time? (e.g. 2pm, 14:30, or 'all day')")
        await update.message.reply_text(
            "Time? (e.g. 2pm, 14:30, or 'all day')",
            parse_mode=ParseMode.MARKDOWN,
        )
        return TIME
    except Exception:
        await update.message.reply_text("Couldn't parse that date. Try YYYY-MM-DD.")
        await update.message.reply_text(
            "Couldn't parse that date. Try YYYY-MM-DD.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return DATE


@@ -411,14 +457,18 @@ async def add_receive_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pending_action"] = {"type": "add", "title": title, "date": date, "time": raw_time}
    await update.message.reply_text(
        f"Add *{title}* on {date} at {raw_time}. Go ahead?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=CONFIRM_KB,
    )
    return ConversationHandler.END


async def add_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Cancelled.")
    await update.message.reply_text(
        "Cancelled.",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


@@ -430,23 +480,38 @@ async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.pop("pending_action", None)

    if query.data == "confirm_no" or not action:
        await query.edit_message_text("Cancelled.")
        await query.edit_message_text(
            "Cancelled.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        t = action["type"]
        if t == "add":
            create_event(action["title"], action["date"], action["time"])
            await query.edit_message_text(f"✅ '{action['title']}' added.")
            await query.edit_message_text(
                f"✅ '{action['title']}' added.",
                parse_mode=ParseMode.MARKDOWN,
            )
        elif t == "delete":
            delete_event_by_id(action["event_id"])
            await query.edit_message_text(f"🗑️ '{action['event_title']}' deleted.")
            await query.edit_message_text(
                f"🗑️ '{action['event_title']}' deleted.",
                parse_mode=ParseMode.MARKDOWN,
            )
        elif t == "edit":
            patch_event(action["event_id"], action["patch"])
            await query.edit_message_text(f"✏️ '{action['event_title']}' updated.")
            await query.edit_message_text(
                f"✏️ '{action['event_title']}' updated.",
                parse_mode=ParseMode.MARKDOWN,
            )
    except Exception as e:
        logger.error("confirm execute: %s", e)
        await query.edit_message_text("Something went wrong. Please try again.")
        await query.edit_message_text(
            "Something went wrong. Please try again.",
            parse_mode=ParseMode.MARKDOWN,
        )


async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
@@ -455,7 +520,10 @@ async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if query.data == "del_cancel":
        context.user_data.pop("delete_events", None)
        await query.edit_message_text("Cancelled.")
        await query.edit_message_text(
            "Cancelled.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
@@ -468,11 +536,16 @@ async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
            "type": "delete", "event_id": event["id"], "event_title": title,
        }
        await query.edit_message_text(
            f"Delete *{title}* ({start}). Go ahead?", reply_markup=CONFIRM_KB,
            f"Delete *{title}* ({start}). Go ahead?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=CONFIRM_KB,
        )
    except Exception as e:
        logger.error("delete_callback: %s", e)
        await query.edit_message_text("Couldn't process that.")
        await query.edit_message_text(
            "Couldn't process that.",
            parse_mode=ParseMode.MARKDOWN,
        )


async def edit_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
@@ -482,7 +555,10 @@ async def edit_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE)
    if query.data == "editpick_cancel":
        context.user_data.pop("edit_events", None)
        context.user_data.pop("edit_new_values", None)
        await query.edit_message_text("Cancelled.")
        await query.edit_message_text(
            "Cancelled.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
@@ -495,23 +571,34 @@ async def edit_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE)
        if new_values and any(v for v in new_values.values() if v):
            patch = build_patch_body(event, new_values)
            if not patch:
                await query.edit_message_text("Nothing to change.")
                await query.edit_message_text(
                    "Nothing to change.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
            context.user_data["pending_action"] = {
                "type": "edit", "event_id": event["id"],
                "event_title": event.get("summary", "Untitled"), "patch": patch,
            }
            await query.edit_message_text(_describe_edit(event, new_values), reply_markup=CONFIRM_KB)
            await query.edit_message_text(
                _describe_edit(event, new_values),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=CONFIRM_KB,
            )
        else:
            context.user_data["edit_event"] = event
            title = event.get("summary", "Untitled")
            await query.edit_message_text(
                f"Editing *{title}*. What would you like to change?\n"
                "(e.g. 'rename to X', 'move to 4pm', 'reschedule to Monday')"
                "(e.g. 'rename to X', 'move to 4pm', 'reschedule to Monday')",
                parse_mode=ParseMode.MARKDOWN,
            )
    except Exception as e:
        logger.error("edit_pick_callback: %s", e)
        await query.edit_message_text("Couldn't process that.")
        await query.edit_message_text(
            "Couldn't process that.",
            parse_mode=ParseMode.MARKDOWN,
        )


# ── Natural language handler ──────────────────────────────────────────────────
@@ -526,22 +613,33 @@ async def handle_natural_message(update: Update, context: ContextTypes.DEFAULT_T
            changes = parse_edit_instruction(text, edit_event)
            if not changes or not any(v for v in changes.values() if v):
                await update.message.reply_text(
                    "Didn't catch that. Try 'rename to X', 'move to 4pm', or 'reschedule to Monday'."
                    "Didn't catch that. Try 'rename to X', 'move to 4pm', or 'reschedule to Monday'.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
            patch = build_patch_body(edit_event, changes)
            if not patch:
                await update.message.reply_text("Nothing to change there. Try again.")
                await update.message.reply_text(
                    "Nothing to change there. Try again.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
            context.user_data.pop("edit_event")
            context.user_data["pending_action"] = {
                "type": "edit", "event_id": edit_event["id"],
                "event_title": edit_event.get("summary", "Untitled"), "patch": patch,
            }
            await update.message.reply_text(_describe_edit(edit_event, changes), reply_markup=CONFIRM_KB)
            await update.message.reply_text(
                _describe_edit(edit_event, changes),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=CONFIRM_KB,
            )
        except Exception as e:
            logger.error("NL edit instruction: %s", e)
            await update.message.reply_text("Couldn't parse that. Try again.")
            await update.message.reply_text(
                "Couldn't parse that. Try again.",
                parse_mode=ParseMode.MARKDOWN,
            )
        return

    # — State 2: collecting missing fields for NL add —
@@ -556,7 +654,10 @@ async def handle_natural_message(update: Update, context: ContextTypes.DEFAULT_T
                pending["date"] = parse_date(text)
                pending.pop("missing")
            except Exception:
                await update.message.reply_text("Couldn't parse that date. Try YYYY-MM-DD.")
                await update.message.reply_text(
                    "Couldn't parse that date. Try YYYY-MM-DD.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
        elif missing == "time":
            pending["time"] = text
@@ -565,23 +666,34 @@ async def handle_natural_message(update: Update, context: ContextTypes.DEFAULT_T
        # Ask for the next missing field
        if not pending.get("title"):
            pending["missing"] = "title"
            await update.message.reply_text("What should I call this event?")
            await update.message.reply_text(
                "What should I call this event?",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        if not pending.get("date"):
            pending["missing"] = "date"
            await update.message.reply_text("What date?")
            await update.message.reply_text(
                "What date?",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        if not pending.get("time"):
            pending["missing"] = "time"
            await update.message.reply_text("What time? (or 'all day')")
            await update.message.reply_text(
                "What time? (or 'all day')",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # All fields collected — show confirmation
        title, date, time_val = pending["title"], pending["date"], pending["time"]
        context.user_data.pop("nl_pending")
        context.user_data["pending_action"] = {"type": "add", "title": title, "date": date, "time": time_val}
        await update.message.reply_text(
            f"Add *{title}* on {date} at {time_val}. Go ahead?", reply_markup=CONFIRM_KB,
            f"Add *{title}* on {date} at {time_val}. Go ahead?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=CONFIRM_KB,
        )
        return

@@ -590,7 +702,10 @@ async def handle_natural_message(update: Update, context: ContextTypes.DEFAULT_T
        d = classify_intent(text)
    except Exception as e:
        logger.error("classify_intent: %s", e)
        await update.message.reply_text("Didn't understand that. Try /today, /week, /add, /edit, or /delete.")
        await update.message.reply_text(
            "Didn't understand that. Try /today, /week, /add, /edit, or /delete.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    intent = d.get("intent", "unknown")
@@ -603,19 +718,34 @@ async def handle_natural_message(update: Update, context: ContextTypes.DEFAULT_T
            resolved_date = d.get("date") or today_str
            if resolved_date != today_str:
                label = f"on {resolved_date}"
                await update.message.reply_text(format_events(fetch_events_for_date(resolved_date), label))
                await update.message.reply_text(
                    format_events(fetch_events_for_date(resolved_date), label),
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await update.message.reply_text(format_events(fetch_events_for_date(today_str), "today"))
                await update.message.reply_text(
                    format_events(fetch_events_for_date(today_str), "today"),
                    parse_mode=ParseMode.MARKDOWN,
                )
        except Exception as e:
            logger.error("NL today: %s", e)
            await update.message.reply_text("Couldn't fetch today's events.")
            await update.message.reply_text(
                "Couldn't fetch today's events.",
                parse_mode=ParseMode.MARKDOWN,
            )

    elif intent == "week":
        try:
            await update.message.reply_text(format_events(fetch_events(7), "this week"))
            await update.message.reply_text(
                format_events(fetch_events(7), "this week"),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.error("NL week: %s", e)
            await update.message.reply_text("Couldn't fetch this week's events.")
            await update.message.reply_text(
                "Couldn't fetch this week's events.",
                parse_mode=ParseMode.MARKDOWN,
            )

    elif intent == "check_free":
        try:
@@ -633,10 +763,16 @@ async def handle_natural_message(update: Update, context: ContextTypes.DEFAULT_T
                    "\nAnswer in 1-2 sentences.",
                    max_tokens=80,
                )
            await update.message.reply_text(reply)
            await update.message.reply_text(
                reply,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.error("NL check_free: %s", e)
            await update.message.reply_text("Couldn't check your availability.")
            await update.message.reply_text(
                "Couldn't check your availability.",
                parse_mode=ParseMode.MARKDOWN,
            )

    # WRITE — confirmation required
    elif intent == "add":
@@ -646,26 +782,40 @@ async def handle_natural_message(update: Update, context: ContextTypes.DEFAULT_T
        if title and date and time_val:
            context.user_data["pending_action"] = {"type": "add", "title": title, "date": date, "time": time_val}
            await update.message.reply_text(
                f"Add *{title}* on {date} at {time_val}. Go ahead?", reply_markup=CONFIRM_KB,
                f"Add *{title}* on {date} at {time_val}. Go ahead?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=CONFIRM_KB,
            )
        else:
            context.user_data["nl_pending"] = {"title": title, "date": date, "time": time_val}
            p = context.user_data["nl_pending"]
            if not title:
                p["missing"] = "title"
                await update.message.reply_text("What should I call this event?")
                await update.message.reply_text(
                    "What should I call this event?",
                    parse_mode=ParseMode.MARKDOWN,
                )
            elif not date:
                p["missing"] = "date"
                await update.message.reply_text("What date?")
                await update.message.reply_text(
                    "What date?",
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                p["missing"] = "time"
                await update.message.reply_text("What time? (or 'all day')")
                await update.message.reply_text(
                    "What time? (or 'all day')",
                    parse_mode=ParseMode.MARKDOWN,
                )

    elif intent == "delete":
        try:
            events = fetch_events(30)
            if not events:
                await update.message.reply_text("No upcoming events to delete.")
                await update.message.reply_text(
                    "No upcoming events to delete.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
            search    = d.get("search_term") or ""
            hint_date = d.get("date") or ""
@@ -674,13 +824,19 @@ async def handle_natural_message(update: Update, context: ContextTypes.DEFAULT_T
            await _show_delete_menu(update, context, events)
        except Exception as e:
            logger.error("NL delete: %s", e)
            await update.message.reply_text("Couldn't fetch events.")
            await update.message.reply_text(
                "Couldn't fetch events.",
                parse_mode=ParseMode.MARKDOWN,
            )

    elif intent == "edit":
        try:
            events = fetch_events(30)
            if not events:
                await update.message.reply_text("No upcoming events to edit.")
                await update.message.reply_text(
                    "No upcoming events to edit.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
            search    = d.get("search_term") or ""
            hint_date = d.get("date") or ""
@@ -699,26 +855,37 @@ async def handle_natural_message(update: Update, context: ContextTypes.DEFAULT_T
                if has_new_values:
                    patch = build_patch_body(event, new_values)
                    if not patch:
                        await update.message.reply_text("Nothing to change there.")
                        await update.message.reply_text(
                            "Nothing to change there.",
                            parse_mode=ParseMode.MARKDOWN,
                        )
                        return
                    context.user_data["pending_action"] = {
                        "type": "edit", "event_id": event["id"],
                        "event_title": event.get("summary", "Untitled"), "patch": patch,
                    }
                    await update.message.reply_text(_describe_edit(event, new_values), reply_markup=CONFIRM_KB)
                    await update.message.reply_text(
                        _describe_edit(event, new_values),
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=CONFIRM_KB,
                    )
                else:
                    context.user_data["edit_event"] = event
                    await update.message.reply_text(
                        f"Editing *{event.get('summary','Untitled')}*. What would you like to change?\n"
                        "(e.g. 'rename to X', 'move to 4pm', 'reschedule to Monday')"
                        "(e.g. 'rename to X', 'move to 4pm', 'reschedule to Monday')",
                        parse_mode=ParseMode.MARKDOWN,
                    )
            else:
                if has_new_values:
                    context.user_data["edit_new_values"] = new_values
                await _show_edit_menu(update, context, filtered)
        except Exception as e:
            logger.error("NL edit: %s", e)
            await update.message.reply_text("Couldn't fetch events.")
            await update.message.reply_text(
                "Couldn't fetch events.",
                parse_mode=ParseMode.MARKDOWN,
            )

    else:
        await update.message.reply_text(
@@ -727,7 +894,8 @@ async def handle_natural_message(update: Update, context: ContextTypes.DEFAULT_T
            "• \"Add a call with Sarah on Monday at 10am\"\n"
            "• \"Edit my Friday meeting\"\n"
            "• \"Delete my 3pm tomorrow\"\n"
            "• \"Am I free Tuesday afternoon?\""
            "• \"Am I free Tuesday afternoon?\"",
            parse_mode=ParseMode.MARKDOWN,
        )


0 commit comments
Comments
0
 (0)
Comment
You're not receiving notifications from this thread.

There are no files selected for viewing
