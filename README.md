# AI Calendar Agent

An autonomous AI agent that manages Google Calendar through natural language via Telegram. No GUI (graphical user interface), no clicks — just conversation! 

## What It Does

Message the bot in plain English and it handles the rest:

- "What's on today?" → summarises your day
- "Am I free tomorrow afternoon?" → checks availability 
- "Add a meeting with the team on Friday at 3pm" → creates the event and asks for confirmation
- "Delete my 2pm tomorrow" → finds it and confirms before deleting
- "Move my Monday standup to 4pm" → edits the event with a confirmation gate

## Why I Built This

This was a deliberate exercise in end-to-end agent deployment — not a tutorial follow-along. The goal was to design, build, ship, and iterate on a fully functional AI agent in a single day, making real architectural decisions along the way.

The core challenge: build something that is fast, secure, always-on, and actually useful — without a server, without a budget, and without prior infrastructure experience.

## Architecture

You (Telegram) → bot.py → Claude API (intent classification) → Google Calendar API → bot.py → Telegram

**Claude API** handles natural language understanding — parsing intent, resolving dates like "next Friday" or "tomorrow afternoon", and formatting responses conversationally.

**Google Calendar API** executes the actual read/write operations on the calendar.

**python-telegram-bot** manages the Telegram interface, conversation state, and inline confirmation buttons.

**Railway** hosts the bot in the cloud so it runs 24/7 independent of local hardware.

## Key Design Decisions

**Confirmation gate for all write operations.** The agent never modifies the calendar without explicit user approval. Read operations (summaries, availability checks) are instant. Write operations (add, edit, delete) always show exactly what will happen and wait for a "yes" before proceeding. This is a deliberate safety pattern for any agent that touches real data.

**Timezone-aware from the ground up.** All datetimes are handled in SGT (Asia/Singapore, UTC+8) end-to-end — from natural language parsing through to Google Calendar API calls and display formatting.

**Token efficiency.** Claude is only called when intelligence is genuinely needed. Errors, confirmations, and state transitions use plain Python strings. This keeps latency low and API costs minimal.

**Cloud-native secrets management.** No credentials are stored in code or version control. All secrets (Telegram token, Anthropic API key, Google OAuth credentials) live in Railway's environment variable vault.

## Stack

- Python 3.13
- Claude API (Anthropic) — intent classification and response formatting
- Google Calendar API — calendar read/write
- python-telegram-bot — Telegram interface
- Railway — cloud hosting
- pytz — timezone handling

## What I'd Do Differently

Replace the Claude API call for intent classification with a lightweight local classifier. The current architecture sends every message to the LLM just to determine intent — that adds 1-2 seconds of latency and unnecessary API cost for simple commands like "/today". A simple keyword-based router in Python handles 80% of cases instantly, reserving Claude for genuine ambiguity. This would cut response time by half and reduce cost by roughly 40%.

I'd also implement a proper refresh token flow for Google OAuth from day one rather than treating it as a deployment afterthought. On a cloud server with no browser, re-authentication becomes a manual intervention — a background token refresh loop eliminates that entirely.

## Time taken

1 day — strategy, architecture, build, deployment, and iteration
