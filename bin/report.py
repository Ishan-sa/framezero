#!/usr/bin/env python3
"""Mechanical winner-vs-control deltas, so the agent doesn't have to eyeball them.

An agent reading transcripts will find patterns whether or not they are there.
This stage computes the countable ones first, with both cohorts side by side,
so the qualitative pass starts from numbers instead of impressions.

Everything here is a FEATURE OF THE OPENING or a whole-reel statistic. None of
it is causal. A feature that splits the cohorts is a candidate; a feature that
does not is dead and should stop being repeated as advice.

Writes data/<handle>/report.md and prints it.
"""
import json, pathlib, re, argparse, math, statistics as st, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import project as P

ROOT = pathlib.Path(__file__).resolve().parent.parent

def famous_re(project):
    """Entities big enough that naming one borrows reach.

    Never hardcode this. It is niche-specific by definition, so it comes from
    the project -- either the vocabulary you declared or, better, the lexicon
    derived from what actually recurs across that niche's biggest accounts.
    """
    if not project:
        return None
    cfg = P.load(project)
    words = cfg["niche"].get("lexicon") or cfg["niche"].get("vocabulary") or []
    if not words:
        return None
    alts = "|".join(sorted((re.escape(w) for w in words), key=len, reverse=True))
    return re.compile(rf"(?<!\w)({alts})(?!\w)", re.I)
ANON = (r"(I just found|I found this|there'?s a (free|new)|this website|this tool|"
        r"this new AI tool|a free AI (tool|website|app))")
NEWSPEG = r"\b(just (released|launched|dropped|leaked|shipped|announced)|now (available|live))\b"
HEDGE = r"\b(I think|honestly|sort of|kind of|a little bit|somehow|probably|maybe|I guess)\b"


def body_of(path):
    lines = [re.sub(r"^\[\d+:\d+\]\s*", "", l)
             for l in path.read_text().split("\n") if l.startswith("[")]
    return " ".join(lines).strip()


def features(text, duration, famous):
    sents = re.split(r"(?<=[.?!])\s+", text)
    open2 = " ".join(sents[:2])
    words = text.split()
    return {
        "number in first 2 sentences": bool(re.search(r"[\d$]", open2)),
        "famous entity named in open": bool(famous.search(open2)) if famous else None,
        "anonymous-subject opener": bool(re.search(ANON, open2, re.I)),
        "news peg in open": bool(re.search(NEWSPEG, open2, re.I)),
        "question in first 2 sentences": "?" in open2,
        "first person in sentence 1": bool(re.search(r"\b(I|I'm|I've|my)\b", sents[0])),
        "_famous_count": (len(set(w.lower() for w in famous.findall(open2)))
                          if famous else None),
        "_words": len(words),
        "_hedges": len(re.findall(HEDGE, text, re.I)),
        "_wpm": len(words) / duration * 60 if duration else None,
    }


def corr(pairs):
    """Pearson r between log outlier and a numeric field."""
    pairs = [(a, b) for a, b in pairs if a and a > 0 and b]
    if len(pairs) < 10:
        return None, len(pairs)
    xs = [math.log(a) for a, _ in pairs]
    ys = [b for _, b in pairs]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return (num / den if den else None), n


def main(handle, project):
    d = ROOT / "data" / handle
    ranked = json.loads((d / "ranked.json").read_text())
    tdir = d / "transcripts"

    famous = famous_re(project)
    if project and famous is None:
        print("  no niche lexicon yet — run: bin/project.py lexicon <project>",
              file=sys.stderr)
    coh = {"winner": [], "control": []}
    for r in ranked["study_set"]:
        t = tdir / f"{r['code']}.txt"
        if not t.exists():
            continue
        text = body_of(t)
        if len(text.split()) < 15:        # music-only or failed transcript
            continue
        coh[r["cohort"]].append((r, features(text, r.get("duration"), famous)))

    W, C = coh["winner"], coh["control"]
    if not W or not C:
        sys.exit("need both cohorts transcribed — run listen.py first")

    L = [f"# Mechanical deltas — @{handle}\n",
         f"{len(W)} winners vs {len(C)} controls, transcribed. "
         f"{ranked['reel_count']} reels ranked.\n",
         "A feature that splits the cohorts is a **candidate**. A feature that "
         "does not is **dead** — stop repeating it as advice. None of this is "
         "causal.\n",
         "## Opening features\n",
         "| feature | winners | controls | split |", "|---|---|---|---|"]

    flags = [k for k in W[0][1]
             if not k.startswith("_") and W[0][1][k] is not None]
    for k in flags:
        w = sum(1 for _, f in W if f[k]); c = sum(1 for _, f in C if f[k])
        pw, pc = 100 * w / len(W), 100 * c / len(C)
        gap = pw - pc
        mark = "**strong**" if abs(gap) >= 30 else ("weak" if abs(gap) >= 15 else "dead")
        L.append(f"| {k} | {w}/{len(W)} ({pw:.0f}%) | {c}/{len(C)} ({pc:.0f}%) | "
                 f"{gap:+.0f}pp {mark} |")

    L += ["\n## Magnitudes\n", "| measure | winners | controls |", "|---|---|---|"]
    for key, label in [("_famous_count", "famous entities in open (mean)"),
                       ("_words", "words (median)"),
                       ("_hedges", "hedges (median)"),
                       ("_wpm", "words per minute (median)")]:
        wv = [f[key] for _, f in W if f[key] is not None]
        cv = [f[key] for _, f in C if f[key] is not None]
        if not wv or not cv:
            continue
        fn = st.mean if key == "_famous_count" else st.median
        L.append(f"| {label} | {fn(wv):.2f} | {fn(cv):.2f} |")

    for key, label in [("duration", "duration (median, s)")]:
        wv = [r[key] for r, _ in W if r.get(key)]
        cv = [r[key] for r, _ in C if r.get(key)]
        if wv and cv:
            L.append(f"| {label} | {st.median(wv):.0f} | {st.median(cv):.0f} |")

    L.append("\n## Whole-catalogue correlations\n")
    L.append("Computed over every ranked reel, not just the study set. This is "
             "the check that kills findings which only look real at the tails.\n")
    L.append("| field | Pearson r (log outlier) | n |")
    L.append("|---|---|---|")
    for field, label in [("duration", "duration")]:
        r, n = corr([(x.get("outlier"), x.get(field)) for x in ranked["all_ranked"]])
        if r is not None:
            verdict = "**dead**" if abs(r) < 0.1 else ("weak" if abs(r) < 0.3 else "**real**")
            L.append(f"| {label} | {r:+.3f} {verdict} | {n} |")

    out = "\n".join(L) + "\n"
    (d / "report.md").write_text(out)
    print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("handle")
    ap.add_argument("--project", help="use this project's niche lexicon")
    a = ap.parse_args()
    main(a.handle.lstrip("@"), a.project)
