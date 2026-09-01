# Extraction prompt

Give this to a long-context agent along with `data/<handle>/corpus.md`.
It produces the skill files described in `prompts/emit.md`.

---

You are analysing one creator's short-form video catalogue to extract a
*reusable writing method*, not to summarise their content.

You have `corpus.md`: a full ranked table of their reels, plus timestamped
transcripts for a WINNERS cohort and a CONTROLS cohort. Winners beat the
creator's own contemporaneous median. Controls fell below it. Both cohorts
come from the same creator, the same niche, and roughly the same period.

## The one rule that governs everything

**Report only what separates winners from controls.**

Anything that appears in both cohorts is the creator's habit, not their
advantage. If they open with a question in 12 of 15 winners *and* 12 of 15
controls, opening with a question is worth nothing and must not appear in
your output as a technique. If they use a numbered triad in 11 winners and 3
controls, that is a finding.

Where you have no controls, or fewer than five, say so explicitly and label
every claim as unverified pattern rather than a validated one. Do not quietly
present habit as advantage. An honest "we cannot yet tell these apart" is
worth more than a confident list that sends the writer in the wrong
direction.

## What to produce

### 1. Content modes

Classify every transcribed reel into one of these modes. A reel gets exactly
one primary mode.

- **informational** — conveys news, findings, or a landscape. The viewer
  leaves knowing something they didn't. No action required of them.
- **teaching** — walks the viewer through doing a thing themselves. Steps,
  order, prerequisites. The viewer leaves able to do something.
- **tech-demo** — narrates something happening on a screen. The build, the
  tool, the result. Structure is driven by what the screen shows.
- **personal** — story, opinion, or positioning. Included so it doesn't
  contaminate the other three.

Give the count and the median outlier score per mode. If one mode
systematically outperforms, say so — that is a strategic finding, not a
structural one, and the writer needs it.

### 2. Structure profile, per mode

For each mode with at least three transcribed reels, produce:

- **Hook taxonomy.** Name each archetype you find, give its frequency in
  winners vs controls, and quote two real examples verbatim with timestamps.
  Name the archetype for what it *does* to the viewer, not for its grammar.
- **Beat map.** The actual timing, taken from the transcript timestamps, not
  from theory. When does the hook end. When does the first substantive claim
  land. When does the payoff arrive. When does the CTA start. Give real
  seconds and the spread across the cohort.
- **The middle.** How the body is organised — parallel list, escalation,
  problem-then-solution, chronology. How many beats. Whether beats are
  parallel in grammar.
- **Proof placement.** Where evidence, numbers, names, or screen events land
  relative to the claim they support.
- **The turn.** Most strong short-form has one line that reframes what came
  before into why it matters. Find it. Quote several verbatim. Note its
  position.
- **CTA shape.** Exact wording patterns, position, and what is being asked.
- **Length.** Median and range of duration and word count, and the words per
  second that implies. Note whether winners are longer or shorter than
  controls — do not assume shorter.

### 3. Voice profile

Separate from structure, because the two are used independently.

Hard cap: **200 words.** Long style documents measurably degrade generation —
the model starts imitating the description instead of the voice. Be
ruthlessly specific and short. Cover only: diction and register, sentence
length pattern, person and mode of address, contractions and filler, how
jargon is handled, humour, and any genuinely distinctive recurring
construction. Give three verbatim lines that are maximally characteristic.

Note explicitly anything that would be a *mistake to copy* — verbal tics,
crutches, anything identity-bound to that specific creator.

### 4. Swipe file

The winning transcripts, each annotated inline with which structural move is
happening at each beat. This is the evidence base; the skill points back to
it when the writer wants a real example.

## How to be useful

Quote constantly. A verbatim line with a timestamp beats any amount of
characterisation. Count things and give the counts. When you assert a
pattern, give the frequency in both cohorts.

Never invent a technique because it sounds like good advice. Everything in
your output must be traceable to a specific reel in the corpus. If the corpus
is too thin to support a section, write "insufficient data" and say how many
more reels of which mode would settle it.
