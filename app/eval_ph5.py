# PURPOSE OF THE FILE -- EVALUATION: is the agent actually RIGHT, and how fast?
#
# Phase 3 already measures speed (timings, X-Process-Time). Speed means
# nothing if the answer is wrong, so this script asks the Phase 2 agent a
# fixed list of test questions (eval/eval_questions.json) and scores each one:
#
#   tool_ok    - did it call exactly the tool(s) it should have?
#   sources_ok - did the expected source file(s)/index show up in `sources`?
#   mention_ok - does the answer contain at least one expected key word?
#                (a ROUGH check - a quick signal, not proof the answer is good)
#   seconds    - how long the whole agent run took
#
# It calls the agent DIRECTLY in Python, not through the HTTP API. That
# skips the Redis + semantic caches (a cached answer would hide the real
# tool choice and real time) and keeps test runs out of the audit log.
#
# Usage (venv active, Elasticsearch + Ollama running):
#   python -m app.eval_ph5 --seed        # one-time: load test log lines (see below)
#   python -m app.eval_ph5               # run all questions
#   python -m app.eval_ph5 --only log    # run only ids starting with "log"
#
# Compare models (PowerShell):
#   $env:CHAT_MODEL="llama3.2"; python -m app.eval_ph5; Remove-Item Env:CHAT_MODEL
#
# Each run saves a full report to eval/results/<model>_<time>.json.

import argparse
import json
import os
import time
from datetime import datetime, timezone

from . import config_ph1 as config

QUESTIONS_FILE = os.path.join("eval", "eval_questions.json")
RESULTS_DIR = os.path.join("eval", "results")
MOCK_LOGS_FILE = os.path.join("sample_logs", "mock_logs.json")
SEED_SOURCE = "mock_logs_seed"


# ---------------------------------------------------------------------------
# Seeding. Since Phase 4, search_logs reads the live-alerts index, not
# sample_logs/mock_logs.json - so the test hosts (WKSTN-042, WKSTN-017, ...)
# don't exist there unless we put them in. This files each mock log line
# into security_live_alerts with a FIXED document id, so running --seed
# twice overwrites instead of creating duplicates.
# ---------------------------------------------------------------------------


def seed_mock_logs():
    from .alerts_ph4 import ensure_alerts_index
    from .embeddings_ph1 import embed_text
    from .es_client_ph1 import get_client

    es = get_client()
    ensure_alerts_index(es)

    with open(MOCK_LOGS_FILE, "r", encoding="utf-8") as f:
        entries = json.load(f)

    for i, entry in enumerate(entries):
        text = f"[{entry['host']}] {entry['event']}"
        es.index(
            index=config.ES_ALERTS_INDEX,
            id=f"{SEED_SOURCE}::{i}",
            document={
                "text": text,
                "embedding": embed_text(text),
                "source": SEED_SOURCE,
                "chunk_id": f"{SEED_SOURCE}::{i}",
                "received_at": entry["timestamp"],
            },
        )
        print(f"  seeded: {text[:80]}")

    es.indices.refresh(index=config.ES_ALERTS_INDEX)
    print(f"Done. {len(entries)} log lines in '{config.ES_ALERTS_INDEX}' (source='{SEED_SOURCE}').")


# ---------------------------------------------------------------------------
# Running one question through the agent and reading what it did.
# ---------------------------------------------------------------------------


def tools_called(messages) -> list[str]:
    """Tool names in the order the model asked for them."""
    names = []
    for msg in messages:
        for call in getattr(msg, "tool_calls", None) or []:
            names.append(call["name"])
    return names


def sources_from(messages) -> list[str]:
    """Same source-collection logic as agent_ph2.ask_agent()."""
    sources = set()
    for msg in messages:
        tool_name = getattr(msg, "name", None)
        if tool_name == "search_knowledge_base":
            for line in msg.content.splitlines():
                if line.startswith("[Source: "):
                    sources.add(line[len("[Source: ") : -1])
        elif tool_name == "search_logs":
            if not msg.content.startswith("No log entries found"):
                sources.add(config.ES_ALERTS_INDEX)
    return sorted(sources)


def score(case: dict, tools: list[str], sources: list[str], answer: str) -> dict:
    tool_ok = set(tools) == set(case["expected_tools"])

    expected_sources = case.get("expected_sources")
    sources_ok = None if expected_sources is None else set(expected_sources) <= set(sources)

    lowered = answer.lower()
    mention_ok = any(word.lower() in lowered for word in case["answer_mentions_any"])

    return {"tool_ok": tool_ok, "sources_ok": sources_ok, "mention_ok": mention_ok}


def run_case(agent, case: dict) -> dict:
    start = time.perf_counter()
    try:
        result = agent.invoke({"messages": [("user", case["question"])]})
    except Exception as exc:
        return {
            **case,
            "error": str(exc)[:300],
            "seconds": round(time.perf_counter() - start, 1),
            "tool_ok": False,
            "sources_ok": None if case.get("expected_sources") is None else False,
            "mention_ok": False,
        }
    seconds = round(time.perf_counter() - start, 1)

    messages = result["messages"]
    tools = tools_called(messages)
    sources = sources_from(messages)
    answer = messages[-1].content or ""

    return {
        **case,
        "tools_called": tools,
        "sources_returned": sources,
        "answer": answer,
        "seconds": seconds,
        **score(case, tools, sources, answer),
    }


# ---------------------------------------------------------------------------
# Report.
# ---------------------------------------------------------------------------


def mark(value) -> str:
    return "-" if value is None else ("PASS" if value else "FAIL")


def summarize(results: list[dict]) -> dict:
    def rate(key):
        scored = [r[key] for r in results if r[key] is not None]
        return f"{sum(scored)}/{len(scored)}" if scored else "n/a"

    by_category = {}
    for r in results:
        cat = by_category.setdefault(r["category"], {"total": 0, "tool_ok": 0})
        cat["total"] += 1
        cat["tool_ok"] += int(r["tool_ok"])

    times = [r["seconds"] for r in results]
    return {
        "tool_routing_correct": rate("tool_ok"),
        "sources_correct": rate("sources_ok"),
        "answer_mentions_key_fact": rate("mention_ok"),
        "tool_routing_by_category": {k: f"{v['tool_ok']}/{v['total']}" for k, v in by_category.items()},
        "avg_seconds": round(sum(times) / len(times), 1) if times else 0,
        "max_seconds": max(times) if times else 0,
        "errors": sum(1 for r in results if "error" in r),
    }


def print_report(results: list[dict], summary: dict):
    print()
    print(f"{'id':<10} {'tools':<6} {'sources':<8} {'mention':<8} {'secs':>6}  tools called")
    print("-" * 78)
    for r in results:
        called = ", ".join(r.get("tools_called", [])) or ("ERROR" if "error" in r else "(none)")
        print(
            f"{r['id']:<10} {mark(r['tool_ok']):<6} {mark(r['sources_ok']):<8} "
            f"{mark(r['mention_ok']):<8} {r['seconds']:>6}  {called}"
        )
    print("-" * 78)
    print(f"Model:                     {config.CHAT_MODEL}")
    print(f"Tool routing correct:      {summary['tool_routing_correct']}   {summary['tool_routing_by_category']}")
    print(f"Sources correct:           {summary['sources_correct']}")
    print(f"Answer mentions key fact:  {summary['answer_mentions_key_fact']}   (rough keyword check)")
    print(f"Time per question:         avg {summary['avg_seconds']}s, max {summary['max_seconds']}s")
    if summary["errors"]:
        print(f"Errors:                    {summary['errors']} (see the results file)")


def main():
    parser = argparse.ArgumentParser(description="Evaluate the SentinelCopilot agent.")
    parser.add_argument("--seed", action="store_true", help="load sample_logs/mock_logs.json into the live-alerts index, then exit")
    parser.add_argument("--only", default="", help="run only question ids starting with this text, e.g. 'log' or 'both'")
    args = parser.parse_args()

    if args.seed:
        seed_mock_logs()
        return

    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        cases = [c for c in json.load(f) if c["id"].startswith(args.only)]
    if not cases:
        print(f"No questions match --only '{args.only}'.")
        return

    # Imported here, not at the top, so `--seed` works even if the agent's
    # dependencies or the chat model aren't ready yet.
    from .agent_ph2 import agent

    print(f"Running {len(cases)} question(s) with model '{config.CHAT_MODEL}' - local models can take ~1-3 min each.\n")
    results = []
    for n, case in enumerate(cases, start=1):
        print(f"[{n}/{len(cases)}] {case['id']}: {case['question']}")
        result = run_case(agent, case)
        print(
            f"         tools={mark(result['tool_ok'])} sources={mark(result['sources_ok'])} "
            f"mention={mark(result['mention_ok'])} ({result['seconds']}s)"
        )
        results.append(result)

    summary = summarize(results)
    print_report(results, summary)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe_model = config.CHAT_MODEL.replace(":", "-").replace("/", "-")
    out_path = os.path.join(RESULTS_DIR, f"{safe_model}_{stamp}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"model": config.CHAT_MODEL, "run_at": stamp, "summary": summary, "results": results}, f, indent=2)
    print(f"\nFull report (with every answer): {out_path}")


if __name__ == "__main__":
    main()
