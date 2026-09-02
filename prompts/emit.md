# Emission prompt

Turns the analysis from `prompts/extract.md` into installable agent skills.

---

Write one skill per content mode that had enough data to support it. Skip any
mode that didn't — a thin skill is worse than no skill, because the writer
trusts it.

Each skill is a directory:

```
<skill-name>/
  SKILL.md          the method
  swipe-file.md     annotated real examples from the corpus
```

Voice lives in its own file per creator, because a writer picks a structure and
a voice separately — and because two voices must never be merged into one:

```
voice-<handle>.md   one creator's derived voice layer
```

You do not write these from impression. `data/<handle>/voice.md` is generated
by `bin/voice.py` and already contains measured dials, signature phrases, and
real exemplar lines. Carry it across; do not paraphrase it.

## SKILL.md rules

**Frontmatter.** `name` and a `description` that states when to use this skill
and — critically — when to use a *different* one. Three sibling skills that
don't disambiguate each other will be invoked at random.

**Lead with the return format.** State the exact sections the skill must output
and forbid everything else. A script skill that returns camera directions,
runtime math, and word counts nobody asked for is a worse skill. Name the
failure mode explicitly: "if you catch yourself writing prose without the
headings, stop and restart."

**One angle before drafting.** Force the writer to finish a single sentence
about what this specific video is arguing before a line gets written. Most
weak short-form is weak because it has two arguments.

**Topic playbook.** Before any structure advice, the skill states what this
mode is *about*. Take the REPLICATED subjects from `signals-<mode>.md` as
standing territory, the SINGLE ones as labelled bets, and the underperforming
ones as an explicit avoid-list — that half is usually more useful and is
usually the half that gets dropped.

Write territory, never sentences. "Open-source tooling and what it replaces"
is territory the writer fills with their own material. "China just released
another AI video model" is somebody's actual reel and putting it in a skill is
how you ship a knock-off. If a line in your topic section could be read aloud
as-is, delete it and write the category instead.

**Hook playbook.** The archetypes from the analysis, each with its name, what
it *does to the viewer*, and when it applies. Include the banned openings — the
ones that appeared in controls at the same rate as winners, and the generic
ones ("Welcome to", "Check out this", "In this video").

Examples go in `swipe-file.md`, not in `SKILL.md`, and they are labelled **for
recognition, not reuse**. The shape is the transferable part; the sentence
belongs to the person who already has the audience for it. A skill that hands
the writer a hook to paste has quietly changed jobs from teaching a craft to
laundering someone's work.

**Beat map with real numbers.** The timings from the analysis, as a target the
writer works against. Say where the payoff lands and where the CTA starts.

**Say what is evidence and what is inference.** Where the analysis flagged
insufficient data, carry that flag through. The writer should know which rules
are load-bearing and which are provisional.

## Voice layer rules

**Sounding like a specific creator is a first-class job of this tool, not an
extra.** Most people who want to write for social media already have someone
they wish they sounded like. Serving that is the point.

So: when the writer names a creator to sound like, the voice layer is loaded
and it is binding. When they name nobody, the skill uses structure only and
says so, rather than quietly imposing the model's own register — which is what
produces an essay read aloud instead of a reel.

**One voice at a time.** Structure findings pool across creators; that is what
makes them trustworthy. Voice does the opposite — averaging two people produces
a third person who does not exist and sounds like nobody. Pool voices only when
the writer explicitly asks, and warn them what it costs.

**The dials are targets, not decoration.** Put the target bands from
`voice.md` into the skill, and make the check loop mandatory:

```
./framezero check draft.txt --like <handle> --wpm <the writer's own pace>
```

`--wpm` is the **writer's** speaking rate, not the creator's. The default of
210 is the studied creators' median and is faster than most people talk;
getting it wrong makes every script about 20% too long. Have them time
themselves reading 200 words aloud.

Every draft gets written, checked, and fixed before it is returned. A skill
that emits a script without running the check is not finished. Say this in the
skill in the imperative, next to the return format.

**Fix by rewriting the beat, not by tuning tokens.** A script edited word by
word to land inside a band reads worse than one that missed it honestly. If
contractions are low, the sentences are written rather than spoken — rewrite
them as speech. If second person is low, the script is *about* a subject
instead of addressed to a viewer — that is a framing problem, not a word
problem.

**Carry the exemplars.** Statistics alone will get the numbers right and still
sound wrong. The exemplar lines in `voice.md` are the few-shot material and
they do more work than the dials do. Include them verbatim.

## Bootstrapping the writer's own voice

A writer starting from zero has no voice profile, because they have no
content. Say so in the voice file rather than pretending otherwise. Until then
they borrow one: pick the creator they most want to sound like and write in
that voice deliberately, with the check loop on.

Point the same pipeline at their own handle once they have roughly twenty reels
and `voice.py` extracts their real profile, which replaces the borrowed one.
That is the intended end state, not a fallback — the borrowed voice is
scaffolding, and the tool should tell them so plainly.
