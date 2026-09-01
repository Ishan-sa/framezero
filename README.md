# framezero

Reverse-engineer what actually works on a creator's Instagram Reels, and turn it
into a reusable AI skill that writes scripts in that structure.

Point it at a public handle. It pulls every reel with real play counts, scores
each one against that creator's own baseline, transcribes the outliers locally,
and hands you a corpus your agent turns into a script-writing skill.

No login. No cookies. No paid scraping service. No transcription API.
Runs on your machine for the cost of electricity.

## Why not just use one of the existing tools

The market splits in two and nothing bridges it. Some tools **find** a creator's
best reels (rank by views). Others **explain** one reel (hook, pacing, structure).
The ones that claim to do both and "write scripts in your competitor's voice"
are, on inspection, generic models trained on a generic viral corpus — the
output is not grounded in that specific creator's transcripts at all.

framezero does the grounding, and does three things those tools don't:

**Outlier score, not raw views.** Every reel is scored against the median of its
own neighbours in a ±90 day window. A 100K-view reel from when the creator had
20K followers is a far bigger signal than a 100K-view reel today. Sorting by raw
views — which is all the paid tools do — mostly surfaces recent work.

**Controls, not just winners.** It transcribes the worst performers alongside the
best. Studying only winners is survivorship bias: you learn what all their
videos do, not what the winning ones do *differently*. The delta is the whole
point. No SaaS does this because it doubles their transcription bill.

**A seeded transcript.** whisper.cpp emits all-lowercase, unpunctuated text
unless you give it an initial prompt. framezero seeds one, and loads that seed
with the creator's own domain vocabulary — so it stops writing "N8 N",
"make dot com", and "cloud" when it means Claude. One flag, two wins.

## What 616 reels actually showed

Run against two creators in the same niche — 221 and 395 reels, each split
into winners and controls against their own contemporaneous baseline. Worth
reading before you trust anything you have been told about short-form.

**A concrete number in the first two sentences replicated.** 60% of winners vs
21% of controls for one creator; 58% vs 25% for the other. Two different
formats, two different audiences, near-identical split. It is the most
reliable finding in the dataset.

**Length is not a lever.** Correlation between duration and performance:
**-0.058** across 221 reels and **-0.006** across 395. Every quartile of one
creator's ranking had a median duration of 47-49 seconds. And the two
creators' tails point in *opposite* directions — one's winners are shorter
than her controls, the other's are longer. That is what noise looks like.
Every "keep it under N seconds" rule you have ever read is unsupported here.

**The named subject carries the reel.** One creator's winners named 1.67
already-famous entities in their opening two sentences; his controls named
0.58. The scripts are structurally identical — same format, same CTA, same
delivery, similar length. A 3.2M-play reel and a 7.7K-play reel from the same
creator, written the same way, differed mainly in whether the subject was a
household-name tool or an unknown one. The matching negative: openers that
withhold the subject and refer to it only as an unnamed category ran 8% of
winners and 41% of controls.

**Small samples lie confidently.** The first pass here used 6 reels and
produced a clean, plausible, completely false rule about length, with zero
overlap between cohorts. Scaling to the full catalogue destroyed it — and
re-baselining revealed that the reel that pass had called the best performer
was actually running at 0.818x, *below* the creator's median. Six reels had it
studying an underperformer. **This is the entire argument for scraping the
catalogue rather than eyeballing a handful.**

`aggregate.py` is the stage that decides this for you. It pools every creator
studied for a mode and marks each feature **REPLICATED** (same direction, real
gap, two or more creators), **SINGLE** (one creator's habit — a bet),
**CONTESTED** (creators disagree) or **DEAD**. Only REPLICATED findings belong
in a skill as rules.

**One finding did not replicate,** and the tool was only able to tell because
it ran twice: interview framing (an off-camera voice asks, the creator
answers) split 5-of-15 winners against 0-of-15 controls for one creator, and
appeared nowhere at all in the other's catalogue. A real edge for her, not a
law of the format. Anything measured on a single creator is a bet.

## Requirements

- Python 3.9+ (standard library only — no pip install)
- [`ffmpeg`](https://ffmpeg.org/)
- [`whisper.cpp`](https://github.com/ggerganov/whisper.cpp) — `brew install whisper-cpp`
- A whisper model at `~/.whisper/models/ggml-large-v3-turbo.bin`

## Usage

Describe your niche, the kinds of content you make, and whose work you want to
learn each kind from:

```bash
./framezero new myproject \
    --niche "AI, automation and workflow software" \
    --vocabulary "ChatGPT,Claude,n8n,Make.com,Zapier,Cursor" \
    --mode informational=creator_a,creator_b \
    --mode tech-demo=creator_c \
    --mode funny=creator_d,creator_e

./framezero run myproject
./framezero show myproject
```

**Modes are yours to name.** informational, teaching, tech-demo, funny,
storytime, reviews — whatever divisions your niche actually has. Creators are
mapped to the mode you study them *for*, and the same creator can appear under
more than one. Pooling a comedy account with a tutorial account would compare
two different crafts, so the pipeline keeps them apart and only compares
like with like.

If one creator changed niche and their older reels would poison the baseline,
give that creator their own cutoff rather than the whole project:

```json
"creators": { "somehandle": { "since": "2025-06-01" } }
```

`run` is safe to repeat — every stage skips work already on disk. Add
`--mode funny` or `--only handle` to narrow it.

The stages are also usable on their own:

```bash
python3 bin/scrape.py    <handle>                  # post index + play counts
python3 bin/rank.py      <handle> [--since D]      # outlier scoring
python3 bin/fetch.py     <handle>                  # download + 16kHz audio
python3 bin/listen.py    <handle> --project P      # local transcription
python3 bin/corpus.py    <handle>                  # one markdown corpus
python3 bin/report.py    <handle> --project P      # countable deltas
python3 bin/aggregate.py <project> <mode>          # what replicates
```

### Nothing is hardcoded to one niche

Three things used to be, and all three now come from the project:

- **The whisper seed.** whisper.cpp emits all-lowercase text without an
  initial prompt, so framezero seeds one — built from your niche's vocabulary,
  which fixes the casing *and* stops it mangling names it has never heard.
- **The famous-entity lexicon.** Derived from your own scraped captions:
  proper nouns that recur broadly across the niche's biggest accounts. It
  filters sentence-initial capitals, drops words that also appear lowercase,
  and discards anything appearing in more than a third of posts — a term in
  every caption is that niche's boilerplate, not a household name.
- **The modes.** Yours to define.

Then hand `data/_projects/<project>/<mode>.md` — which findings replicated —
along with `data/<handle>/report.md`, `data/<handle>/corpus.md` and
`prompts/extract.md` to your agent, and it writes the skills.

`report.py` matters more than it looks. An agent reading transcripts will find
patterns whether or not they are there, so the countable features get measured
before the qualitative pass starts — each one marked strong, weak or dead by
the size of the cohort split, with whole-catalogue correlations run separately
to kill findings that only look real at the tails. On its first run it caught
two errors in a careful hand analysis of the same data.

Each stage writes to disk and reads the previous stage's output, so any stage
reruns on its own. `scrape.py` resumes from whatever is already there.

### Options worth knowing

| Flag | Stage | Why |
|---|---|---|
| `--delay 30` | scrape | Seconds between pages. Instagram throttles anonymous requests hard; see below. |
| `--top 15 --bottom 15` | rank | Size of the winner and control cohorts. |
| `--window 90` | rank | Baseline window in days. Shrink it for creators who grew fast. |
| `--keep-mp4` | fetch | Keep the video, not just the audio. |

## How it gets the data, and why that matters

Instagram gated the old REST timeline (`/api/v1/feed/user/`) for logged-out
clients. It now answers 401 on the very first request from a cold IP with:

```
{"message":"Please wait a few minutes before you try again.",
 "require_login":true,"igweb_rollout":true}
```

**That message is a lie.** It is not a throttle and no cooldown clears it — it
is the generic string Instagram returns for a retired or gated surface. Backing
off and retrying is the trap; it costs hours and never succeeds. The same is
true of the legacy `query_hash` route and the older `doc_id`s that instaloader
and gallery-dl still ship.

What works anonymously is two GraphQL calls joined on `code`:

| call | gives you | missing |
|---|---|---|
| `PolarisProfilePostsQuery` | captions, timestamps, likes, comments, `video_versions[]` CDN URLs, DASH manifest | `view_count` is always null logged-out |
| clips user connection | real `play_count` per reel | no video URLs, no timestamps |

Duration is not returned at all any more, so framezero parses
`mediaPresentationDuration` out of the DASH manifest that ships with each post.
Same number, no extra request.

**The only header that matters is the CSRF pair.** Fetch the profile page,
keep the `csrftoken` cookie, echo it back as `X-CSRFToken`. The cookie alone is
rejected with a 403. A browser User-Agent, `X-IG-App-ID`, `X-ASBD-ID`,
`Referer` and `Sec-Fetch-*` are all cargo cult on this endpoint — though
`X-IG-App-ID` *is* required for the one REST call that resolves the user id.

Two seconds between pages is plenty; there is no meaningful rate limit on this
path. A 370-post profile takes about a minute.

**`doc_id`s rotate every two to four weeks.** When one stops working, framezero
scrapes the current value out of Instagram's own JS bundle rather than failing.
That is why this keeps working when the libraries above do not.

## What comes out

The agent writes skills into your own agent config — for Claude Code that is
`~/.claude/skills/<name>/`, one directory per content mode:

```
informational-reel-script/   SKILL.md + swipe-file.md
teaching-reel-script/        SKILL.md + swipe-file.md
tech-demo-reel-script/       SKILL.md + swipe-file.md
reel-voice-layers/           SKILL.md   (voice profiles, applied on request)
```

Split by **mode**, not by creator. A news reel, a how-to and a screen
recording are three different crafts with different beat structures, and one
skill that tries to cover all three writes mush. The sibling descriptions have
to disambiguate each other explicitly or the agent picks between them at
random.

Structure and voice stay in separate files on purpose. The default is the
studied *structure* in your own words; a creator's voice is applied only when
you ask for it. Copying structure is learning a craft. Copying voice produces
a knockoff of someone who already has the audience — and it stops working the
moment you study a second creator, because two voices do not merge.

Swipe files quote real transcripts, so they stay local and out of git along
with everything else under `data/`.

## Scope and etiquette

This reads **public** profile data while logged out, the same data any visitor
sees. It does not log in, does not use anyone's cookies, and does not touch
private accounts. It derives structural patterns for your own writing; it is not
for republishing anyone's content. `data/` is gitignored so scraped material
never lands in a commit.

## Licence

MIT.
