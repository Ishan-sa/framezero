# AGENTS.md

Instructions for an AI coding assistant (Claude Code, Codex, Copilot, Cursor,
Gemini CLI, Aider, …) that has just been handed this repository.

Read this file top to bottom before running anything. It is written so you can
take a user from a cold clone to a working script-writing skill without asking
them to figure anything out.

---

## 0. Fastest route: connect it as an MCP server

If your client speaks MCP, do this first — it turns the whole pipeline into
typed tools and you can skip the shell entirely.

```bash
claude mcp add framezero -- python3 "$(pwd)/bin/mcp_server.py"
```

Any other client, in its JSON config:

```json
{"mcpServers": {"framezero": {"command": "python3",
                              "args": ["/abs/path/to/bin/mcp_server.py"]}}}
```

Twelve tools. Stdlib only, no install:

| tool | cost | what it answers |
|---|---|---|
| `list_projects` | free | what already exists on disk |
| `niche_neighbours` | free | **who else to study** — start here if they have no handles |
| `profile_creator` | ~1 min | who they are, and is their audience real |
| `creator_topics` | free | which **subjects** beat their own baseline |
| `creator_hooks` | free | how they **open**, and whether it separates winners |
| `replicated_signals` | free | which subjects and hooks hold up across creators |
| `findings` | free | which **structure** replicated |
| `creator_report` | free | one creator's winner/control deltas |
| `voice_profile` | free | how they sound: 16 dials + signature phrases |
| `check_script` | free | score a draft — **run this before showing any draft** |
| `transcripts` | free | the transcripts, read LAST |
| `run_pipeline` | 20–60 min | the whole thing. Confirm with the user first. |

The rest of this file still applies — it is the reasoning behind the tools, and
sections 2, 7 and 8 in particular are not encoded in the schemas.

---

## 1. What this repository is

**framezero** studies a public Instagram creator's Reels and turns what it finds
into a reusable script-writing skill for *you*, the assistant.

It answers two separate questions, and keeping them separate is the whole design:

| question | stage | output | needs transcription? |
|---|---|---|---|
| **Who is this creator**, and are they worth studying? | `profile.py` | dossier: reach, trajectory, brand deals, CTAs, neighbours | no — ~1 min |
| What are their winning reels **about**, structurally? | `report.py` → `aggregate.py` | countable feature deltas, marked REPLICATED / SINGLE / CONTESTED / DEAD | yes |
| What does that creator **sound like**? | `voice.py` | 16 numeric dials with target bands, plus signature phrases | yes |

You are not an optional add-on to this pipeline. **You are the last stage.** The
Python writes measurements; you read them and write the skill. `prompts/extract.md`
and `prompts/emit.md` are your instructions for that stage — read them when you
get there, not before.

---

## 2. Ground rules (violating these breaks the project)

> [!IMPORTANT]
> These are not style preferences. Each one exists because breaking it already
> caused a real failure.

1. **Never commit anything under `data/`, `out/`, or `projects/*.json`.**
   `data/` is someone else's content. `projects/*.json` names real creators.
   `.gitignore` covers all three; only `projects/example.json` is tracked. Do not
   `git add -f` past it, and do not paste creator handles or verbatim transcript
   lines into commit messages, the README, or any tracked file.

2. **Never average two creators' voices.** Structure findings pool across
   creators — that is what makes them trustworthy. Voice does not. Averaging two
   voices produces a third person who does not exist. Write in one voice at a time.

3. **Never retry `/api/v1/feed/user/<id>/`.** Instagram gated it. It returns 401
   on the first request from a cold IP with the text *"Please wait a few minutes
   before you try again."* **That message is a lie** — it is the generic string for
   a retired surface, there is no cooldown, and backing off costs hours and never
   succeeds. `scrape.py` already uses the two GraphQL calls that do work.

   **Instagram returns that identical string for two different things**, and you
   cannot tell them apart from the response: a permanently retired surface, and a
   temporarily blocked one. `/api/v1/users/web_profile_info/` — the one call that
   still fetches follower count, bio, category and related accounts — now answers
   it too, IP-wide, for handles never touched. So:

   - **Never let it kill a run.** `scrape.py` falls back to
     `user_id_from_timeline()`, which lifts the user id and basic identity off
     the post timeline. Every downstream stage still works; only the identity
     block in the dossier is thinner.
   - **Do not build in a retry loop.** If it is the rollout, no wait clears it.
   - **Do offer `--refresh` later.** If it was a throttle, it comes back, and
     `--refresh` refills the missing fields.

4. **Only REPLICATED findings become rules.** A finding measured on one creator
   is that creator's habit, not a law of the format. Write it into a skill as a
   bet, labelled as one — never as a rule.

5. **Do not install skills into the user's agent config without asking.** Emit to
   `out/skills/` and let them review first.

6. **Standard library only.** No `pip install`. If you are tempted to add a
   dependency, you are solving the wrong problem.

---

## 3. Preflight

Run this first. It tells you exactly what is missing.

```bash
python3 - <<'PY'
import shutil, sys, pathlib
ok = True
print("python  ", sys.version.split()[0], "OK" if sys.version_info >= (3, 9) else "NEED >= 3.9")
for tool in ("ffmpeg", "whisper-cli"):
    p = shutil.which(tool)
    print(f"{tool:8}", p or "MISSING"); ok &= bool(p)
m = pathlib.Path.home() / ".whisper/models/ggml-large-v3-turbo.bin"
print("model   ", m if m.exists() else f"MISSING -> {m}"); ok &= m.exists()
print("\nready" if ok else "\nsee section 3 of AGENTS.md")
PY
```

Install whatever it reports missing:

<table>
<tr><th>macOS</th><th>Debian / Ubuntu</th></tr>
<tr valign="top"><td>

```bash
brew install ffmpeg whisper-cpp
```

</td><td>

```bash
sudo apt install -y ffmpeg build-essential cmake
git clone https://github.com/ggerganov/whisper.cpp /tmp/whisper.cpp
cmake -B /tmp/whisper.cpp/build -S /tmp/whisper.cpp
cmake --build /tmp/whisper.cpp/build -j --config Release
sudo cp /tmp/whisper.cpp/build/bin/whisper-cli /usr/local/bin/
```

</td></tr>
</table>

The model, on either platform (~1.6 GB, one time):

```bash
mkdir -p ~/.whisper/models
curl -L -o ~/.whisper/models/ggml-large-v3-turbo.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin
```

No API keys. No accounts. No login. Nothing is sent anywhere except the
anonymous requests to Instagram's public GraphQL endpoint.

---

## 4. What to ask the user

You need four things before you can create a project. Ask for all of them in one
message; do not go one at a time.

| you need | example | why |
|---|---|---|
| **niche label** | `"AI, automation and workflow software"` | seeds the whisper prompt |
| **vocabulary** | `ChatGPT,Claude,n8n,Make.com,Zapier` | stops whisper writing "N8 N" and "make dot com" |
| **modes** | `informational`, `tech-demo`, `funny` | different crafts, studied separately |
| **creators per mode** | public handles they admire | 2+ per mode, or nothing can replicate |

> [!TIP]
> If the user names only one creator, tell them plainly: with one creator nothing
> can be marked REPLICATED, so every finding will come back as a bet. Two is the
> minimum for the tool to do its actual job. Run it anyway if they want — just
> make sure they know what they are getting.

Modes are the user's to name. Pooling a comedy account with a tutorial account
compares two different crafts and produces mush, so the pipeline keeps them
apart. Same creator can appear under more than one mode.

---

## 5. Start cheap: profile before you commit

### If they do not know whose work to study

Most people arrive with one or two handles and a vague sense that there must be
others. Do not make them guess, and do not guess for them — a handle you
invented either 404s or, worse, resolves to somebody irrelevant.

```bash
./framezero neighbours                        # every catalogue on disk
./framezero neighbours <handle> --probe       # and check they have an audience
```

Creators tag each other, run collabs, and name each other in captions, and all
of that is already sitting in `index.json`. `neighbours` ranks those handles by
how many of *your* creators point at them — two unrelated accounts naming the
same person is a niche; one account tagging somebody four hundred times is a
business partner.

`--probe` then pulls a three-page sample of each candidate and reports median
plays, because the list is worthless if half the names have no audience. That
check has already killed a candidate that looked perfect on paper and turned
out to run 150 plays a reel.

Two limits worth saying out loud to the user: a tag is not a similarity, so
read `profile.md` before adding anyone to a project; and the best creator in a
niche is often the one who never collabs, so this will never be the whole list.

A full run costs 20–60 minutes, almost all of it transcription. A dossier costs
one scrape:

```bash
./framezero profile <handle>
```

That one command runs three free stages and writes six files:

| file | what it answers |
|---|---|
| `profile.md` | who they are, how they earn, **is their audience real** |
| `topics.md` | which **subjects** beat their own baseline |
| `hooks.md` | how they **open**, and whether it separates their winners |
| `posts.csv` | every post, one row each — with `hook`, `topics` and `hook_shapes` columns |
| `profile.json` / `topics.json` / `hooks.json` | the same, structured |

None of it transcribes anything. All three read the index that the scrape put
on disk, so re-running them costs nothing.

**Use it as a gate — there are two gates, and both are in `profile.md`.**

1. *"Does the audience match the views?"* — plays per follower over **recent**
   reels, read together with engagement. A million followers and twenty
   thousand views is not a creator to study, and this section says so in
   words. If it reports **the numbers do not add up**, tell the user before
   they build a content strategy on that account.
2. *"Is there anything to learn here?"* — the ratio of the creator's top decile
   to their own median. If that ratio is near 1, their winners are not doing
   anything different and the expensive pass will produce nothing.

### What topics.md and hooks.md are for

This is the part that answers **"what do I make tomorrow"**, and it is the part
users actually want.

- `topics.md` opens with a **brief**: the subjects that beat this creator's own
  rolling baseline, plus the ones that cost them. Every topic is rank-sum
  tested against the rest of the catalogue and the whole family is held to a
  Benjamini-Hochberg false-discovery rate — because testing six hundred mined
  terms against one catalogue guarantees a few spectacular coincidences.
  **Anything the file calls `inconclusive` is not a finding. Do not report it
  as one.**
- `hooks.md` opens with the actual opening line of every transcribed reel, in
  outlier order. **Read that table before the statistics under it** — thirty
  hooks you can see beat any test run on thirty rows.

Both take `--define <spec>`, and you should push the user toward it:

```bash
./framezero topics <handle> --define specs/real-estate.topics.txt
./framezero hooks  <handle> --define specs/real-estate.hooks.txt
```

The mined lens infers subject matter from word counts. The user already knows
what the subjects in their niche are, and naming them is also what makes two
creators comparable — the cross-creator pass can only line up topics that share
a name. `specs/` holds a worked example of both formats; copy the shape.

It is also the answer to "who else should I study": `neighbours` in
`profile.json` is Instagram's own related-accounts list for that handle.

### Then compare two creators before trusting either

```bash
./framezero signals <project> --mode informational
./framezero signals <project> --handles handle_a,handle_b   # no config edit
```

A subject or a hook shape that works for one creator is that creator's
territory. `signals.md` gives it the same verdicts the structural pass uses —
**REPLICATED / CONTESTED / SINGLE / DEAD** — and only REPLICATED should ever
become a rule. CONTESTED is not a weak REPLICATED: two creators pointing
opposite ways means the effect belongs to something nobody measured.

Hook shapes replicate more meaningfully than subjects do, and it is worth
telling the user why: every creator is scored against the *same* archetype
list, so those names line up by construction, whereas two creators only share a
topic name when they happen to use the same word for the same thing.

Six limits to state plainly rather than paper over:

- **No follower history.** Instagram returns one number, today. The trajectory
  table is median plays per quarter, which is a proxy and moves with the
  algorithm as well as the audience. Never present it as follower growth.
- **Disclosed sponsorship only.** `paid_partnership` is the platform flag.
  Sponsor tags, recurring @mentions and caption CTAs catch more, never all.
- **Location only where tagged**, which is usually nowhere.
- **A caption is not the video.** The topic lenses read captions. A reel about
  something its caption never names is invisible to all of them.
- **Correlation.** A topic that overperforms is a place to look, not a proven
  cause — the hook and the structure travel with the subject.
- **The spoken hook lens is ~30 reels**, chosen as the two tails of the
  catalogue. It shows the user hooks to read; it cannot prove an archetype wins
  on its own, and Fisher's exact on 15-vs-15 will rarely reach significance
  even when the split looks lopsided. Say "the winners lean on this", not
  "this works".

---

### Wire the specs into the project so `run` picks them up

Two optional keys in `projects/<name>.json`, both paths relative to the repo
root. When present, `./framezero run` passes them to every creator's topics and
hooks stage automatically:

```json
"topic_spec": "specs/real-estate.topics.txt",
"hook_spec":  "specs/real-estate.hooks.txt"
```

Worth doing early. A shared spec is what lets `signals` line two creators up on
the same topic name, and topic names are the one thing the cross-creator pass
cannot infer for you.

---

## 6. The run

```bash
./framezero new myproject \
    --niche "AI, automation and workflow software" \
    --vocabulary "ChatGPT,Claude,n8n,Make.com,Zapier,Cursor" \
    --mode informational=handle_a,handle_b \
    --mode tech-demo=handle_c

./framezero run myproject          # 20-60 min for two creators, mostly transcription
./framezero show myproject         # progress at any time
```

`run` is **idempotent** — every stage skips work already on disk. If it dies
halfway, run it again. To force a re-pull for one creator, delete
`data/<handle>/index.json`.

Useful narrowing: `--mode informational`, `--only handle_a`, `--top 15 --bottom 15`.

Stages, in order, all runnable alone:

```mermaid
flowchart LR
  A[scrape.py<br/><sub>index + play counts</sub>] --> B[rank.py<br/><sub>outlier score</sub>]
  B --> C[fetch.py<br/><sub>mp4 to 16kHz wav</sub>]
  C --> D[listen.py<br/><sub>whisper.cpp</sub>]
  D --> E[corpus.py<br/><sub>one markdown</sub>]
  E --> F[report.py<br/><sub>countable deltas</sub>]
  F --> P[profile.py<br/><sub>account dossier</sub>]
  P --> G[voice.py<br/><sub>16 dials</sub>]
  G --> H[aggregate.py<br/><sub>what replicates</sub>]
  H --> I([you<br/><sub>write the skill</sub>])
```

Two ordering constraints you must not "optimise" away:

- `voice.py` runs **after every creator**, never inside the per-creator loop. A
  signature phrase is one this creator uses *and the others do not*, so it cannot
  be computed until the others exist.
- `report.py` runs **before** you read any transcript. An agent reading
  transcripts will find patterns whether or not they are there. Measure first,
  then read.

---

## 7. Read the outputs in this order

```
data/_projects/<project>/<mode>.md          ← START HERE. Structure that replicated.
data/_projects/<project>/signals-<mode>.md  ← subjects + hook shapes that replicated
data/<handle>/profile.md                    ← who they are, and is the audience real
data/<handle>/topics.md                     ← which subjects beat their own baseline
data/<handle>/hooks.md                      ← how they open — the transferable part
data/<handle>/report.md                     ← that creator's countable deltas
data/<handle>/voice.md                      ← how they sound: dials + signature phrases
data/<handle>/corpus.md                     ← the transcripts themselves (read LAST)
prompts/extract.md                          ← how to turn the above into a skill
prompts/emit.md                             ← how the skill must be written
```

The two `_projects` files come first for the same reason: they are the only
files in the tree that have been checked against a second creator. Everything
under `data/<handle>/` is one account's habits until proven otherwise.

Then emit one skill **per mode** (not per creator) into `out/skills/`, plus a
separate voice layer. Structure and voice stay in separate files on purpose:
copying structure is learning a craft, copying voice makes a knockoff of someone
who already has the audience.

---

## 8. Closing the loop on every draft

This is the part assistants skip, and skipping it is why generated scripts read
like an essay in the shape of a reel. **Every draft gets checked before you show
it to the user.**

```bash
./framezero check draft.txt --like handle_a --wpm 176
```

```
runtime at 176.0 wpm: 55s   their winners ran 23–57s   ok
dial                         script          target  verdict
second person /100w            6.17     4.26 – 7.77  ok
words per sentence             13.5     12.9 – 20.5  ok
long sentences (>20w) %        8.33     9.11 – 52.0  LOW  ↑ raise
numbers /100w                  4.94     0.24 – 4.13  HIGH ↓ lower
...
2 of 16 dials off. Worst first:
  HIGH  numbers /100w   (20% outside)
```

Rules for using it:

- **`--wpm` is the writer's own pace, not the creator's.** Default is 210, which
  is the studied creators' median and is faster than most people speak. Have the
  user time themselves reading 200 words aloud; `wpm = words / minutes`. Getting
  this wrong makes every script about 20% too long.
- **Fix a failing dial by rewriting the beat, not by tuning tokens.** If runtime
  is over, cut a whole beat — do not shave adjectives.
- A dial is a **band, not a point.** Land inside it; do not chase the mean.
- `--like a,b` pools bands across handles. Use it only to widen a target range,
  never as a licence to blend two voices in the prose.

---

## 9. Troubleshooting

| symptom | cause | fix |
|---|---|---|
| `scrape.py` returns 0 posts | `doc_id` rotated (happens every 2–4 weeks) | It self-heals — it scrapes the current id out of Instagram's JS bundle. Re-run once. |
| 401 on `/api/v1/feed/user/` | the retired REST timeline | Do not back off. See ground rule 3. |
| `profile endpoint unavailable (401) — falling back to the timeline` | `web_profile_info` is gated or throttled for your IP | **Nothing is broken.** The run continues; the dossier says which identity fields are missing. Retry with `--refresh` later. |
| Transcripts are all lowercase, no punctuation | whisper ran without a seed prompt | Pass `--project <name>` to `listen.py`. This is not optional. |
| Whisper writes "N8 N", "make dot com", "cloud" | niche vocabulary missing from the project | Add the terms to `vocabulary`, delete the bad transcripts, re-run `listen.py`. |
| Every finding says SINGLE | only one creator in that mode | Add a second creator. This is the tool working correctly. |
| `voice.py profile` refuses | fewer than 3 transcribed winners | Raise `--top`, or the creator does not have enough catalogue. |
| `profile.md` has no brand deals, audio or tags | index predates those fields | `./framezero profile <handle> --refresh` |
| Dossier says the spread is flat | the account genuinely has no winner/control delta | Say so before spending an hour transcribing it. |
| Ranking looks wrong for a creator who pivoted | old reels poisoning the baseline | Give that creator their own cutoff: `"creators": {"handle": {"since": "2025-06-01"}}` |

---

## 10. Repository map

```
framezero              CLI: new / run / show / profile / topics / hooks /
                       signals / neighbours / voice / check
bin/scrape.py          public GraphQL index + real play counts
bin/rank.py            outlier score vs a ±90-day rolling median
bin/fetch.py           mp4 download, ffmpeg to 16kHz mono wav
bin/listen.py          whisper.cpp, seeded with the niche vocabulary
bin/corpus.py          ranking + transcripts into one markdown file
bin/report.py          countable winner/control deltas, per creator
bin/profile.py         whole-account dossier + audience-health verdict
bin/topics.py          which subjects beat the baseline, FDR-corrected
bin/hooks.py           spoken + written hook archetypes, per creator
bin/replicate.py       subjects and hooks that hold up across creators
bin/neighbours.py      who else in the niche is worth studying, from co-tags
bin/voice.py           16 voice dials, signature phrases, draft scoring
bin/mcp_server.py      the same pipeline as MCP tools, over stdio
bin/aggregate.py       pools creators, assigns replication verdicts
bin/project.py         project config, niche lexicon derivation
prompts/extract.md     how to read the outputs
prompts/emit.md        how to write the skills
projects/example.json  placeholder config — copy this shape
specs/                 worked topic + hook specs for --define, copy the shape
```

---

## 11. Definition of done

Before you tell the user you are finished:

- [ ] `./framezero show <project>` lists every creator with a transcript count > 0
- [ ] `data/_projects/<project>/<mode>.md` exists for every mode and has verdicts
- [ ] `data/_projects/<project>/signals-<mode>.md` exists and you have read it
- [ ] every creator has a `profile.md`, `topics.md`, `hooks.md` and a `voice.md`
- [ ] you told the user which creators failed the audience-health check, if any
- [ ] nothing the tool called `inconclusive` was reported to the user as a finding
- [ ] `out/skills/` has one skill per mode, plus a voice layer
- [ ] every rule in a skill traces to a REPLICATED finding; bets are labelled as bets
- [ ] any sample script you wrote passes `./framezero check` at the user's own wpm
- [ ] `git status` is clean of `data/`, `out/`, and real `projects/*.json`
