# llm_reasoning

Without having read the Python myself yet, does that mean that the resources being counted need clear unambiguous identifiers?


Close, but let me split it, because the answer is "yes" at one level and "more than you need" at another — and the seam between them is exactly the interesting part.

What's actually non-negotiable is a **crisp identity criterion**: you must be able to say unambiguously what counts as one unit, what the conserved total is, and when two mentions refer to the same unit. Unique identifiers are how you *implement* that, but there are two tiers of how much identity you need:

For **additive/quantity conservation** — occupied + free = capacity, a stock that equals inflow minus outflow — you don't need per-unit labels. You need well-defined, countable, fungible units and a sharp boundary. An integer count against a capacity is enough. Worth saying since you haven't read it yet: my demo is this weaker tier. It tracks occupancy as an integer and never assigns patient→bed; there's no `bed_7`. That suffices to enforce the capacity bound.

For **assignment / exclusivity conservation** — this nurse can't be in two units at once, this bed holds one patient, this dollar is spent once — you *do* need stable per-unit identifiers. You cannot enforce "at most once" without being able to recognize that it's the same one in both places it might be double-counted. My demo doesn't do this, and couldn't without introducing IDs.

So the requirement scales with the constraint. Pure quantity → crisp countability. "Who has which," no-double-booking, provenance → genuine individuation with identifiers.

And this is precisely the ontology re-entering, which is why your instinct is right. An identity criterion *is* an ontological commitment. Embeddings avoid the ontology by replacing identity with graded similarity — "close" never requires "same." Conservation requires "same," or at minimum "exactly one, bounded, countable." That's the thing softness gives up.

The place it bites in real hospital data: the units are often fuzzy. Is a physically-present but unstaffed bed a bed? Is a float nurse one resource or fractional across units? Those are identity questions, and if you leave them ambiguous the conservation law itself becomes ill-posed — you can't conserve a quantity whose unit boundary you haven't fixed. The work of sharpening them into countable, individuated units is the ontology work, and it's the part you cannot delegate to the embedding. You can let the embedding carry acuity or case-mix similarity; you cannot let it decide what one bed is.