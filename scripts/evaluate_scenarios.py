"""
evaluate_scenarios.py
=====================
Runs the golden scenarios in golden_scenarios.yaml against the live API
and lets you score each response. Saves results for before/after comparison.

Usage:
    # Run all scenarios (interactive scoring):
    python scripts/evaluate_scenarios.py

    # Run specific scenarios by id:
    python scripts/evaluate_scenarios.py --ids career_hinglish_anxious_01 finance_english_worried_01

    # Run without scoring (just see outputs side by side):
    python scripts/evaluate_scenarios.py --no-score

    # Compare two saved result files:
    python scripts/evaluate_scenarios.py --compare results/eval_before.json results/eval_after.json

    # Skip scenarios already scored in a previous run (resume):
    python scripts/evaluate_scenarios.py --resume results/eval_before.json
"""

import argparse
import json
import sys
import time
import textwrap
from datetime import datetime
from pathlib import Path

import requests
import yaml

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL = "http://localhost:6262"
API_KEY = "test_api_key"
SCENARIOS_FILE = Path(__file__).parent.parent / "data" / "golden_scenarios.yaml"
RESULTS_DIR = Path(__file__).parent.parent / "data" / "eval_results"

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
}

# ── Terminal colours (works on Windows 10+, macOS, Linux) ─────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
CYAN   = "\033[36m"
BLUE   = "\033[34m"
MAGENTA= "\033[35m"

def c(text, *codes): return "".join(codes) + str(text) + RESET
def hr(char="─", width=80): return char * width


# ── API helpers ───────────────────────────────────────────────────────────────

def initialize_user(user_id: str, profile: dict) -> bool:
    payload = {
        "user_id": user_id,
        "user_profile": {**profile, "user_id": user_id},
        "conversation_history": [],
    }
    try:
        r = requests.post(f"{BASE_URL}/api/v1/chat/initialize", json=payload, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return True
    except Exception as e:
        print(c(f"  [ERROR] Initialize failed: {e}", RED))
        return False


def send_message(user_id: str, question: str) -> dict:
    payload = {"user_id": user_id, "question": question}
    try:
        r = requests.post(f"{BASE_URL}/api/v1/chat/message", json=payload, headers=HEADERS, timeout=120)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        return {"error": "Request timed out after 120s"}
    except Exception as e:
        return {"error": str(e)}


def health_check() -> bool:
    try:
        r = requests.get(f"{BASE_URL}/api/v1/health", headers=HEADERS, timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def redis_check() -> tuple[bool, str]:
    """
    Verify Redis is reachable by attempting a real initialize call
    with a throwaway user. Returns (ok, error_message).
    """
    payload = {
        "user_id": "__eval_preflight__",
        "user_profile": {
            "user_id": "__eval_preflight__",
            "name": "Test",
            "date_of_birth": "1990-01-01",
            "time_of_birth": "12:00:00",
            "place_of_birth": "Delhi, India",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "timezone": "Asia/Kolkata",
            "preferred_system": "vedic",
        },
        "conversation_history": [],
    }
    try:
        r = requests.post(f"{BASE_URL}/api/v1/chat/initialize", json=payload, headers=HEADERS, timeout=10)
        if r.status_code in (200, 201):
            return True, ""
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
        detail = body.get("detail", str(body)) if isinstance(body, dict) else str(body)
        return False, f"HTTP {r.status_code}: {detail}"
    except Exception as e:
        return False, str(e)


# ── Display helpers ───────────────────────────────────────────────────────────

def wrap(text: str, width: int = 76, indent: str = "  ") -> str:
    lines = text.strip().split("\n")
    wrapped = []
    for line in lines:
        if line.strip() == "":
            wrapped.append("")
        else:
            wrapped.extend(textwrap.wrap(line, width=width, initial_indent=indent, subsequent_indent=indent))
    return "\n".join(wrapped)


def print_turn(role: str, text: str, colour: str):
    label = "USER" if role == "user" else "GOLDEN ANSWER"
    print(c(f"\n  [{label}]", colour, BOLD))
    print(wrap(text))


def print_actual(text: str):
    print(c("\n  [ACTUAL ANSWER]", CYAN, BOLD))
    print(wrap(text))


def print_scenario_header(scenario: dict, index: int, total: int):
    sid   = scenario.get("id", "unknown")
    tags  = ", ".join(scenario.get("tags", []))
    print("\n" + c(hr("═"), BOLD))
    print(c(f"  SCENARIO {index}/{total}  —  {sid}", BOLD))
    print(c(f"  Tags: {tags}", DIM))
    print(c(hr("─"), DIM))


def score_prompt() -> str:
    """Prompt user for a score. Returns 'good', 'okay', 'bad', or 'skip'."""
    valid = {"g": "good", "o": "okay", "b": "bad", "s": "skip",
             "good": "good", "okay": "okay", "bad": "bad", "skip": "skip"}
    while True:
        try:
            raw = input(c("\n  Score this answer  [g]ood / [o]kay / [b]ad / [s]kip → ", YELLOW, BOLD)).strip().lower()
            if raw in valid:
                return valid[raw]
            print(c("  Please enter g, o, b, or s", RED))
        except (KeyboardInterrupt, EOFError):
            print()
            return "skip"


def notes_prompt() -> str:
    """Optional free-text note from the scorer."""
    try:
        note = input(c("  Optional note (press Enter to skip) → ", DIM)).strip()
        return note
    except (KeyboardInterrupt, EOFError):
        return ""


# ── Core evaluation logic ─────────────────────────────────────────────────────

def run_scenario(scenario: dict, interactive: bool = True) -> dict:
    """
    Run a single scenario against the live API.
    Returns a result dict with actual answer, optional score, and metadata.
    """
    sid      = scenario["id"]
    profile  = scenario.get("user_profile", {})
    chart_ctx = scenario.get("chart_context", "")
    turns    = scenario.get("conversation", [])

    # Extract the first user question (and optional prior turns for multi-turn)
    user_turns = [t for t in turns if t["role"] == "user"]
    golden_turns = [t for t in turns if t["role"] == "assistant"]

    if not user_turns:
        return {"id": sid, "error": "No user turn found", "score": "skip"}

    # For multi-turn scenarios, only run the LAST user question
    # (history from prior turns is fed as conversation_history)
    is_multiturn = len(user_turns) > 1
    question = user_turns[-1]["text"]
    golden   = golden_turns[-1]["text"] if golden_turns else ""

    # Build conversation_history for multi-turn scenarios
    conversation_history = []
    if is_multiturn:
        # Pair up prior turns (exclude the last user turn)
        prior_turns = turns[:-1]  # everything before the final user message
        i = 0
        while i < len(prior_turns) - 1:
            if prior_turns[i]["role"] == "user" and prior_turns[i+1]["role"] == "assistant":
                conversation_history.append({
                    "question": prior_turns[i]["text"],
                    "answer": prior_turns[i+1]["text"],
                    "source": "golden",
                    "timestamp": datetime.utcnow().isoformat(),
                })
                i += 2
            else:
                i += 1

    # Use a unique user_id per scenario run so sessions don't bleed
    user_id = f"eval_{sid}_{int(time.time())}"

    # Initialize
    init_payload = {
        "user_id": user_id,
        "user_profile": {**profile, "user_id": user_id},
        "conversation_history": conversation_history,
    }
    try:
        r = requests.post(f"{BASE_URL}/api/v1/chat/initialize", json=init_payload, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as e:
        err = f"Init failed: {e}"
        print(c(f"\n  Question: ", DIM) + c(question, BOLD))
        print(c(f"\n  ✗ {err}", RED))
        return {"id": sid, "question": question, "error": err, "score": "error"}

    # Send message
    t0 = time.time()
    result = send_message(user_id, question)
    elapsed = round(time.time() - t0, 2)

    actual = result.get("answer", result.get("error", "[no answer]"))

    # Display
    print(c(f"\n  Question: ", DIM) + c(question, BOLD))

    # Show golden answer (condensed if long)
    if golden:
        print(c("\n  ── GOLDEN ANSWER ──────────────────────────────────────────────", GREEN))
        print(wrap(golden))

    print(c(f"\n  ── ACTUAL ANSWER  (⏱ {elapsed}s) ──────────────────────────────────", CYAN))
    if "error" in result and "answer" not in result:
        print(c(wrap(actual), RED))
    else:
        print(wrap(actual))

    # Score
    score = "no_score"
    note  = ""
    if interactive:
        score = score_prompt()
        if score not in ("skip",):
            note = notes_prompt()

    return {
        "id": sid,
        "tags": scenario.get("tags", []),
        "question": question,
        "is_multiturn": is_multiturn,
        "golden": golden,
        "actual": actual,
        "elapsed_s": elapsed,
        "score": score,
        "note": note,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary(results: list[dict]):
    counts = {"good": 0, "okay": 0, "bad": 0, "skip": 0, "error": 0, "no_score": 0}
    for r in results:
        counts[r.get("score", "no_score")] = counts.get(r.get("score", "no_score"), 0) + 1

    scored = counts["good"] + counts["okay"] + counts["bad"]
    total  = len(results)

    print("\n" + c(hr("═"), BOLD))
    print(c("  EVALUATION SUMMARY", BOLD))
    print(c(hr("─"), DIM))
    print(f"  Total scenarios run : {total}")
    print(f"  Scored              : {scored}")
    print(c(f"  Good  : {counts['good']}", GREEN))
    print(c(f"  Okay  : {counts['okay']}", YELLOW))
    print(c(f"  Bad   : {counts['bad']}", RED))
    if counts["skip"]:
        print(c(f"  Skipped: {counts['skip']}", DIM))
    if counts["error"]:
        print(c(f"  Errors : {counts['error']}", RED))

    if scored > 0:
        pct = round(counts["good"] / scored * 100)
        bar_width = 40
        filled = round(counts["good"] / scored * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        col = GREEN if pct >= 70 else YELLOW if pct >= 40 else RED
        print(c(f"\n  Quality score: {pct}%  [{bar}]", col, BOLD))

    # List bad ones
    bad = [r for r in results if r.get("score") == "bad"]
    if bad:
        print(c(f"\n  Needs work:", RED, BOLD))
        for r in bad:
            note = f" — {r['note']}" if r.get("note") else ""
            print(c(f"    • {r['id']}{note}", RED))

    print(c(hr("═"), BOLD))


# ── Compare mode ─────────────────────────────────────────────────────────────

def compare_runs(file_a: str, file_b: str):
    """Compare two eval result files side by side."""
    def load(path):
        with open(path) as f:
            return {r["id"]: r for r in json.load(f)["results"]}

    a = load(file_a)
    b = load(file_b)

    label_a = Path(file_a).stem
    label_b = Path(file_b).stem

    score_order = {"good": 2, "okay": 1, "bad": 0, "skip": -1, "error": -1, "no_score": -1}

    all_ids = sorted(set(a) | set(b))

    print(c(f"\n  Comparing: {label_a}  vs  {label_b}", BOLD))
    print(c(hr("─"), DIM))
    print(f"  {'ID':<45}  {label_a:<10}  {label_b:<10}  Change")
    print(c(hr("─"), DIM))

    improved = degraded = same = 0
    for sid in all_ids:
        ra = a.get(sid, {})
        rb = b.get(sid, {})
        sa = ra.get("score", "—")
        sb = rb.get("score", "—")
        oa = score_order.get(sa, -1)
        ob = score_order.get(sb, -1)

        if oa < ob:
            change_str = c("▲ improved", GREEN)
            improved += 1
        elif oa > ob:
            change_str = c("▼ degraded", RED)
            degraded += 1
        else:
            change_str = c("  same", DIM)
            same += 1

        sa_c = c(sa, GREEN) if sa == "good" else c(sa, YELLOW) if sa == "okay" else c(sa, RED) if sa == "bad" else sa
        sb_c = c(sb, GREEN) if sb == "good" else c(sb, YELLOW) if sb == "okay" else c(sb, RED) if sb == "bad" else sb
        print(f"  {sid:<45}  {sa_c:<20}  {sb_c:<20}  {change_str}")

    print(c(hr("─"), DIM))
    print(c(f"  Improved: {improved}  |  Degraded: {degraded}  |  Same: {same}", BOLD))
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Evaluate golden scenarios against the live API")
    parser.add_argument("--ids", nargs="+", help="Run only these scenario IDs")
    parser.add_argument("--tags", nargs="+", help="Run only scenarios with all these tags")
    parser.add_argument("--no-score", action="store_true", help="Skip interactive scoring")
    parser.add_argument("--compare", nargs=2, metavar=("FILE_A", "FILE_B"), help="Compare two result files")
    parser.add_argument("--resume", metavar="FILE", help="Skip scenarios already scored in FILE")
    parser.add_argument("--output", metavar="FILE", help="Save results to this file (default: auto-named in data/eval_results/)")
    args = parser.parse_args()

    # Compare mode — no API calls needed
    if args.compare:
        compare_runs(*args.compare)
        return

    # Load scenarios
    with open(SCENARIOS_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    scenarios = data.get("scenarios", [])

    # Filter by ID
    if args.ids:
        scenarios = [s for s in scenarios if s["id"] in args.ids]
        if not scenarios:
            print(c(f"No scenarios matched IDs: {args.ids}", RED))
            sys.exit(1)

    # Filter by tags (all specified tags must be present)
    if args.tags:
        scenarios = [s for s in scenarios if all(t in s.get("tags", []) for t in args.tags)]
        if not scenarios:
            print(c(f"No scenarios matched tags: {args.tags}", RED))
            sys.exit(1)

    # Resume: skip already-scored scenarios
    already_scored = {}
    if args.resume:
        try:
            with open(args.resume) as f:
                prev = json.load(f)
            already_scored = {r["id"]: r for r in prev.get("results", []) if r.get("score") not in ("skip", "error", "no_score")}
            print(c(f"  Resuming — skipping {len(already_scored)} already-scored scenarios.", DIM))
        except Exception as e:
            print(c(f"  Could not load resume file: {e}", YELLOW))

    # Pre-flight checks
    print(c(f"\n  Checking API at {BASE_URL} ...", DIM))
    if not health_check():
        print(c(f"  ✗ API is not reachable at {BASE_URL}", RED, BOLD))
        print(c("  Start the server:  uvicorn src.api.main:app --host 0.0.0.0 --port 6262", DIM))
        sys.exit(1)
    print(c("  ✓ API is healthy", GREEN))

    print(c("  Checking Redis (via /initialize preflight) ...", DIM))
    redis_ok, redis_err = redis_check()
    if not redis_ok:
        print(c(f"  ✗ Redis is offline or unreachable: {redis_err}", RED, BOLD))
        print(c("  Start Redis:  redis-server", DIM))
        print(c("  Or on Windows with WSL:  wsl redis-server", DIM))
        sys.exit(1)
    print(c("  ✓ Redis is reachable\n", GREEN))

    interactive = not args.no_score
    results = list(already_scored.values())  # carry over from resume
    total = len(scenarios)

    # Stable output path for this run (so auto-save is resumable)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    run_file = (
        Path(args.output) if args.output
        else RESULTS_DIR / f"eval_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    )

    def save():
        payload = {
            "run_timestamp": datetime.utcnow().isoformat(),
            "api_base": BASE_URL,
            "scenarios_file": str(SCENARIOS_FILE),
            "results": results,
        }
        with open(run_file, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    for i, scenario in enumerate(scenarios, 1):
        sid = scenario["id"]

        if sid in already_scored:
            print(c(f"  [skip] {sid} — already scored", DIM))
            continue

        print_scenario_header(scenario, i, total)

        result = run_scenario(scenario, interactive=interactive)
        results.append(result)
        save()  # auto-save after every scenario

    print_summary(results)
    print(c(f"\n  Results saved to: {run_file}", DIM))


if __name__ == "__main__":
    main()
