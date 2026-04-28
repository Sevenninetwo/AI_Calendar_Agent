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
- Telegram-bot — Telegram interface (perfect playground for developers and hobbyists)
- Railway — cloud hosting
- pytz — timezone handling

## Evals

The repo includes an automated eval suite (see `eval.py`) covering two layers:

1) **LLM Quality Evals** — 14 test cases that verify Claude correctly classifies intent, resolves dates like "tomorrow" and "next Friday", extracts event titles and times, and handles edge cases like unknown intents.

2) **Functional Evals** — live integration tests against Google Calendar that verify event creation, retrieval, the 11pm to 11:59pm boundary fix, and deletion. Runs only when `RUN_FUNCTIONAL=true` is set to avoid touching your real calendar unintentionally, as a precautionary measure. 

Results are exported to `eval_results.csv` after every run for quality tracking over time.

To run:
```bash
python eval.py
# or with functional tests:
RUN_FUNCTIONAL=true python eval.py
```

## What I'd Do Differently

The bot works, but two things bit me during deployment that I'd design out from the start next time.

1. The first is response speed. Right now the bot asks Claude to figure out what you mean before doing anything, even for something as simple as "what's on today?" That adds unnecessary wait time for commands that don't actually need AI to interpret. I'd build a simple fast-path that handles obvious requests instantly, and only bring Claude in when the message is genuinely ambiguous. Faster for the user, cheaper to run.

2. The second is the Google authentication setup. I didn't think through what happens when the bot runs on a cloud server with no browser — and I paid for it with two manual re-authentication incidents mid-build. I'd design the credential refresh to happen automatically in the background from day one, so it never becomes a user-facing problem.

Both are solvable. I just didn't anticipate them until I hit them in production.

## Time taken

1 day — strategy, architecture, build, deployment, and iteration
