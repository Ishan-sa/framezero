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

Voice lives outside the skills, in a single shared file, because structure and
voice are used independently:

```
voice-<handle>.md   the optional voice layer, <= 200 words
```

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

**Hook playbook.** The archetypes from the analysis, each with its name, when
it applies, and a verbatim example from the corpus. Include the banned openings
— the ones that appeared in controls at the same rate as winners, and the
generic ones ("Welcome to", "Check out this", "In this video").

**Beat map with real numbers.** The timings from the analysis, as a target the
writer works against. Say where the payoff lands and where the CTA starts.

**Say what is evidence and what is inference.** Where the analysis flagged
insufficient data, carry that flag through. The writer should know which rules
are load-bearing and which are provisional.

## Voice layer rules

Default behaviour: **their structure, the writer's own words.** The skill uses
the structure profile always. The voice file is applied only when the writer
explicitly asks for it.

This matters. Copying structure is learning a craft. Copying diction is
producing a knockoff of someone who already has the audience — and it stops
scaling the moment you study a second creator, because two voices don't merge.

State this in the skill, once, plainly. Then make the voice layer easy to turn
on for the writer who wants it anyway.

## Bootstrapping the writer's own voice

A writer starting from zero has no voice profile, because they have no
content. Say so in the voice file rather than pretending otherwise. Note that
the same pipeline pointed at their own handle replaces the hand-written
placeholder with a real extracted profile once they have roughly twenty reels
of their own — and that this is the intended end state, not a fallback.
