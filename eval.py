# eval.py
# AI Calendar Agent — Functional + LLM Quality Evals
# Run with: python eval.py

import json
import csv
import os
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
import anthropic

load_dotenv()

SGT = pytz.timezone("Asia/Singapore")
anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ── Helpers ──────────────────────────────────────────────────────────────────

def classify_intent(text: str) -> dict:
    today = datetime.now(tz=SGT)
    msg = anthropic_client.messages.create(
        model="claude-opus-4-5",
        max_tokens=160,
        messages=[{"role": "user", "content": (
            f"Today: {today.strftime('%Y-%m-%d')} ({today.strftime('%A')}).\n"
            f"Message: \"{text}\"\n\n"
            "Return JSON only, no markdown. Fields:\n"
            "  intent: today|week|add|delete|edit|check_free|unknown\n"
            "  title: str|null\n"
            "  date: YYYY-MM-DD|null\n"
            "  time: HH:MM|'all day'|null\n"
            "  search_term: str|null\n"
            "  new_title: str|null\n"
            "  new_date: YYYY-MM-DD|null\n"
            "  new_time: HH:MM|null"
        )}]
    )
    raw = msg.content[0].text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def get_expected_date(offset_days: int) -> str:
    return (datetime.now(tz=SGT) + timedelta(days=offset_days)).strftime("%Y-%m-%d")


# ── LLM Intent Evals ─────────────────────────────────────────────────────────

LLM_TESTS = [
    {
        "input": "What's on today?",
        "expected_intent": "today",
        "expected_date": get_expected_date(0),
    },
    {
        "input": "What's on tomorrow?",
        "expected_intent": "today",
        "expected_date": get_expected_date(1),
    },
    {
        "input": "What do I have this week?",
        "expected_intent": "week",
        "expected_date": None,
    },
    {
        "input": "Am I free Friday afternoon?",
        "expected_intent": "check_free",
        "expected_date": get_expected_date(
            (4 - datetime.now(tz=SGT).weekday()) % 7 or 7
        ),
    },
    {
        "input": "Add a meeting with Sarah tomorrow at 3pm",
        "expected_intent": "add",
        "expected_date": get_expected_date(1),
        "expected_time": "15:00",
        "expected_title_contains": "Sarah",
    },
    {
        "input": "Add lunch next Monday at 1pm",
        "expected_intent": "add",
        "expected_time": "13:00",
    },
    {
        "input": "Add a call at 11pm tonight",
        "expected_intent": "add",
        "expected_date": get_expected_date(0),
        "expected_time": "23:00",
    },
    {
        "input": "Delete my 2pm tomorrow",
        "expected_intent": "delete",
        "expected_date": get_expected_date(1),
    },
    {
        "input": "Cancel my morning standup",
        "expected_intent": "delete",
    },
    {
        "input": "Move my 3pm to 4pm",
        "expected_intent": "edit",
        "expected_new_time": "16:00",
    },
    {
        "input": "Reschedule my Monday meeting to Tuesday",
        "expected_intent": "edit",
    },
    {
        "input": "Rename my standup to Team Sync",
        "expected_intent": "edit",
        "expected_new_title": "Team Sync",
    },
    {
        "input": "What's the weather like?",
        "expected_intent": "unknown",
    },
    {
        "input": "Remind me to call mum",
        "expected_intent": "unknown",
    },
]


def run_llm_evals():
    print("\n── LLM Intent Evals ─────────────────────────────────")
    results = []
    passed = 0

    for test in LLM_TESTS:
        result = classify_intent(test["input"])
        checks = []

        # Intent check
        intent_ok = result.get("intent") == test["expected_intent"]
        checks.append(("intent", intent_ok, test["expected_intent"], result.get("intent")))

        # Date check
        if "expected_date" in test and test["expected_date"]:
            date_ok = result.get("date") == test["expected_date"]
            checks.append(("date", date_ok, test["expected_date"], result.get("date")))

        # Time check
        if "expected_time" in test:
            time_ok = result.get("time") == test["expected_time"]
            checks.append(("time", time_ok, test["expected_time"], result.get("time")))

        # New time check
        if "expected_new_time" in test:
            new_time_ok = result.get("new_time") == test["expected_new_time"]
            checks.append(("new_time", new_time_ok, test["expected_new_time"], result.get("new_time")))

        # New title check
        if "expected_new_title" in test:
            new_title_ok = result.get("new_title") == test["expected_new_title"]
            checks.append(("new_title", new_title_ok, test["expected_new_title"], result.get("new_title")))

        # Title contains check
        if "expected_title_contains" in test:
            title = result.get("title") or ""
            title_ok = test["expected_title_contains"].lower() in title.lower()
            checks.append(("title_contains", title_ok, test["expected_title_contains"], title))

        all_passed = all(c[1] for c in checks)
        if all_passed:
            passed += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"

        print(f"\n{status} | \"{test['input']}\"")
        for field, ok, expected, actual in checks:
            if not ok:
                print(f"       {field}: expected={expected}, got={actual}")

        results.append({
            "input": test["input"],
            "passed": all_passed,
            "expected_intent": test["expected_intent"],
            "actual_intent": result.get("intent"),
            "full_result": json.dumps(result),
        })

    total = len(LLM_TESTS)
    print(f"\nLLM Evals: {passed}/{total} passed ({round(passed/total*100)}%)")
    return results


# ── Functional Evals ──────────────────────────────────────────────────────────

def run_functional_evals():
    print("\n── Functional Evals ─────────────────────────────────")
    print("These require a live Google Calendar connection.")
    print("Skipping in dry-run mode — set RUN_FUNCTIONAL=true to enable.")

    if os.getenv("RUN_FUNCTIONAL") != "true":
        return []

    from bot import get_calendar_service, create_event, delete_event_by_id, fetch_events_for_date
    results = []
    service = get_calendar_service()
    today = datetime.now(tz=SGT).strftime("%Y-%m-%d")

    # Test 1: Create event
    print("\nTest 1: Create event at 15:00")
    try:
        create_event("Eval Test Meeting", today, "15:00")
        events = fetch_events_for_date(today)
        match = [e for e in events if "Eval Test Meeting" in e.get("summary", "")]
        assert match, "Event not found after creation"
        event_id = match[0]["id"]
        print("✅ PASS — event created")
        results.append({"test": "create_event", "passed": True})
    except Exception as e:
        print(f"❌ FAIL — {e}")
        results.append({"test": "create_event", "passed": False, "error": str(e)})
        return results

    # Test 2: Event appears in today's fetch
    print("\nTest 2: Event appears in today fetch")
    try:
        events = fetch_events_for_date(today)
        titles = [e.get("summary", "") for e in events]
        assert "Eval Test Meeting" in titles
        print("✅ PASS")
        results.append({"test": "fetch_today", "passed": True})
    except Exception as e:
        print(f"❌ FAIL — {e}")
        results.append({"test": "fetch_today", "passed": False, "error": str(e)})

    # Test 3: 11pm event end time is 23:59 not 00:00
    print("\nTest 3: 11pm event end time boundary")
    try:
        create_event("Eval Late Meeting", today, "23:00")
        events = fetch_events_for_date(today)
        match = [e for e in events if "Eval Late Meeting" in e.get("summary", "")]
        assert match, "Late event not found"
        end_time = match[0]["end"].get("dateTime", "")
        assert "23:59" in end_time, f"Expected 23:59, got {end_time}"
        late_id = match[0]["id"]
        print("✅ PASS — end time is 23:59")
        results.append({"test": "late_event_boundary", "passed": True})
        delete_event_by_id(late_id)
    except Exception as e:
        print(f"❌ FAIL — {e}")
        results.append({"test": "late_event_boundary", "passed": False, "error": str(e)})

    # Test 4: Delete event
    print("\nTest 4: Delete event")
    try:
        delete_event_by_id(event_id)
        events = fetch_events_for_date(today)
        titles = [e.get("summary", "") for e in events]
        assert "Eval Test Meeting" not in titles
        print("✅ PASS — event deleted")
        results.append({"test": "delete_event", "passed": True})
    except Exception as e:
        print(f"❌ FAIL — {e}")
        results.append({"test": "delete_event", "passed": False, "error": str(e)})

    return results


# ── CSV Export ────────────────────────────────────────────────────────────────

def export_csv(llm_results, functional_results):
    path = "eval_results.csv"
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["type", "test", "passed", "notes"])
        writer.writeheader()
        for r in llm_results:
            writer.writerow({
                "type": "LLM",
                "test": r["input"],
                "passed": r["passed"],
                "notes": f"expected={r['expected_intent']}, got={r['actual_intent']}"
            })
        for r in functional_results:
            writer.writerow({
                "type": "Functional",
                "test": r["test"],
                "passed": r["passed"],
                "notes": r.get("error", "")
            })
    print(f"\nResults exported to {path}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    llm_results = run_llm_evals()
    functional_results = run_functional_evals()
    export_csv(llm_results, functional_results)
