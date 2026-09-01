#!/usr/bin/env python3
"""Derive how a creator SOUNDS, and score a draft against it.

report.py measures what a reel is ABOUT -- features of the opening, the things
that separate winners from controls. That is structure, and structure is only
half of why a script feels like a particular person.

The other half is voice: who the sentences are addressed to, how long they run,
which words recur, how a beat is handed to the next one. None of that was
measured anywhere, which meant a writing agent got findings about a creator and
then supplied its own diction -- producing an essay in the shape of a reel.

This stage measures voice mechanically, the same way report.py measures
structure, so that "sound like them" becomes a target with numbers on it
instead of an instruction to vibe.

Two commands:

  profile <handle>            -> data/<handle>/voice.md, voice.json
  check <script> --like <h>   -> scorecard: which dials are off, and which way

`check` closes the loop. Write, measure, fix, repeat -- the same discipline the
rest of the pipeline already applies to findings.
"""
import json, pathlib, re, argparse, sys, math
import statistics as st
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Bands are built from a creator's WINNERS. A creator's controls are still
# their voice, but the winners are the version of it worth reproducing.
COHORT = "winner"
MIN_TRANSCRIPTS = 3

WORD = re.compile(r"[A-Za-z']+")
SENT = re.compile(r"(?<=[.?!])\s+")

SECOND = re.compile(r"\b(you|your|you're|youre|yours|yourself)\b", re.I)
FIRST_SG = re.compile(r"\b(i|i'm|im|i've|i'll|my|me|mine)\b", re.I)
FIRST_PL = re.compile(r"\b(we|we're|our|us|ours)\b", re.I)
CONTRACTION = re.compile(r"\b\w+'(s|re|ve|ll|t|d|m)\b", re.I)
NUMBER = re.compile(r"[\d]+|\b(one|two|three|four|five|ten|hundred|thousand|million|billion)\b", re.I)

# Sentences that begin with a bare verb read as instructions to the viewer.
IMPERATIVE = re.compile(
    r"^(go|try|start|stop|use|take|look|watch|check|comment|open|click|type|copy|"
    r"paste|build|make|think|imagine|forget|remember|keep|give|grab|drop|save|"
    r"pick|head|drag|hit|add|run|install|download|sign|let|don't|do not|never|always)\b",
    re.I)

ANCHOR = re.compile(
    r"\b(think of it like|it'?s basically|basically|just like|works like|"
    r"kind of like|sort of like|imagine|it'?s like|similar to|on par with)\b", re.I)

# Fillers so generic they say nothing about a person. Excluded from the
# distinctive-marker search for the same reason `max_df` exists in the lexicon
# derivation: something everybody says is not a fingerprint.
GENERIC = {
    "the", "a", "an", "and", "or", "but", "if", "so", "to", "of", "in", "on",
    "for", "with", "that", "this", "it", "is", "are", "was", "were", "be",
    "been", "as", "at", "by", "from", "up", "out", "not", "no", "yes", "can",
    "will", "just", "one", "two", "all", "get", "got", "has", "have", "had",
    "do", "does", "did", "you", "your", "i", "my", "we", "our", "they", "them",
    "he", "she", "his", "her", "its", "there", "here", "what", "when", "how",
    "why", "who", "which", "than", "then", "now", "very", "more", "most",
}


def syllables(word):
    """Rough spoken-length proxy. Exactness does not matter; the delta does."""
    w = word.lower().strip("'")
    if not w:
        return 0
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and n > 1 and not w.endswith(("le", "ee", "ye")):
        n -= 1
    return max(1, n)


def transcripts(handle, cohort=COHORT):
    """Spoken text of one cohort, one entry per reel."""
    ranked = ROOT / "data" / handle / "ranked.json"
    if not ranked.exists():
        return []
    study = json.loads(ranked.read_text())["study_set"]
    tdir = ROOT / "data" / handle / "transcripts"
    out = []
    for r in study:
        if cohort and r.get("cohort") != cohort:
            continue
        p = tdir / f"{r['code']}.txt"
        if not p.exists():
            continue
        lines = [re.sub(r"^\[\d+:\d+\]\s*", "", l)
                 for l in p.read_text().split("\n") if l.startswith("[")]
        body = " ".join(lines).strip()
        if body:
            out.append({"code": r["code"], "outlier": r.get("outlier"), "text": body})
    return out


def sentences(text):
    return [s.strip() for s in SENT.split(text) if s.strip() and WORD.search(s)]


def measure(text):
    """The dials. Every one is a rate or a shape, so scripts of any length compare."""
    words = WORD.findall(text)
    sents = sentences(text)
    if not words or not sents:
        return None
    n, ns = len(words), len(sents)
    lens = [len(WORD.findall(s)) for s in sents]
    per100 = lambda rx: 100 * len(rx.findall(text)) / n

    return {
        "second person /100w": per100(SECOND),
        "first person sing /100w": per100(FIRST_SG),
        "first person plur /100w": per100(FIRST_PL),
        "imperative sentences %": 100 * sum(bool(IMPERATIVE.match(s)) for s in sents) / ns,
        "words per sentence": st.mean(lens),
        "short sentences (<8w) %": 100 * sum(1 for x in lens if x < 8) / ns,
        "long sentences (>20w) %": 100 * sum(1 for x in lens if x > 20) / ns,
        "longest sentence (w)": max(lens),
        "sentence length spread": st.pstdev(lens) if ns > 1 else 0.0,
        "contractions /100w": per100(CONTRACTION),
        "long words (8+ch) %": 100 * sum(1 for w in words if len(w) >= 8) / n,
        "syllables per word": sum(syllables(w) for w in words) / n,
        "commas per sentence": text.count(",") / ns,
        "numbers /100w": per100(NUMBER),
        "questions %": 100 * sum(1 for s in sents if s.endswith("?")) / ns,
        "anchor phrases /100w": per100(ANCHOR),
    }


def band(values):
    """A target range, not a target number.

    A voice is a region, not a point. One reel's rate is noise; the spread
    across a creator's winners is the thing a draft should land inside.
    """
    lo, hi = min(values), max(values)
    mean = st.mean(values)
    sd = st.pstdev(values) if len(values) > 1 else 0.0
    # Widen to one sd so a draft is not punished for landing between two reels,
    # but never wider than what the creator actually did.
    return {"mean": mean, "sd": sd,
            "lo": max(lo, mean - sd), "hi": min(hi, mean + sd),
            "min": lo, "max": hi}


def fingerprint(handle):
    ts = transcripts(handle)
    if len(ts) < MIN_TRANSCRIPTS:
        return None
    rows = [m for m in (measure(t["text"]) for t in ts) if m]
    keys = rows[0].keys()
    return {k: band([r[k] for r in rows]) for k in keys}, ts


def ngrams(texts, nmax=3):
    c = Counter()
    for t in texts:
        for s in sentences(t):
            w = [x.lower() for x in WORD.findall(s)]
            for n in range(1, nmax + 1):
                for i in range(len(w) - n + 1):
                    g = w[i:i + n]
                    if n == 1 and g[0] in GENERIC:
                        continue
                    if all(x in GENERIC for x in g):
                        continue
                    c[" ".join(g)] += 1
    return c


def distinctive(handle, others, top=18, min_count=3):
    """Phrases this creator reaches for and the others do not.

    Raw frequency finds "the AI tool". What makes someone sound like themselves
    is the phrase that is ordinary for them and rare for everyone else, so this
    scores rate-here against rate-elsewhere -- the same logic the niche lexicon
    uses to throw away boilerplate.
    """
    mine_t = [t["text"] for t in transcripts(handle)]
    if not mine_t:
        return []
    mine = ngrams(mine_t)
    mine_n = sum(mine.values()) or 1

    theirs, theirs_n = Counter(), 0
    for h in others:
        ts = [t["text"] for t in transcripts(h)]
        if not ts:
            continue
        c = ngrams(ts)
        theirs += c
        theirs_n += sum(c.values())
    theirs_n = theirs_n or 1

    scored = []
    for g, k in mine.items():
        if k < min_count:
            continue
        r_self = k / mine_n
        r_other = theirs.get(g, 0) / theirs_n
        lift = r_self / (r_other + 1 / theirs_n)
        if lift < 1.5:
            continue
        scored.append((g, k, lift))
    # Longer phrases carry more voice than single words at the same lift.
    scored.sort(key=lambda x: (x[2] * (1 + 0.35 * (x[0].count(" "))), x[1]),
                reverse=True)
    return scored[:top]


def openers(handle, top=10):
    c = Counter()
    for t in transcripts(handle):
        for s in sentences(t["text"]):
            w = WORD.findall(s)
            if len(w) >= 2:
                c[" ".join(w[:2]).lower()] += 1
    return [(g, k) for g, k in c.most_common(top) if k > 1]


def exemplars(handle):
    """Real lines, by the job they do. This is the few-shot material.

    A writing agent given only statistics will hit the numbers and still sound
    wrong. It needs to see the actual sentences.
    """
    ts = sorted(transcripts(handle), key=lambda t: -(t["outlier"] or 0))
    hooks, anchors, closes = [], [], []
    for t in ts:
        s = sentences(t["text"])
        if not s:
            continue
        hooks.append((t["code"], t["outlier"], s[0]))
        closes.append((t["code"], t["outlier"], s[-1]))
        for x in s[1:-1]:
            if ANCHOR.search(x) and len(WORD.findall(x)) <= 32:
                anchors.append((t["code"], t["outlier"], x))
    return {"hooks": hooks[:8], "anchors": anchors[:8], "closes": closes[:6]}


def fmt(v):
    return f"{v:.1f}" if abs(v) >= 10 else f"{v:.2f}"


def cmd_profile(a):
    handle = a.handle.lstrip("@")
    fp = fingerprint(handle)
    if not fp:
        sys.exit(f"@{handle}: need at least {MIN_TRANSCRIPTS} transcribed "
                 f"{COHORT}s -- run the pipeline for this creator first")
    bands, ts = fp

    others = []
    if a.project:
        sys.path.insert(0, str(ROOT / "bin"))
        import project as P
        cfg = P.load(a.project)
        others = [h for h in P.creators(cfg) if h != handle]

    marks = distinctive(handle, others) if others else []
    ops = openers(handle)
    ex = exemplars(handle)

    out = [f"# Voice profile — @{handle}", ""]
    out += [f"Derived from {len(ts)} transcribed winners. Every number is a rate "
            f"or a shape, so it compares across scripts of any length.", "",
            "A voice is a **region, not a point**. Land inside the band; do not "
            "chase the mean.", ""]

    out += ["## Dials", "",
            "| dial | target band | their range |", "|---|---|---|"]
    for k, b in bands.items():
        out.append(f"| {k} | **{fmt(b['lo'])} – {fmt(b['hi'])}** | "
                   f"{fmt(b['min'])} – {fmt(b['max'])} |")
    out.append("")

    if marks:
        out += ["## Signature phrases", "",
                "Phrases they reach for and the other creators in this project "
                "do not. Lift is how much more often, relative to everyone else.",
                "", "| phrase | uses | lift |", "|---|---|---|"]
        for g, k, lift in marks:
            out.append(f"| {g} | {k} | {lift:.1f}× |")
        out.append("")
    elif others == []:
        out += ["## Signature phrases", "",
                "_Not derived — this needs at least one other creator in the "
                "project to compare against. Distinctiveness is relative._", ""]

    if ops:
        out += ["## How their sentences start", "",
                "| opener | uses |", "|---|---|"]
        for g, k in ops:
            out.append(f"| {g}… | {k} |")
        out.append("")

    out += ["## Exemplars", "",
            "Read these before writing. The dials tell you the shape; these "
            "tell you the sound.", ""]
    for title, rows in (("Hooks", ex["hooks"]), ("Anchors", ex["anchors"]),
                        ("Closes", ex["closes"])):
        if not rows:
            continue
        out.append(f"### {title}")
        out.append("")
        for code, o, line in rows:
            out.append(f"- _{o:.1f}x_ — {line}")
        out.append("")

    out += ["## How to use this", "",
            "Write the script from the structure skill first. Then run:", "",
            "```", f"./framezero check <script.txt> --like {handle}", "```", "",
            "and fix whatever comes back OFF. Do not edit toward the numbers "
            "sentence by sentence — rewrite the beat that is wrong. A script "
            "tuned token by token to hit a band reads worse than one that "
            "missed it honestly.", ""]

    d = ROOT / "data" / handle
    (d / "voice.md").write_text("\n".join(out))
    (d / "voice.json").write_text(json.dumps(
        {"handle": handle, "n": len(ts), "bands": bands,
         "distinctive": [{"phrase": g, "n": k, "lift": lift} for g, k, lift in marks],
         "openers": [{"opener": g, "n": k} for g, k in ops]}, indent=2))
    print("\n".join(out))
    print(f"\nwrote data/{handle}/voice.md and voice.json", file=sys.stderr)


def spoken_seconds(text, wpm):
    """How long THIS person takes to say it.

    The creators' own pace is theirs, not the writer's. Sizing a script to a
    creator's words-per-minute hands someone a script that runs long the moment
    they actually read it aloud -- which is the kind of error that only shows up
    off-screen, after the writing is done.
    """
    return 60 * len(WORD.findall(text)) / wpm


def cmd_check(a):
    handles = [h.lstrip("@") for h in a.like.split(",")]
    text = pathlib.Path(a.script).read_text()
    # Strip any markdown scaffolding so we measure the spoken words only.
    text = re.sub(r"^\s*(#+|[-*>]|\d+\.)\s*", "", text, flags=re.M)
    text = re.sub(r"\*\*|__|\*|`", "", text)
    got = measure(text)
    if not got:
        sys.exit("nothing measurable in that script")

    pooled = {}
    for h in handles:
        p = ROOT / "data" / h / "voice.json"
        if not p.exists():
            sys.exit(f"no voice profile for @{h} — run: ./framezero voice {h}")
        for k, b in json.loads(p.read_text())["bands"].items():
            pooled.setdefault(k, []).append(b)
    bands = {k: {"lo": min(x["lo"] for x in v), "hi": max(x["hi"] for x in v)}
             for k, v in pooled.items()}

    # Runtime bands come from the creators' winners; pace comes from the writer.
    durs = []
    for h in handles:
        r = ROOT / "data" / h / "ranked.json"
        if r.exists():
            durs += [x["duration"] for x in json.loads(r.read_text())["study_set"]
                     if x.get("cohort") == COHORT and x.get("duration")]
    secs = spoken_seconds(text, a.wpm)

    print(f"\nvoice check — {a.script}  vs  " + ", ".join("@" + h for h in handles))
    if durs:
        lo, hi = min(durs), max(durs)
        verdict = ("ok" if lo <= secs <= hi else
                   "LONG ↓ cut" if secs > hi else "SHORT ↑ add")
        print(f"runtime at {a.wpm} wpm: {secs:.0f}s   "
              f"their winners ran {lo:.0f}–{hi:.0f}s   {verdict}")
        if secs > hi:
            over = len(WORD.findall(text)) - int(hi * a.wpm / 60)
            print(f"  ~{over} words over. Cut a whole beat, not adjectives.")
    print(f"{'dial':<26}{'script':>9}{'target':>16}  verdict")
    print("-" * 68)
    off = []
    for k, b in bands.items():
        v, lo, hi = got[k], b["lo"], b["hi"]
        if v < lo:
            verdict, d = "LOW  ↑ raise", (lo - v) / (abs(lo) + 1e-9)
        elif v > hi:
            verdict, d = "HIGH ↓ lower", (v - hi) / (abs(hi) + 1e-9)
        else:
            verdict, d = "ok", 0.0
        if d:
            off.append((d, k, verdict))
        print(f"{k:<26}{fmt(v):>9}{fmt(lo)+' – '+fmt(hi):>16}  {verdict}")
    print("-" * 68)

    if not off:
        print("all dials inside the band.")
    else:
        off.sort(reverse=True)
        print(f"{len(off)} of {len(bands)} dials off. Worst first:")
        for d, k, verdict in off[:4]:
            print(f"  {verdict.split()[0]:<5} {k}   ({d*100:.0f}% outside)")

    used = []
    for h in handles:
        for m in json.loads((ROOT / "data" / h / "voice.json").read_text())["distinctive"]:
            if re.search(rf"(?<!\w){re.escape(m['phrase'])}(?!\w)", text, re.I):
                used.append(m["phrase"])
    if used:
        print(f"\nsignature phrases used: {', '.join(sorted(set(used)))}")
    else:
        print("\nsignature phrases used: none — the script does not sound "
              "like anyone in particular yet.")
    print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("profile", help="derive a creator's voice fingerprint")
    p.add_argument("handle")
    p.add_argument("--project", help="compare against the project's other creators")

    c = sub.add_parser("check", help="score a draft against a creator's voice")
    c.add_argument("script")
    c.add_argument("--like", required=True, help="handle, or comma-separated handles")
    c.add_argument("--wpm", type=float, default=210,
                   help="YOUR speaking rate, not theirs. Time yourself reading "
                        "a script aloud: words / minutes. Default 210 is the "
                        "creators' median and is probably too fast for you.")

    a = ap.parse_args()
    (cmd_profile if a.cmd == "profile" else cmd_check)(a)
