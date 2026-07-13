# llm_reasoning

This is a Claude project to compare LLM accounting to that of a proper tool. The context is a stream of events in a hosptial ICU and the task is to keep track of limited resources over that event stream. Claude wrote some python code to implement this in three ways: pure python, llm and assisted llm.  The llm drifts a bit.

## "Without having read the Python myself yet, does that mean that the resources being counted need clear unambiguous identifiers?"


Close, but let me split it, because the answer is "yes" at one level and "more than you need" at another — and the seam between them is exactly the interesting part.

What's actually non-negotiable is a **crisp identity criterion**: you must be able to say unambiguously what counts as one unit, what the conserved total is, and when two mentions refer to the same unit. Unique identifiers are how you *implement* that, but there are two tiers of how much identity you need:

For **additive/quantity conservation** — occupied + free = capacity, a stock that equals inflow minus outflow — you don't need per-unit labels. You need well-defined, countable, fungible units and a sharp boundary. An integer count against a capacity is enough. Worth saying since you haven't read it yet: my demo is this weaker tier. It tracks occupancy as an integer and never assigns patient→bed; there's no `bed_7`. That suffices to enforce the capacity bound.

For **assignment / exclusivity conservation** — this nurse can't be in two units at once, this bed holds one patient, this dollar is spent once — you *do* need stable per-unit identifiers. You cannot enforce "at most once" without being able to recognize that it's the same one in both places it might be double-counted. My demo doesn't do this, and couldn't without introducing IDs.

So the requirement scales with the constraint. Pure quantity → crisp countability. "Who has which," no-double-booking, provenance → genuine individuation with identifiers.

And this is precisely the ontology re-entering, which is why your instinct is right. An identity criterion *is* an ontological commitment. Embeddings avoid the ontology by replacing identity with graded similarity — "close" never requires "same." Conservation requires "same," or at minimum "exactly one, bounded, countable." That's the thing softness gives up.

The place it bites in real hospital data: the units are often fuzzy. Is a physically-present but unstaffed bed a bed? Is a float nurse one resource or fractional across units? Those are identity questions, and if you leave them ambiguous the conservation law itself becomes ill-posed — you can't conserve a quantity whose unit boundary you haven't fixed. The work of sharpening them into countable, individuated units is the ontology work, and it's the part you cannot delegate to the embedding. You can let the embedding carry acuity or case-mix similarity; you cannot let it decide what one bed is.


## RUN 1 odd output at n=80
=== stream: 80 events, seed 10 ==============================
  REFERENCE (enforced engine) : occ=11  cap=12  refused= 7   <- ground truth
  LEDGER    (LLM in its head) : ERROR no JSON in reply: I'll track state: occupied (O), capacity (C), refused (R)

Start: O=0, C=10, R=0

1. Admit: O=1,C=10
2. Admit: O=2,C=10

  TOOL      (LLM routes -> eng): occ=11  cap=12  refused= 7  matches truth


That output is the thesis happening in front of you, not a bug — but you're right that it's "strange," and the reason is worth unpacking because it's actually the sharpest result you've gotten.
Ground truth on that stream is a badly saturated unit: capacity squeezed to 2, occupancy 2, 19 admits refused. The TOOL rail nailed all three exactly, because the engine enforces. The LEDGER rail didn't drift — it refused to answer in one shot. Look at what it started emitting: "I need to track occupied beds... Start: occupied=0, capacity=10... 1." It began writing out a step-by-step ledger, then hit the 1000-token cap before reaching event 80 and never emitted the JSON. My extractor found no JSON → error.
That's the model doing exactly the thing we said it would. Faced with 80 events it can't hold in its head, it reached for a scratchpad — reconstructing a symbolic ledger in tokens, which is the relational model sneaking back in. It knows it can't conserve by attention alone. So the n=80 "error" is stronger evidence than a drift number would have been: forced to conserve over a long stream, the in-head approach abandons "in head" and starts rebuilding the structural layer by hand.
But it also means the LEDGER condition wasn't cleanly testing what it claims to. The model escaped into a scratchpad, so you saw truncation instead of drift. The experimentally correct way to test "in its head" is to deny it the scratchpad — force it to answer in the pure-attention regime. The clean way to do that is an assistant prefill: seed the reply with { so the model must continue as JSON immediately, with no room to reason first. Let me apply that.


## Run 2 (v2) fails
"This model does not support assistant message prefill. The conversation must end with a user message."


## Run 3 icu2.py
Claude rewrote the code, describing it:

That model dropped support for assistant prefill — the request has to end on a user turn. So I can't force the single-shot regime that way. Let me take a different, model-agnostic approach: remove the prefill, let the model reason if it insists (with enough token budget that it can't truncate mid-thought), and extract the final JSON. Then give you a command-line knob to squeeze the token budget yourself when you want to induce drift.Diagnosed file synchronization conflicts across directoriesDiagnosed file synchronization conflicts across directoriesLet me consolidate — I edited the wrong copy. Making /home/claude authoritative:Refactored label terminology and located replacement instancesRefactored label terminology and located replacement instancesNow verify syntax, the extractor against reasoning-then-JSON, and the request shape, then copy over the outputs file:Ran a command, read a fileRan a command, read a fileFixed and verified. The prefill is gone (your model rejects it), the extractor now skips any reasoning and grabs the final JSON, and there's a token budget big enough that the ledger call won't truncate mid-thought.
Two ways to run it now, and they test different rungs:
python3 icu_conservation.py --n 80 --seed 11 — generous budget. The model is free to reason, which on a hard stream means it rebuilds the ledger step by step in tokens. It'll often come out close or correct — and that's the point worth seeing,

### no-env:llm_reasoning:main...origin/main>python3 icu2.py --runs 5 --n 80

=== stream: 80 events, seed 7 ==============================
  REFERENCE (enforced engine)    : occ= 9  cap=10  refused= 4   <- ground truth
  LEDGER    (LLM does the count) : occ= 9  cap=10  refused= 4  matches truth
  TOOL      (LLM routes -> eng)  : occ= 9  cap=10  refused= 4  matches truth

=== stream: 80 events, seed 8 ==============================
  REFERENCE (enforced engine)    : occ=11  cap=11  refused=11   <- ground truth
  LEDGER    (LLM does the count) : occ=11  cap=11  refused=11  matches truth
  TOOL      (LLM routes -> eng)  : occ=11  cap=11  refused=11  matches truth

=== stream: 80 events, seed 9 ==============================
  REFERENCE (enforced engine)    : occ=12  cap=12  refused= 8   <- ground truth
  LEDGER    (LLM does the count) : occ=11  cap=12  refused= 9  drift vs truth
  TOOL      (LLM routes -> eng)  : occ=12  cap=12  refused= 8  matches truth

=== stream: 80 events, seed 10 ==============================
  REFERENCE (enforced engine)    : occ=11  cap=12  refused= 7   <- ground truth
  LEDGER    (LLM does the count) : occ=11  cap=12  refused= 7  matches truth
  TOOL      (LLM routes -> eng)  : occ=11  cap=12  refused= 7  matches truth

=== stream: 80 events, seed 11 ==============================
  REFERENCE (enforced engine)    : occ= 2  cap= 2  refused=19   <- ground truth
  LEDGER    (LLM does the count) : occ= 3  cap= 3  refused=17  drift vs truth
  TOOL      (LLM routes -> eng)  : occ= 2  cap= 2  refused=19  matches truth

ledger rail reported a physically impossible state in 0/5 runs. the tool rail: 0/5, always.


