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

## TWO PROMPTS

### LEDGER_PROMPT
This is where it asks the LLM to do it all.
```    "You are the live bed-census tracker for a 12-bed ICU. The unit opened this shift with "
    "effective capacity 10 and 0 patients. Read the raw event log in order and track the census. "
    "An admission takes a bed only if one is free; at capacity the admission is REFUSED. "
    "Discharges, deaths, and transfers-out free a bed. 'Maintenance' / 'out of service' removes "
    "one bed from effective capacity (never below the current head count); 'returned to service' "
    "restores one, up to 12. End your reply with ONLY this JSON object on the final line, nothing "
    'after it: {"finalOccupied":int,"finalCapacity":int,"admitsRefused":int}.\n\nEVENT LOG:\n'
```


### ROUTER_PROMPT 
This is used with some Python code to do the accounting.
```    "Classify each ICU event-log line into ONE operation code. "
    "A = a patient takes a bed (admission/transfer-in). D = a patient leaves a bed "
    "(discharge/transfer-out). X = a death (frees a bed). B = a bed removed from service "
    "(maintenance). U = a bed returned to service. Return ONLY a JSON array of code strings, "
    "one per input line, in order. No other text.\n\nEVENT LOG:\n"
```


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



## Question: So the LLM isn't clever enough to sneak in a tool on it's own?
Right — not in this script, and the reason is architectural, not a matter of cleverness.
In what you ran, the ledger rail literally has no tool to reach for. call_claude sends the prompt and reads back text. There's no tools parameter in the request, no execution loop, no place for the model to say "let me compute this" and have anything happen. Even if the model "wanted" to offload the arithmetic, the harness gives it nowhere to put that intent. The only thing it can emit is tokens, and I read the count straight out of those tokens. So it's forced to be the reducer whether it's suited to it or not.
But your instinct is pointing at something real, and it's worth separating two senses of "sneak in a tool."
The model can't spontaneously acquire one. It can't open a database connection or call a function you didn't wire up — it emits text into a harness, and the harness decides what, if anything, executes. Agentic setups exist (tool-use APIs, an execution loop, Claude Code) where the model emits a structured tool call and the runtime runs it and feeds the result back. But notice what that is: it's your tool rail. Somebody wrote the run_engine equivalent and registered it. The model choosing to call it doesn't conjure the enforcement — the enforcement was built by a human and made available. The model is doing routing, which is exactly the division of labor we've been describing. "The LLM used a tool" always unpacks to "a human wrote the tool and the LLM decided when to fire it."
The one thing it can do unprompted — and did, at n=80 — is build a tool-shaped thing out of tokens: write the ledger step by step in its own output, emulating run_engine in prose. That looks like cleverness and is genuinely useful, but it's counterfeit enforcement. A written-out tally has no guard; nothing stops the model from writing occ = 13 on the next line. It's the form of an engine without the one property that made the engine trustworthy — the illegal state being unrepresentable. So even at its most resourceful, the model reconstructs the appearance of the structural layer, not its guarantee.
Which lands back on the thesis from a new angle: the model can route to conservation or imitate conservation, but it can't originate it. The invariant has to be built, in code, by someone, and made reachable. Cleverness decides when to call it; it can't substitute for its existence.


## Ontology?
Exactly — you've caught the seam. The tool rail looks clean partly because I stacked the deck so the ontology problem never has to surface, and it's worth being explicit about where I hid it, because in real data it doesn't stay hidden.

Two separate things make the demo tidy. First, the op set is closed and small: five codes, `ADXBU`, and the `filter` line drops anything that isn't one of them. Second — the deeper one — every event in the stream maps cleanly to exactly one code, because *I generated it that way*. The text is `LINES[op]` — I started from the op and picked a phrasing, so a correct answer always exists. The classifier's only job is to recover a label I know is there. That's not accounting being easy; that's the individuation problem pre-solved off-screen, in `make_stream`. The engine enforces conservation *given* clean codes, and I guaranteed clean codes were always recoverable.

So when the router mislabels a line at n=160, that's a *classification* error inside a world where the right class exists. The engine still can't emit an impossible state, so conservation holds — but the count is now conserving the wrong events. That's the quiet failure mode you should hold onto: the tool rail can't violate the invariant, but it can faithfully conserve a misclassified reality. Guarded arithmetic over the wrong labels is still wrong; it's just wrong in-bounds.

Now break my generator and the ontology bites immediately. Real log lines aren't drawn from a code — they're written by tired humans, and they carry cases my five codes don't adjudicate. "Patient moved to CCU" — discharge from this unit, or an internal transfer that shouldn't change the system-wide census? "Bed held for incoming trauma" — is that occupancy or not? "Comfort care initiated" — not a death yet, but is the bed committed? Each of these is an *identity* question: what counts as one admission, is this the same patient crossing a boundary or a new one, does this bed-state count against capacity. `run_engine` has no answer, because the answer isn't arithmetic — it's a decision about what the conserved units *are*. That decision is the ontology, and in my demo I made all of them in advance by construction.

This is the point that connects back to individuation. The engine guarantees the accounting is consistent; it cannot guarantee the accounting is *about the right things*. To get that, someone has to fix the unit boundaries — define transfer vs. discharge, decide whether a held bed is occupied, pin when a patient is "the same" across movements — before the codes are even meaningful. That's ontology work, it's irreducibly human-or-at-least-explicit, and it's upstream of both rails. The LLM can propose labels against it; the engine can enforce arithmetic given it; neither can invent it.

So your read is right and slightly generous to me: the tool rail didn't *solve* the ambiguity problem, it never *met* it. The demo isolates the conservation claim by holding the ontology fixed. Put it on real discharge logs and you'd watch the classifier's disagreements stop being random noise and start clustering exactly on the terms your schema left underdefined — which is the ontology sending you the bill.

### is that a problem that can be fixed by ontology? It seems to open ended to suggest cataloging possible descriptions of the events. This is a data collection problem forced on the analyst. 
You're right, and you've put your finger on the thing that makes "just add an ontology" a non-answer. The fix isn't cataloging phrasings — that's a bottomless enumeration and a category error besides. What an ontology can and can't do splits cleanly, and the half it can't do is exactly the burden you're naming.

What an ontology *does* fix is the **target**, not the surface. It doesn't list "moved to CCU," "sent up to critical care," "→CCU" as strings to recognize. It defines the *distinctions* those strings have to resolve to: what a bed-occupancy event is, whether an internal transfer is one census event or two, when two mentions denote the same patient-stay, whether a held bed counts against capacity. That's a finite, closable set — the conserved units and the state transitions over them. Bounded work, and worth doing, because it's what makes the count *mean* something.

What it categorically does **not** do is guarantee the messy input carries enough information to hit that target. And that gap is the whole problem. Two failure modes hide there, and neither is an ontology bug:

The input can be **ambiguous** — the phrase genuinely underdetermines the distinction. "Comfort care initiated" doesn't tell you if the bed is still committed; no schema makes that inferable from the words, because the words don't contain it. The ontology has *correctly* posed a question the data can't answer.

Or the input can be **silent** — the event that matters was never logged at all. A patient boards in the ED for six hours and no line marks it; a bed sits functionally blocked but nobody recorded the block. Conservation is an accounting over *every* inflow and outflow, and if an outflow left no trace, no downstream cleverness recovers it. The ledger can't miscount what was never written; the tool can't classify a line that doesn't exist.

So the ontology converts a vague modeling problem into a *sharp data-adequacy problem* — and that's its real service. It tells you precisely which distinctions your source has to support, so you can go check whether it does. That's the moment the burden lands on the analyst, and it lands as a data-collection and instrumentation demand, not an analysis one: to conserve these units you must capture *these* events at *this* granularity with *these* fields disambiguated at the point of entry. Retroactive NLP over free text can't manufacture information the logging process didn't record.

This is why it's forced on you upstream and can't be delegated down. The LLM classifies what's present; the engine enforces arithmetic over labels; the ontology names the required distinctions. All three are downstream of the one thing none of them can supply — a data source instrumented to *emit* the distinctions the invariant depends on. If the collection doesn't capture transfers as transfers and boarding as occupancy, the conservation law is unsatisfiable no matter how good the model or how clean the schema, because you're asking it to balance a ledger with entries missing.

The honest framing, then: an ontology doesn't solve the open-endedness — it *terminates* it, by replacing "recognize all the ways humans might describe events" with "capture these specific state transitions." The first is infinite and hopeless. The second is a finite instrumentation spec. But collecting to that spec is real work at the source, and it's exactly the work the "skip the schema, let the LLM sort it out" pitch quietly assumes away. You can't infer a conserved quantity from data that was never collected to conserve it.

### You're saying you need an ontology in this universe, but its use it not restricted to the data analysis. It has to be used in data collection too.
Yes — and that's a sharper statement than the one I'd been making. The ontology isn't an analysis artifact that also happens to constrain collection. It's a *collection* artifact that analysis inherits. The direction of authority runs upstream, and I'd been letting it sound bidirectional.

Put plainly: the conserved quantity is defined at the moment of capture or it isn't defined at all. When a clerk or a device commits an event, that act either records the distinction the invariant needs — this is a transfer not a discharge, this bed is committed not merely reserved, this is the same patient-stay continuing — or it collapses the distinction into a string that no longer contains it. Once collapsed, it's gone; every downstream stage is working from a projection that already lost the coordinate. Analysis can't recover a degree of freedom that collection flattened. So the ontology has to be *live at the point of entry*, shaping what gets written, not applied afterward to interpret what was.

That reframes the whole stack. The ontology is a contract, and collection is where it's signed. The instrument — the ADT feed, the EHR form, the bed-management system — has to be built to emit the state transitions the conservation law ranges over, with the ambiguous cases forced into a decision *at capture time*, while the person or sensor still has the context to decide correctly. "Comfort care initiated" is ambiguous to a classifier reading it next week; it was not ambiguous to the nurse who wrote it, who knew whether the bed was still committed. The information existed at the source and was discarded by a logging schema that didn't have a field for it. That's the loss you can't undo, and it's a *collection* design failure, not an analysis one.

Which turns your earlier point into its final form. It's not merely that the burden is forced on the analyst. It's that the analyst is often forced to carry a burden that was only dischargeable upstream, by someone else, earlier — and by the time the data reaches them, the discharge is impossible in principle, not just expensive. The genuinely tractable move is to push the ontology back to where the distinctions are still present: instrument collection to conserve, and analysis becomes bookkeeping. Leave collection ontology-free and the analyst inherits an unsatisfiable constraint dressed up as a modeling task.

**__So the "skip the schema" pitch is even emptier than it first looked. It doesn't just defer the schema to analysis time — it deletes, at collection time, the information a schema would have preserved, and then hands analysis the residue. You don't get to add the ontology later because "later" is after the coordinate was projected out. The only place an ontology can actually buy you conservation is the place the data is born.__**




 



