# reelmine

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

reelmine does the grounding, and does three things those tools don't:

**Outlier score, not raw views.** Every reel is scored against the median of its
own neighbours in a ±90 day window. A 100K-view reel from when the creator had
20K followers is a far bigger signal than a 100K-view reel today. Sorting by raw
views — which is all the paid tools do — mostly surfaces recent work.

**Controls, not just winners.** It transcribes the worst performers alongside the
best. Studying only winners is survivorship bias: you learn what all their
videos do, not what the winning ones do *differently*. The delta is the whole
point. No SaaS does this because it doubles their transcription bill.

**A seeded transcript.** whisper.cpp emits all-lowercase, unpunctuated text
unless you give it an initial prompt. reelmine seeds one, and loads that seed
with the creator's own domain vocabulary — so it stops writing "N8 N",
"make dot com", and "cloud" when it means Claude. One flag, two wins.

## Requirements

- Python 3.9+ (standard library only — no pip install)
- [`ffmpeg`](https://ffmpeg.org/)
- [`whisper.cpp`](https://github.com/ggerganov/whisper.cpp) — `brew install whisper-cpp`
- A whisper model at `~/.whisper/models/ggml-large-v3-turbo.bin`

## Usage

```bash
python3 bin/scrape.py  <handle>              # public post index + play counts
python3 bin/rank.py    <handle>              # outlier scoring, pick study set
python3 bin/fetch.py   <handle>              # download + extract 16kHz audio
python3 bin/listen.py  <handle>              # local transcription
python3 bin/corpus.py  <handle>              # assemble one markdown corpus
```

Then hand `data/<handle>/corpus.md` to your agent along with
`prompts/extract.md`, and it writes the skills.

Each stage writes to disk and reads the previous stage's output, so any stage
reruns on its own. `scrape.py` resumes from whatever is already there.

### Options worth knowing

| Flag | Stage | Why |
|---|---|---|
| `--delay 30` | scrape | Seconds between pages. Instagram throttles anonymous requests hard; see below. |
| `--top 15 --bottom 15` | rank | Size of the winner and control cohorts. |
| `--window 90` | rank | Baseline window in days. Shrink it for creators who grew fast. |
| `--keep-mp4` | fetch | Keep the video, not just the audio. |

## The rate limit, honestly

The public endpoint this uses is real and returns real data, but Instagram
throttles anonymous access aggressively per IP. In practice the first page
returns instantly and then you get:

```
HTTP 401 {"message":"Please wait a few minutes before you try again.",
          "require_login":true,"igweb_rollout":true}
```

`scrape.py` treats that as "slow down" rather than "no": it backs off
exponentially, saves after every single page, and resumes from disk on the next
run. **Expect a full profile to take a while, and expect to run it more than
once.** That is the tradeoff for not paying anyone.

Do not lower `--delay` to speed it up. You will get blocked for longer and
finish later.

## Scope and etiquette

This reads **public** profile data while logged out, the same data any visitor
sees. It does not log in, does not use anyone's cookies, and does not touch
private accounts. It derives structural patterns for your own writing; it is not
for republishing anyone's content. `data/` is gitignored so scraped material
never lands in a commit.

## Licence

MIT.
