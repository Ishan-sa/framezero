#!/usr/bin/env python3
"""Pool every creator studied for a mode and decide which findings replicate.

This is the stage that separates a rule from a coincidence, and it is the one
thing no off-the-shelf tool does.

A pattern measured on ONE creator is that creator's habit. You only learn
whether it is a property of the format by checking whether it holds for
somebody else making the same kind of content. In this project's own first
run, a beautifully clean length rule -- zero overlap between cohorts --
evaporated the moment a second creator was added, and the two creators turned
out to point in opposite directions.

So every feature gets a verdict:

  REPLICATED   same direction, meaningful gap, in 2+ creators. Trust it.
  SINGLE       strong for one creator, absent for the others. A bet, not a law.
  CONTESTED    creators point opposite ways. Treat as noise until resolved.
  DEAD         no creator shows a meaningful gap. Stop repeating it as advice.

Writes data/_projects/<project>/<mode>.md
"""
import json, pathlib, sys, argparse, statistics as st

BIN = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(BIN))
import project as P
import report as R

ROOT = BIN.parent
STRONG, WEAK = 30, 15          # percentage-point gaps
CORR_DEAD = 0.10               # |r| below this is no relationship


def measure(handle, famous):
    """Per-creator cohort features. None if the creator isn't ready yet."""
    d = ROOT / "data" / handle
    rf = d / "ranked.json"
    if not rf.exists():
        return None
    ranked = json.loads(rf.read_text())
    tdir = d / "transcripts"
    coh = {"winner": [], "control": []}
    for r in ranked["study_set"]:
        t = tdir / f"{r['code']}.txt"
        if not t.exists():
            continue
        text = R.body_of(t)
        if len(text.split()) < 15:
            continue
        coh[r["cohort"]].append(R.features(text, r.get("duration"), famous))
    if not coh["winner"] or not coh["control"]:
        return None
    out = {"n_w": len(coh["winner"]), "n_c": len(coh["control"]), "flags": {}}
    for k in coh["winner"][0]:
        if k.startswith("_") or coh["winner"][0][k] is None:
            continue
        w = 100 * sum(1 for f in coh["winner"] if f[k]) / len(coh["winner"])
        c = 100 * sum(1 for f in coh["control"] if f[k]) / len(coh["control"])
        out["flags"][k] = (w, c, w - c)
    out["mags"] = {}
    for key, label in (("_famous_count", "famous entities in open (mean)"),
                       ("_words", "words (median)"),
                       ("_wpm", "words per minute (median)")):
        wv = [f[key] for f in coh["winner"] if f.get(key) is not None]
        cv = [f[key] for f in coh["control"] if f.get(key) is not None]
        if wv and cv:
            fn = st.mean if key == "_famous_count" else st.median
            out["mags"][label] = (fn(wv), fn(cv))
    out["corr_duration"], out["corr_n"] = R.corr(
        [(x.get("outlier"), x.get("duration")) for x in ranked["all_ranked"]])
    out["reels"] = ranked["reel_count"]
    out["median_plays"] = ranked["median_plays"]
    return out


def verdict(gaps):
    """gaps: list of (handle, percentage-point gap)."""
    sized = [(h, g) for h, g in gaps if abs(g) >= WEAK]
    if not sized:
        return "DEAD", "no creator shows a meaningful gap"
    pos = [g for _, g in sized if g > 0]
    neg = [g for _, g in sized if g < 0]
    if pos and neg:
        return "CONTESTED", "creators point in opposite directions"
    if len(sized) >= 2:
        d = "more common in winners" if pos else "more common in controls"
        return "REPLICATED", f"{len(sized)} creators, {d}"
    h = sized[0][0]
    return "SINGLE", f"only @{h}"


def main(project, mode):
    cfg = P.load(project)
    if mode not in cfg["modes"]:
        sys.exit(f"project '{project}' has no mode '{mode}'. "
                 f"modes: {', '.join(cfg['modes']) or '(none)'}")
    handles = cfg["modes"][mode].get("creators", [])
    famous = R.famous_re(project)

    data, skipped = {}, []
    for h in handles:
        m = measure(h, famous)
        (data.__setitem__(h, m) if m else skipped.append(h))

    if not data:
        sys.exit(f"no creator under '{mode}' has a transcribed study set yet")

    L = [f"# {mode} — cross-creator findings",
         f"\nProject **{project}** · niche: {cfg['niche']['label']}\n"]
    L += ["| creator | reels | median plays | study set |", "|---|---|---|---|"]
    for h, m in data.items():
        L.append(f"| @{h} | {m['reels']} | {m['median_plays']:,.0f} | "
                 f"{m['n_w']}W / {m['n_c']}C |")
    if skipped:
        L.append(f"\n> Not yet transcribed, so excluded: "
                 f"{', '.join('@' + s for s in skipped)}")
    if len(data) < 2:
        L.append("\n> **Only one creator here.** Nothing can replicate against "
                 "a sample of one — every finding below is that creator's "
                 "habit until a second creator is added. Add one before "
                 "trusting any of it.")

    L += ["\n## Verdicts\n",
          "| feature | " + " | ".join(f"@{h}" for h in data) + " | verdict |",
          "|---" * (len(data) + 2) + "|"]
    keys = sorted({k for m in data.values() for k in m["flags"]})
    rows = []
    for k in keys:
        gaps = [(h, m["flags"][k][2]) for h, m in data.items() if k in m["flags"]]
        v, why = verdict(gaps)
        cells = []
        for h, m in data.items():
            if k not in m["flags"]:
                cells.append("—")
            else:
                w, c, g = m["flags"][k]
                cells.append(f"{w:.0f}% vs {c:.0f}% ({g:+.0f})")
        rows.append((v, k, cells, why))
    order = {"REPLICATED": 0, "SINGLE": 1, "CONTESTED": 2, "DEAD": 3}
    for v, k, cells, why in sorted(rows, key=lambda r: (order[r[0]], r[1])):
        tag = f"**{v}**" if v in ("REPLICATED", "CONTESTED") else v
        L.append(f"| {k} | " + " | ".join(cells) + f" | {tag} — {why} |")

    mag_keys = sorted({k for m in data.values() for k in m["mags"]})
    if mag_keys:
        L += ["\n## Magnitudes\n",
              "A boolean can saturate where the underlying quantity still "
              "separates the cohorts — check these when a flag reads 100% "
              "against 100%.\n",
              "| measure | " + " | ".join(f"@{h}" for h in data) + " |",
              "|---" * (len(data) + 1) + "|"]
        for k in mag_keys:
            cells = []
            for h, m in data.items():
                if k not in m["mags"]:
                    cells.append("—")
                else:
                    w, c = m["mags"][k]
                    cells.append(f"{w:.2f} vs {c:.2f}")
            L.append(f"| {k} | " + " | ".join(cells) + " |")

    L.append("\n## Duration\n")
    L.append("Checked across each creator's whole catalogue, not the study "
             "set — the check that kills findings which only look real at the "
             "tails.\n")
    L.append("| creator | Pearson r (log outlier vs duration) | reels |")
    L.append("|---|---|---|")
    live = []
    for h, m in data.items():
        r, n = m["corr_duration"], m["corr_n"]
        if r is None:
            L.append(f"| @{h} | too few reels | {n} |")
            continue
        live.append(abs(r))
        L.append(f"| @{h} | {r:+.3f} "
                 f"{'**dead**' if abs(r) < CORR_DEAD else 'real'} | {n} |")
    if live and max(live) < CORR_DEAD:
        L.append("\n**Length is not a lever for this mode.** No creator shows "
                 "a relationship between duration and performance. Do not cut "
                 "a good beat to hit a runtime number.")

    L.append("\n## How to read this\n")
    L.append("**REPLICATED** findings are what belongs in a skill as a rule. "
             "**SINGLE** findings are worth trying and measuring, and must be "
             "labelled as one creator's habit. **CONTESTED** and **DEAD** "
             "findings must not appear as advice — silence is better than a "
             "confident rule that is noise.\n")

    out = ROOT / "data" / "_projects" / project
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{mode}.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\n-> {out / (mode + '.md')}", file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("mode")
    a = ap.parse_args()
    main(a.project, a.mode)
