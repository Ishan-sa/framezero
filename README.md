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

Duration is not returned at all any more, so reelmine parses
`mediaPresentationDuration` out of the DASH manifest that ships with each post.
Same number, no extra request.

**The only header that matters is the CSRF pair.** Fetch the profile page,
keep the `csrftoken` cookie, echo it back as `X-CSRFToken`. The cookie alone is
rejected with a 403. A browser User-Agent, `X-IG-App-ID`, `X-ASBD-ID`,
`Referer` and `Sec-Fetch-*` are all cargo cult on this endpoint — though
`X-IG-App-ID` *is* required for the one REST call that resolves the user id.

Two seconds between pages is plenty; there is no meaningful rate limit on this
path. A 370-post profile takes about a minute.

**`doc_id`s rotate every two to four weeks.** When one stops working, reelmine
scrapes the current value out of Instagram's own JS bundle rather than failing.
That is why this keeps working when the libraries above do not.

## Scope and etiquette

This reads **public** profile data while logged out, the same data any visitor
sees. It does not log in, does not use anyone's cookies, and does not touch
private accounts. It derives structural patterns for your own writing; it is not
for republishing anyone's content. `data/` is gitignored so scraped material
never lands in a commit.

## Licence

MIT.
