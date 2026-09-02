# Extraction prompt

Give this to a long-context agent along with `data/<handle>/corpus.md`.
It produces the skill files described in `prompts/emit.md`.

---

You are analysing one creator's short-form video catalogue to extract a
*reusable writing method*, not to summarise their content.

## Read in this order, and do not skip ahead

Almost everything below has already been **measured**. Your job is to turn
measurements into a method, not to rediscover them by eye — you will find
patterns in transcripts whether or not they are there, which is exactly why
the numbers come first.

| # | file | what it settles |
|---|---|---|
| 1 | `data/_projects/<p>/<mode>.md` | which **structure** replicated across creators |
| 2 | `data/_projects/<p>/signals-<mode>.md` | which **subjects and hook shapes** replicated |
| 3 | `data/<handle>/topics.md` | which subjects beat this creator's own baseline |
| 4 | `data/<handle>/hooks.md` | every winner's opening line, and which shapes separate them |
| 5 | `data/<handle>/report.md` | this creator's countable winner/control deltas |
| 6 | `data/<handle>/voice.md` | 16 measured voice dials with target bands |
| 7 | `data/<handle>/corpus.md` | the transcripts — **LAST** |

Two rules that come out of that table and override anything you think you see
in the transcripts:

- **A finding marked DEAD or CONTESTED must not appear as advice**, however
  good it looks. A finding marked SINGLE may appear, labelled as that
  creator's habit and a bet.
- **Anything the tool calls `inconclusive` is not a finding.** `topics.md` and
  `hooks.md` hold every candidate to a false-discovery correction precisely
  because testing hundreds of them against one catalogue throws up
  coincidences. Promoting an inconclusive row to a rule undoes the only thing
  protecting the output from noise.

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

**The modes come from the project file, not from this prompt.** Read
`projects/<name>.json` — whoever set it up declared which modes they care
about and which creators they study for each. Common ones are informational,
teaching, tech-demo, funny, personal, but a niche may want entirely different
ones and you must use theirs.

Each creator was added under the mode they are studied FOR. Treat that as the
starting assumption, then check it: creators post outside their signature
mode, and a reel that does not belong should be flagged rather than forced
into the cohort. Add a **personal** or **off-mode** bucket if you need
somewhere to put them, so they do not contaminate the analysis.

Give the count and the median outlier score per mode. If one mode
systematically outperforms, say so — that is a strategic finding, not a
structural one, and the writer needs it.

### 2. Subject matter — what to write about

`topics.md` opens with a brief: the subjects that beat this creator's own
rolling baseline, and the ones that cost them. `signals-<mode>.md` says which
of those held for a second creator.

Produce a short list the writer can actually pick from:

- **Territory that replicates.** Subjects REPLICATED across creators. These
  are properties of the niche and belong in the skill as standing guidance.
- **Territory that belongs to one creator.** SINGLE subjects, labelled as
  bets, with the creator named so the writer knows whose ground they are
  borrowing.
- **What to avoid.** Subjects that measurably underperformed. This is usually
  the most actionable half and it is routinely ignored — an account whose own
  promotional posts run at 0.55× baseline needs telling.

Do **not** turn a topic into a template sentence. A subject is territory; the
writer supplies their own material inside it. If you find yourself writing
"open with: China just released…", you have crossed from method into
plagiarism.

### 3. Structure profile, per mode

For each mode with at least three transcribed reels, produce:

- **Hook taxonomy.** `hooks.md` has already classified every transcribed
  opening into archetypes and counted winners against controls with Fisher's
  exact. **Start from that table, do not rebuild it.** Your contribution is
  the part the classifier cannot do: read the actual opening lines in outlier
  order and say what the high performers are *doing to the viewer* that the
  low ones are not. Where the built-in archetypes clearly miss something this
  niche does, name the new shape and say so — that is a request for a
  `--define` spec, and worth flagging to the user.

  Two cautions the file itself makes: with ~15 winners against ~15 controls,
  Fisher's exact will rarely reach significance even when a split looks
  lopsided, so write "the winners lean on this" rather than "this works". And
  never lift a hook sentence into the skill. The shape transfers; the sentence
  makes a knock-off.
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

  **Test it, do not assume it.** Nearly every creator in this format runs a
  comment-to-DM trigger, and the usual conclusion — "it appears in winners and
  controls alike, so it is a habit" — is the weakest form of the argument,
  because a habit cannot be tested against itself. Split the *whole catalogue*
  on whether the caption leads with the trigger and rank-sum the two groups.
  On three catalogues and 2,043 reels, two creators turned out to make a real
  choice (115 vs 1,305 and 108 vs 119) and neither split landed on anything.
  "It neither buys reach nor costs it" is a far stronger and more useful thing
  to tell a writer than "we cannot tell them apart."

  Then say what plays cannot see. The trigger's job is DMs, and DMs are not in
  the index. A null result on reach is not a reason to drop a CTA that is
  earning somebody leads, and the analysis must say so or it will be read that
  way.
- **Length.** Median and range of duration and word count, and the words per
  second that implies. Note whether winners are longer or shorter than
  controls — do not assume shorter.

### 4. Voice profile

Separate from structure, because the two are used independently.

**`voice.md` has already measured this** — 16 dials, each with a target band
derived from that creator's own winners. Do not restate the numbers as prose
and do not contradict them. Your job is the residue: the things a dial cannot
hold. Register, how jargon is handled, humour, and any genuinely distinctive
recurring construction. Give three verbatim lines that are maximally
characteristic.

Hard cap: **200 words.** Long style documents measurably degrade generation —
the model starts imitating the description instead of the voice. The bands
carry the precision; prose that tries to carry it too just dilutes them.

Note explicitly anything that would be a *mistake to copy* — verbal tics,
crutches, anything identity-bound to that specific creator. Voice is the one
layer that must never be pooled across creators: structure can be averaged
because it is a craft, voice cannot because it is a person.

### 5. Swipe file

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
