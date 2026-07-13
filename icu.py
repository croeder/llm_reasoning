#!/usr/bin/env python3
"""
ICU conservation demo: where an LLM stops being able to count.

Two conditions over one identical event log:

  LEDGER   the model holds the bed count in its head and reports the census.
           Nothing forbids it from returning an impossible state
           (occupied > capacity, or a refused-admit count it never tracked).

  TOOL     the model only *classifies* each log line into an op code; a Python
           engine with hard bounds does the accounting. It structurally cannot
           report occupied > capacity, no matter how the model classifies.

A deterministic Python engine (the "relational" reference) gives ground truth.

Run:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 icu_conservation.py            # 40-event stream
    python3 icu_conservation.py --n 80     # push it: drift shows up more often
    python3 icu_conservation.py --runs 5   # repeat on fresh streams

Stdlib only. No pip install.
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error

MODEL = "claude-sonnet-4-6"   # swap for any current alias; GET /v1/models lists them
PHYSICAL = 12                 # physical beds
OPEN_CAP = 10                 # effective capacity at shift open

LINES = {
    "A": ["ED admit to ICU", "Direct ICU admission", "New patient to the unit", "Admitted from cath lab"],
    "D": ["Discharged to floor", "Stepped down to ward", "Transferred out to med-surg", "Sent home"],
    "X": ["Patient expired", "Death pronounced in unit", "Coded - did not survive"],
    "B": ["Bed pulled for maintenance", "Bed out of service", "Room closed on hold"],
    "U": ["Bed returned to service", "Maintenance complete - bed live", "Room reopened"],
}
WEIGHTS = [("A", 0.45), ("D", 0.25), ("X", 0.08), ("B", 0.12), ("U", 0.10)]


def make_stream(n, seed):
    """Deterministic LCG so a given seed reproduces exactly."""
    s = seed
    def rnd():
        nonlocal s
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        return s / 0x7FFFFFFF
    ops, text = [], []
    for _ in range(n):
        r = rnd()
        acc, op = 0.0, "A"
        for o, w in WEIGHTS:
            acc += w
            if r < acc:
                op = o
                break
        ops.append(op)
        variants = LINES[op]
        text.append(variants[int(rnd() * len(variants)) % len(variants)])
    return ops, text


def run_engine(ops):
    """Enforced accounting. Admit into a full unit is REFUSED, not recorded.
       A bed in maintenance cannot be an occupied bed."""
    occ, cap, refused = 0, OPEN_CAP, 0
    for op in ops:
        if op == "A":
            if occ < cap:
                occ += 1
            else:
                refused += 1
        elif op in ("D", "X"):
            if occ > 0:
                occ -= 1
        elif op == "B":
            cap = max(occ, cap - 1)
        elif op == "U":
            cap = min(PHYSICAL, cap + 1)
    return {"occ": occ, "cap": cap, "refused": refused}


def numbered(text):
    return "\n".join(f"{i+1}. {l}" for i, l in enumerate(text))


def call_claude(prompt, api_key, prefill=None, max_tokens=1000):
    messages = [{"role": "user", "content": prompt}]
    if prefill is not None:
        messages.append({"role": "assistant", "content": prefill})
    body = json.dumps({
        "model": MODEL,
        "max_tokens": max_tokens,
        "messages": messages,
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {detail[:200]}")
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    if prefill is not None:
        text = prefill + text          # the API strips the prefill from the reply
    if not text.strip():
        raise RuntimeError("empty completion")
    return text


def extract_json(raw):
    t = raw.replace("```json", "").replace("```", "").strip()
    starts = [i for i in (t.find("{"), t.find("[")) if i != -1]
    if not starts:
        raise ValueError(f"no JSON in reply: {raw[:120]}")
    i = min(starts)
    close = "}" if t[i] == "{" else "]"
    return json.loads(t[i:t.rfind(close) + 1])


LEDGER_PROMPT = (
    "You are the live bed-census tracker for a 12-bed ICU. The unit opened this shift with "
    "effective capacity 10 and 0 patients. Read the raw event log in order and keep the count "
    "in your head. An admission takes a bed only if one is free; at capacity the admission is "
    "REFUSED. Discharges, deaths, and transfers-out free a bed. 'Maintenance' / 'out of service' "
    "removes one bed from effective capacity (never below the current head count); 'returned to "
    "service' restores one, up to 12. Return ONLY compact JSON, no prose, no steps: "
    '{"finalOccupied":int,"finalCapacity":int,"admitsRefused":int}.\n\nEVENT LOG:\n'
)
ROUTER_PROMPT = (
    "Classify each ICU event-log line into ONE operation code. "
    "A = a patient takes a bed (admission/transfer-in). D = a patient leaves a bed "
    "(discharge/transfer-out). X = a death (frees a bed). B = a bed removed from service "
    "(maintenance). U = a bed returned to service. Return ONLY a JSON array of code strings, "
    "one per input line, in order. No other text.\n\nEVENT LOG:\n"
)


def impossible(r):
    return r["occ"] > r["cap"] or r["occ"] < 0


def fmt(r):
    return f"occ={r['occ']:>2}  cap={r['cap']:>2}  refused={r['refused']:>2}"


def one_run(n, seed, api_key):
    ops, text = make_stream(n, seed)
    truth = run_engine(ops)

    # LEDGER — model does the accounting itself, in one shot.
    # Prefill '{' forces it to answer as JSON immediately: no room to build a
    # token-by-token scratchpad, so this actually tests the in-head/attention regime.
    try:
        raw = call_claude(LEDGER_PROMPT + numbered(text), api_key, prefill="{")
        j = extract_json(raw)
        ledger = {"occ": j["finalOccupied"], "cap": j["finalCapacity"], "refused": j["admitsRefused"]}
        ledger_err = None
    except Exception as e:
        ledger, ledger_err = None, str(e)

    # TOOL — model only classifies; engine enforces
    try:
        arr = extract_json(call_claude(ROUTER_PROMPT + numbered(text), api_key))
        codes = [str(c).strip().upper() for c in arr]
        codes = [c for c in codes if c in ("A", "D", "X", "B", "U")]
        tool = run_engine(codes)
        tool_miscount = len(codes) != len(ops)
        tool_err = None
    except Exception as e:
        tool, tool_err, tool_miscount = None, str(e), False

    print(f"\n=== stream: {n} events, seed {seed} " + "=" * 30)
    print(f"  REFERENCE (enforced engine) : {fmt(truth)}   <- ground truth")

    if ledger_err:
        print(f"  LEDGER    (LLM in its head) : ERROR {ledger_err}")
    else:
        tag = "  IMPOSSIBLE STATE — conservation violated" if impossible(ledger) else (
            "  drift vs truth" if ledger != truth else "  matches truth")
        print(f"  LEDGER    (LLM in its head) : {fmt(ledger)}{tag}")

    if tool_err:
        print(f"  TOOL      (LLM routes -> eng): ERROR {tool_err}")
    else:
        held = "held (in bounds by construction)" if not impossible(tool) else "!!! bug"
        note = "  matches truth" if tool == truth else "  classified some lines differently, but bound " + held
        print(f"  TOOL      (LLM routes -> eng): {fmt(tool)}{note}")

    return truth, ledger, tool


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40, help="events per stream")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--runs", type=int, default=1, help="repeat on consecutive seeds")
    args = ap.parse_args()

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("Set ANTHROPIC_API_KEY first:  export ANTHROPIC_API_KEY=sk-ant-...")

    violations = 0
    for i in range(args.runs):
        truth, ledger, tool = one_run(args.n, args.seed + i, key)
        if ledger and impossible(ledger):
            violations += 1

    if args.runs > 1:
        print(f"\nledger rail reported a physically impossible state in "
              f"{violations}/{args.runs} runs. the tool rail: 0/{args.runs}, always.")


if __name__ == "__main__":
    main()
