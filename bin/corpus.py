#!/usr/bin/env python3
"""Assemble everything into one markdown corpus for the analysis step.

Deliberately not an API call. The analysis wants a long-context model
reading every transcript at once alongside the numbers, and framezero is
meant to run inside an agent you already pay for. So this stage produces
the input and hands it over.

Writes data/<handle>/corpus.md
"""
import json, pathlib, argparse, statistics, sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent


def when(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d") if ts else "?"


def table(rows):
    hdr = ("| code | cohort | outlier | plays | baseline | likes | comments | "
           "eng % | dur | posted |")
    sep = "|---|---|---|---|---|---|---|---|---|---|"
    out = [hdr, sep]
    for r in rows:
        out.append(
            f"| {r['code']} | {r.get('cohort','-')} | {r['outlier']}x | "
            f"{r['play_count']:,} | {r['baseline']:,.0f} | {r.get('like_count',0):,} | "
            f"{r.get('comment_count',0):,} | "
            f"{(r.get('engagement_rate') or 0)*100:.2f} | "
            f"{(r.get('duration') or 0):.0f}s | {when(r.get('taken_at'))} |")
    return "\n".join(out)


def main(handle):
    d = ROOT / "data" / handle
    ranked = json.loads((d / "ranked.json").read_text())
    tdir = d / "transcripts"
    prof = ranked.get("profile") or {}
    study = ranked["study_set"]
    winners = [r for r in study if r.get("cohort") == "winner"]
    controls = [r for r in study if r.get("cohort") == "control"]
    allr = ranked["all_ranked"]

    durs = [r["duration"] for r in allr if r.get("duration")]
    dur_txt = (f"Median duration: {statistics.median(durs):.0f}s. "
               if durs else "Duration: unavailable. ")
    L = []
    L.append(f"# Reel corpus: @{handle}\n")
    L.append(f"**{prof.get('full_name','')}** — {prof.get('followers',0):,} followers, "
             f"{prof.get('post_count',0)} posts, {ranked['reel_count']} reels analysed.\n")
    if prof.get("biography"):
        L.append("> " + prof["biography"].replace("\n", "\n> ") + "\n")
    L.append(f"Median reel: **{ranked['median_plays']:,.0f} plays**. "
             + dur_txt +
             f"Baseline window: ±{ranked['window_days']} days.\n")
    L.append("Every reel is scored against the median of its own neighbours in "
             "that window, not against raw views, so follower growth over time "
             "does not masquerade as performance.\n")

    L.append("## Full ranking\n")
    L.append(table(allr) + "\n")

    for label, cohort, note in [
        ("WINNERS", winners, "These beat the creator's own contemporaneous baseline."),
        ("CONTROLS", controls, "These UNDERperformed. They are here on purpose: the "
                               "signal is what the winners do that these do not."),
    ]:
        if not cohort:
            continue
        L.append(f"\n---\n\n# {label}\n\n{note}\n")
        for r in cohort:
            t = tdir / f"{r['code']}.txt"
            if not t.exists():
                continue
            L.append(f"\n## {r['code']} — {r['outlier']}x — {r['play_count']:,} plays "
                     f"— {when(r.get('taken_at'))}\n")
            L.append("```\n" + t.read_text().strip() + "\n```\n")

    (d / "corpus.md").write_text("\n".join(L))
    n = sum(1 for r in study if (tdir / f"{r['code']}.txt").exists())
    print(f"corpus.md: {n} transcripts, {len(winners)}W/{len(controls)}C "
          f"-> {d/'corpus.md'}", file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("handle")
    main(ap.parse_args().handle.lstrip("@"))
