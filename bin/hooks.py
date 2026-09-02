#!/usr/bin/env python3
"""What the winners say in the first three seconds — and whether it matters.

The hook is the most transferable unit in a reel. The subject is theirs, the
voice is theirs, the face is theirs; the *shape of the opening* is a mechanic,
and a mechanic moves between creators without turning you into a copy of one.

Two lenses, because the good data and the plentiful data are not the same data:

  * **spoken** — the real hook, lifted from the transcript's opening sentence.
    Only exists for the reels the pipeline actually transcribed, which is the
    winner/control study set: about thirty. That set is *designed* to be the
    two tails of the catalogue, so the right question is not "does this
    archetype correlate with views" but "do winners use it more often than
    controls", and the right test is Fisher's exact on a 2x2. Small numbers,
    stated as small numbers.
  * **written** — the first line of the caption, which exists for every reel in
    the index. Hundreds of them, no transcription, no cost. It is not what the
    viewer hears, but it is what the creator chose to lead with, and at that
    sample size it can carry a rank-sum test and a false-discovery correction.

An archetype is a named opening shape — a number, a contradiction, a piece of
news, a warning. The built-in set is a starting point and it is deliberately
easy to replace: pass `--define` with your own, because the shapes that matter
in real estate are not the shapes that matter in software.

Three things it is honest about:

  * whisper.cpp emits segment-level timings, not word-level ones, so the
    three-second boundary inside a long opening segment is estimated from that
    segment's own speaking rate rather than measured.
  * One reel can carry several archetypes. They are not exclusive and the
    columns will not sum to the number of reels.
  * Thirty reels is thirty reels. The spoken lens shows you the hooks to read;
    it cannot prove which archetype wins on its own.

Writes data/<handle>/hooks.md, hooks.json, hooks.csv
"""
import json, pathlib, argparse, sys, re, csv, math
import statistics as st
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import rank, topics as T

ROOT = pathlib.Path(__file__).resolve().parent.parent

SENT_END = re.compile(r"(?<=[.!?])\s+")
HASHTAG_LINE = re.compile(r"^[\s#@\w.]*$")

# Plenty of accounts lead the caption with their conversion mechanic rather
# than with a hook: `Comment "CLAUDE" to get this free scraper.` Measuring
# that as an opening shape would just rediscover that they run one CTA on
# every post. Strip the clause and keep the promise that follows it, which is
# the part doing the persuading.
CTA_LEAD = re.compile(
    r"^\s*(?:\W*\s*)?(?:comment|dm|type|drop|send)\s+"
    r"(?:me\s+)?[\"'\u201c\u2018]?[A-Za-z0-9]{2,15}[\"'\u201d\u2019]?\s*"
    r"(?:below\s+)?(?:to|and|for|&)\s+(?:get|grab|receive|download|try|see|watch)?\s*",
    re.I)

# The opening shapes. Each is (name, what it is, pattern). Order is the order
# they are reported in. Replace the lot with --define when your niche's
# openings do not look like these.
ARCHETYPES = [
    ("number/list", "opens on a count — the viewer knows how long this will take",
     r"^\W*(?:here\s+are\s+)?\d{1,3}\b(?!\s*(?:%|percent|k\b|million|billion|dollars?|\$))"
     r"|\b(?:top|these)\s+\d{1,3}\b|\b\d{1,3}\s+(?:ways?|tools?|tips?|things?|reasons?|steps?|prompts?|apps?|sites?|hacks?)\b"),
    ("news", "something just happened — borrows urgency from the event",
     r"\bjust\s+(?:launched|dropped|released|announced|shipped|went|made|built|got|added|leaked|open[\s-]?sourced)\b"
     r"|\b(?:breaking|finally|it'?s\s+here|is\s+now\s+(?:live|free|open))\b"
     r"|\b(?:recently|silently|quietly)\s+(?:launched|released|dropped|shipped|added|built)\b"
     r"|\b(?:leaked|unveiled)\b|\banother\s+(?:new\s+)?ai\b"),
    ("contrarian", "contradicts what the viewer believes — the cheapest way to stop a scroll",
     r"^\W*(?:stop|don'?t|never|forget|nobody|no\s+one|everyone(?:'?s)?\s+(?:is\s+)?wrong)\b"
     r"|\byou'?re\s+(?:doing|using|building)\b.{0,24}\bwrong\b"
     r"|\b(?:actually|but)\s+(?:nobody|no\s+one)\b|\bis\s+(?:dead|over|a\s+lie)\b"
     r"|\byou\s+(?:don'?t|do\s+not)\s+need\b|\bstop\s+(?:using|paying|buying|wasting)\b"
     r"|\bdidn'?t\s+just\b|\banymore\b|\bno\s+longer\b"
     r"|\bwhile\s+(?:everyone|everybody|the\s+rest)\b"),
    ("curiosity gap", "names a thing it refuses to explain yet",
     r"\b(?:nobody|no\s+one)\s+(?:is\s+)?(?:talk|talking|tells?|telling|know|knows)\b"
     r"|\bthe\s+(?:secret|trick|catch|real\s+reason)\b|\bwhat\s+(?:nobody|no\s+one)\b"
     r"|\byou'?ve\s+never\s+(?:seen|heard)\b"),
    ("free", "removes the price objection before it is raised",
     r"\b(?:completely|totally|100%|entirely)?\s*free\b|\bfor\s+\$?0\b|\bwithout\s+paying\b|\bno\s+credit\s+card\b"),
    ("capability", "states a new thing the viewer can now do",
     r"\byou\s+can\s+now\b|\byou\s+can\s+(?:finally|literally|actually)\b"
     r"|\bnow\s+you\s+can\b|\blets?\s+you\b|\ballows?\s+you\s+to\b"
     r"|\bturns?\s+(?:your|any)\b.{0,30}\binto\b"),
    ("warning/loss", "frames inaction as the expensive option",
     r"\b(?:before\s+it'?s\s+too\s+late|you'?re\s+losing|costing\s+you|biggest\s+mistake"
     r"|will\s+replace|about\s+to\s+(?:replace|kill|end)|if\s+you'?re\s+still)\b"),
    ("proof/credential", "leads with a result or an earned right to speak",
     r"\bi'?(?:ve)?\s+(?:made|built|spent|earned|grown|generated|tested|tried|found)\b|\b\$\d"
     r"|\b(?:after|in\s+the\s+last)\s+\d+\s+(?:years?|months?|days?|weeks?)\b"
     r"|\b\d+[km]?\+?\s+(?:clients?|followers?|users?|students?|subscribers?)\b"),
    ("comparison", "pits two named things against each other",
     r"\bvs\.?\b|\bversus\b|\bbetter\s+than\b|\bcompared\s+to\b|\binstead\s+of\b|\breplaced?\s+my\b"),
    ("demo", "promises to show rather than tell",
     r"\b(?:let\s+me\s+show|i'?(?:ll|m\s+going\s+to|m\s+about\s+to)\s+show"
     r"|watch\s+(?:this|me)|here'?s\s+how|this\s+is\s+how|check\s+this\s+out)\b"),

    ("problem", "names something broken before offering the fix",
     r"\bstruggles?\s+with\b|\bthe\s+problem\s+with\b|\bis\s+(?:broken|useless|garbage)\b"
     r"|\bfalls?\s+apart\b|\bbut\s+it\s+(?:usually|always|still|never)\b"
     r"|\bdoesn'?t\s+(?:actually\s+)?work\b|\bkeeps?\s+(?:failing|breaking)\b"),
    ("speed", "puts a clock on the payoff",
     r"\bin\s+(?:under\s+)?\d+\s*(?:seconds?|secs?|minutes?|mins?|hours?|days?)\b"
     r"|\b(?:instantly|in\s+one\s+click|in\s+seconds)\b"),
    ("question", "opens by asking, and owes an answer",
     r"^\W*(?:what|why|how|who|when|where|which|do|does|did|can|could|would|should|is|are|have|has|ever)\b[^.!?]*\?"
     r"|^\W*(?:ever\s+wonder|what\s+if)\b"),
    ("superlative", "claims a maximum — best, only, first",
     r"\bthe\s+(?:best|only|first|fastest|smartest|craziest|most\s+\w+)\b|\bnothing\s+else\b"),
]


def compile_set(pairs):
    return [(n, d, re.compile(p, re.I)) for n, d, p in pairs]


def split_patterns(s):
    """Split a spec line on commas -- but not the commas inside a regex.

    `\\d{1,3}` and `[a-z]{2,14}` and `(?:a,b)` all contain commas that belong to
    the pattern. Splitting on every comma cuts them in half, and the halves
    still compile: `\\d{1` is a valid regex that matches a digit followed by a
    brace. So the failure is silent, and the archetype quietly matches nothing
    it was meant to. Track bracket depth instead."""
    out, buf, depth = [], [], 0
    for ch in s:
        if ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return [x.strip() for x in out if x.strip()]


def read_spec(path):
    """Your own archetypes.

    JSON: {"name": {"about": "...", "match": ["phrase", "re:^\\d+ ways"]}}
    or the short form {"name": ["phrase", "re:pattern"]}
    or plain text, one per line:  name: phrase, phrase, re:pattern

    A bare entry is matched as a phrase with word boundaries. Prefix it with
    `re:` when you mean a real regular expression.

    In the text form the name may carry the shape\'s job after a pipe:

        name | what it does to the viewer: phrase, re:pattern

    That sentence becomes the last column of the table in hooks.md, which is
    the column a writer actually reads. Without it the column is blank and the
    reader is left to infer the point of the shape from its name."""
    p = pathlib.Path(path)
    if not p.exists():
        sys.exit(f"no hook spec at {path}")
    raw = {}
    if p.suffix == ".json":
        for name, v in json.loads(p.read_text()).items():
            if isinstance(v, dict):
                raw[name] = (v.get("about", ""), v.get("match") or [])
            else:
                raw[name] = ("", v)
    else:
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            name, kws = line.split(":", 1)
            name, _, about = name.partition("|")
            raw[name.strip()] = (about.strip(), split_patterns(kws))
    out = []
    for name, (about, pats) in raw.items():
        if not pats:
            continue
        parts = [p[3:] if p.startswith("re:") else r"\b" + re.escape(p) + r"\b"
                 for p in pats]
        out.append((name, about, "|".join(parts)))
    return compile_set(out)


# ------------------------------------------------------------------ hooks

def first_sentence(text, words_cap=None):
    s = SENT_END.split(text.strip(), 1)[0].strip()
    if words_cap:
        w = s.split()
        if len(w) > words_cap:
            s = " ".join(w[:words_cap]) + "…"
    return s


def spoken_hook(tjson, seconds):
    """The opening sentence, truncated to roughly `seconds` of speech.

    whisper.cpp gives segment timings, not word timings, so a long opening
    segment is sliced by its own words-per-second rather than measured. That is
    an estimate and is labelled as one everywhere it surfaces."""
    segs = (tjson or {}).get("transcription") or []
    if not segs:
        return None, None
    text, spent, cap = "", 0.0, None
    for s in segs:
        off = s.get("offsets") or {}
        a, b = off.get("from", 0) / 1000.0, off.get("to", 0) / 1000.0
        body = (s.get("text") or "").strip()
        if not body:
            continue
        if a >= seconds:
            break
        dur, n = max(b - a, 0.01), len(body.split())
        if b > seconds and n:
            take = max(1, int(round(n * (seconds - a) / dur)))
            text = (text + " " + " ".join(body.split()[:take])).strip()
            cap = take
            break
        text = (text + " " + body).strip()
        spent = b
    if not text:
        return None, None
    return first_sentence(text, words_cap=cap), round(seconds, 1)


def caption_opener(caption):
    """The first line the reader sees, minus the hashtag block and the CTA.

    Returns (opener, was_cta_led) -- the flag matters, because an account whose
    captions all open on the same CTA has a written lens that measures its
    funnel rather than its hooks, and the report says so."""
    for line in (caption or "").splitlines():
        line = line.strip()
        if not line or (line.startswith("#") and HASHTAG_LINE.match(line)):
            continue
        stripped = CTA_LEAD.sub("", line)
        cta = stripped != line
        if cta and len(stripped.split()) < 3:
            # Nothing but the CTA on this line; the promise is on the next.
            continue
        return first_sentence(stripped or line, words_cap=30), cta
    return None, False


def classify(text, arch):
    return [n for n, _, rx in arch if text and rx.search(text)]


# ------------------------------------------------------------- statistics

def fisher(a, b, c, d):
    """Two-sided Fisher's exact on a 2x2.

    The study set is fifteen winners and fifteen controls by construction, so
    a chi-square would be leaning on an approximation that does not hold at
    these counts. Fisher is exact, cheap, and stdlib."""
    n, r1, c1 = a + b + c + d, a + b, a + c
    if min(r1, n - r1, c1, n - c1) == 0:
        return 1.0
    def prob(x):
        return (math.comb(r1, x) * math.comb(n - r1, c1 - x)) / math.comb(n, c1)
    obs = prob(a)
    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    return min(1.0, sum(prob(x) for x in range(lo, hi + 1)
                        if prob(x) <= obs * (1 + 1e-9)))


# ----------------------------------------------------------------- lenses

def spoken_lens(handle, seconds, arch):
    """Read every transcript in the study set and score the archetypes."""
    d = ROOT / "data" / handle
    rf = d / "ranked.json"
    if not rf.exists():
        return None
    ranked = json.loads(rf.read_text())
    tdir = d / "transcripts"
    reels = []
    for r in ranked.get("study_set") or []:
        tj = tdir / f"{r['code']}.json"
        if not tj.exists():
            continue
        try:
            hook, secs = spoken_hook(json.loads(tj.read_text()), seconds)
        except (json.JSONDecodeError, OSError):
            continue
        if not hook:
            continue
        reels.append({
            "code": r["code"], "cohort": r.get("cohort"),
            "outlier": r.get("outlier"), "play_count": r.get("play_count"),
            "hook": hook, "hook_seconds": secs,
            "archetypes": classify(hook, arch),
            "caption_opener": caption_opener(r.get("caption"))[0],
        })
    if not reels:
        return None

    wins = [r for r in reels if r["cohort"] == "winner"]
    ctrl = [r for r in reels if r["cohort"] == "control"]
    rows = {}
    for name, about, _ in arch:
        a = sum(1 for r in wins if name in r["archetypes"])
        c = sum(1 for r in ctrl if name in r["archetypes"])
        if not (a + c):
            continue
        used = [r for r in reels if name in r["archetypes"]]
        rows[name] = {
            "about": about,
            "winners": a, "winners_of": len(wins),
            "controls": c, "controls_of": len(ctrl),
            "reels": a + c,
            "median_outlier": round(st.median([r["outlier"] for r in used]), 2),
            "p": round(fisher(a, len(wins) - a, c, len(ctrl) - c), 4),
        }
    bare = [r["code"] for r in reels if not r["archetypes"]]
    return {"reels": reels, "winners": len(wins), "controls": len(ctrl),
            "archetypes": dict(sorted(
                rows.items(), key=lambda kv: (-(kv[1]["winners"] - kv[1]["controls"]),
                                              kv[1]["p"]))),
            "unclassified": bare}


def written_lens(handle, arch, min_reels, q, since):
    """Caption openers across the whole catalogue — hundreds of them, free."""
    _, reels = T.load(handle, since)
    ranks, ties = T.rank_map(reels)
    med = st.median([r["play_count"] for r in reels])
    tagged, cta_led = [], 0
    for r in reels:
        op, cta = caption_opener(r.get("caption"))
        cta_led += bool(cta)
        tagged.append((r, op, classify(op, arch) if op else []))
    rows = {}
    for name, about, _ in arch:
        use = [r for r, _, ks in tagged if name in ks]
        if len(use) < min_reels:
            continue
        rows[name] = T.measure(use, med, ranks, len(reels), ties)
        rows[name]["about"] = about
    stats = T.judge(rows, q)
    return {"tested": len(reels), "median_plays": int(med),
            "cta_led": cta_led,
            "archetypes": dict(sorted(rows.items(), key=lambda kv: -kv[1]["lift"])),
            "stats": stats,
            "openers": [{"code": r["code"], "outlier": r.get("outlier"),
                         "play_count": r["play_count"], "opener": op,
                         "archetypes": ks} for r, op, ks in tagged]}


def build(handle, seconds, spec, min_reels, q, since):
    arch = read_spec(spec) if spec else compile_set(ARCHETYPES)
    return {
        "handle": handle,
        "generated_at": int(datetime.now(timezone.utc).timestamp()),
        "seconds": seconds,
        "spec": spec,
        "archetype_count": len(arch),
        "fdr_q": q,
        "spoken": spoken_lens(handle, seconds, arch),
        "written": written_lens(handle, arch, min_reels, q, since),
    }


# ------------------------------------------------------------------ output

def markdown(d):
    h = d["handle"]
    L = [f"# Hooks — @{h}", "",
         "The opening is the one part of another creator's reel you can take "
         "outright. The subject is theirs and the voice is theirs; the *shape* "
         "of the first line is a mechanic.", ""]

    sp = d["spoken"]
    if sp:
        L += ["## What they actually say first", "",
              f"The opening sentence of every transcribed reel, capped at "
              f"~{d['seconds']}s of speech. **Read this table before the "
              "statistics below it** — thirty hooks you can see beat any test "
              "run on thirty rows.", "",
              "| | outlier | plays | opening line | shape |",
              "|---|---:|---:|---|---|"]
        for r in sorted(sp["reels"], key=lambda r: -(r["outlier"] or 0)):
            mark = "**W**" if r["cohort"] == "winner" else "C"
            hook = r["hook"].replace("|", "\\|")
            L.append(f"| {mark} | {r['outlier']:.2f}× | {r['play_count']:,} | "
                     f"{hook} | {', '.join(r['archetypes']) or '—'} |")
        L.append("")

        L += ["### Which shapes separate the winners", "",
              f"{sp['winners']} winners against {sp['controls']} controls. "
              "*p* is Fisher's exact — the chance of a split this lopsided if "
              "the archetype had nothing to do with it. One reel can carry "
              "several shapes, so the column does not sum.", "",
              "| shape | winners | controls | median outlier | p | what it does |",
              "|---|---:|---:|---:|---:|---|"]
        for name, v in sp["archetypes"].items():
            L.append(f"| **{name}** | {v['winners']}/{v['winners_of']} | "
                     f"{v['controls']}/{v['controls_of']} | "
                     f"{v['median_outlier']:.2f}× | {v['p']:.3f} | {v['about']} |")
        L += ["", f"<sub>{len(sp['unclassified'])} of "
                  f"{len(sp['reels'])} openings matched no archetype. If that "
                  "number is large, the built-in shapes are wrong for this "
                  "niche — write your own and pass `--define`.</sub>", ""]
    else:
        L += ["## What they actually say first", "",
              "> [!NOTE]",
              "> **No transcripts yet**, so there is no spoken lens. The "
              "caption openers below cover the whole catalogue and cost "
              "nothing, but they are what the creator *wrote*, not what the "
              "viewer *hears*.",
              ">",
              f"> Run `./framezero run <project> --only {h}` to transcribe the "
              "study set, then re-run this.", ""]

    w = d["written"]
    L += ["## Caption openers, across the whole catalogue", "",
          f"The first line of every caption on **{w['tested']:,} reels** — no "
          "transcription, no cost. Not what the viewer hears, but what the "
          "creator chose to lead with. **lift** is the median outlier score of "
          "reels opening that way, where 1.00 is exactly typical for this "
          "creator at the time they posted.", "",
          "Held to a Benjamini-Hochberg correction at "
          f"q={d['fdr_q']}: a shape has to beat the correction before it is "
          "called a finding.", "",
          "| shape | reels | lift | median plays | hit rate | p | verdict |",
          "|---|---:|---:|---:|---:|---:|---|"]
    for name, v in w["archetypes"].items():
        flag = {"overperforms": "**works**",
                "underperforms": "**costs them**",
                "at baseline": "real but small"}.get(v["verdict"], "inconclusive")
        L.append(f"| {name} | {v['reels']} | **{v['lift']:.2f}×** | "
                 f"{v['median_plays']:,} | {int(v['hit_rate']*100)}% | "
                 f"{T.fmt_p(v['p'])} | {flag} |")
    s = w["stats"]
    if w["cta_led"]:
        L += ["", f"<sub>{w['cta_led']:,} of {w['tested']:,} captions opened on "
                  "a comment-to-DM style CTA rather than a hook. That clause is "
                  "stripped before matching, so what is measured above is the "
                  "promise the creator made, not the mechanic they used to "
                  "collect on it.</sub>"]
    L += ["", f"<sub>{s['tests']} shapes tested; "
              + (f"p ≤ {s['threshold']:.4g} required to survive."
                 if s["threshold"] else "none cleared the correction.")
              + "</sub>", ""]

    L += ["## How to use this", "",
          "1. Take the **shape**, never the sentence. A hook you paste is a "
          "hook your audience has already seen.",
          "2. A shape that wins on the spoken lens *and* the written lens is "
          "worth more than one that wins on either.",
          "3. A shape that wins for two different creators is worth more "
          "again — that is the whole replication argument, and it is what "
          "`data/_projects/<project>/<mode>.md` is for.",
          f"4. Write it, then check it: `./framezero check draft.txt --like {h}`.",
          "", "## What this cannot tell you", "",
          "- The spoken lens is ~30 reels chosen as the two tails. It shows "
          "you hooks to read; it cannot prove an archetype wins on its own.",
          "- Segment timings, not word timings: the three-second boundary "
          "inside a long opening segment is estimated from that segment's own "
          "speaking rate.",
          "- On-screen text is invisible here. Many hooks are typed, not "
          "spoken, and nothing in the index carries them.",
          "- The archetypes are a starting set. If most openings match "
          "nothing, replace them: `--define my-hooks.txt`.", "",
          "## Next", "",
          f"- `data/{h}/hooks.csv` — one row per reel, with the hook in its own "
          "column, opens in Excel",
          f"- `./framezero topics {h}` — what they cover, not how they open", ""]
    return "\n".join(L)


CSV_COLS = ["code", "lens", "cohort", "outlier", "play_count",
            "hook", "hook_seconds", "archetypes"]


def write_csv(d, path):
    """He asked for the hooks in their own column. This is that file."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLS)
        sp = d["spoken"]
        if sp:
            for r in sorted(sp["reels"], key=lambda r: -(r["outlier"] or 0)):
                w.writerow([r["code"], "spoken", r["cohort"], r["outlier"],
                            r["play_count"], r["hook"], r["hook_seconds"],
                            ";".join(r["archetypes"])])
        for r in sorted(d["written"]["openers"],
                        key=lambda r: -(r["outlier"] or 0)):
            w.writerow([r["code"], "caption", "", r["outlier"], r["play_count"],
                        r["opener"] or "", "", ";".join(r["archetypes"])])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("handle")
    ap.add_argument("--seconds", type=float, default=3.0,
                    help="how much of the opening counts as the hook (default 3)")
    ap.add_argument("--define", help="your own archetypes (.json or .txt)")
    ap.add_argument("--min-reels", type=int, default=6,
                    help="never test a caption shape with fewer reels")
    ap.add_argument("--q", type=float, default=0.10,
                    help="false-discovery rate for the caption lens")
    ap.add_argument("--since", help="ignore reels before YYYY-MM-DD")
    a = ap.parse_args()
    handle = a.handle.lstrip("@")

    d = build(handle, a.seconds, a.define, a.min_reels, a.q, a.since)
    out = ROOT / "data" / handle
    out.mkdir(parents=True, exist_ok=True)
    (out / "hooks.json").write_text(json.dumps(d, indent=2, ensure_ascii=False))
    (out / "hooks.md").write_text(markdown(d))
    write_csv(d, out / "hooks.csv")
    n = len(d["spoken"]["reels"]) if d["spoken"] else 0
    kept = sum(1 for v in d["written"]["archetypes"].values()
               if v["verdict"] in ("overperforms", "underperforms"))
    print(f"  hooks: {n} spoken, {d['written']['tested']:,} captions, "
          f"{kept} caption shapes survived -> data/{handle}/hooks.md",
          file=sys.stderr)
