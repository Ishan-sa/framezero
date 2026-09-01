#!/usr/bin/env python3
"""Score every reel against the creator's OWN local baseline, then pick a
study set of winners and controls.

Raw view sorting just surfaces a creator's recent work. What we want is the
reel that beat what that creator was normally doing AT THE TIME it posted.
So each reel is scored against the median play_count of its neighbours in a
+/- WINDOW_DAYS window. That controls for follower growth.

We keep controls (the worst performers) as well as winners. Studying only
winners teaches you what all their videos do, not what the winners do
differently. The delta is the whole point.

Writes data/<handle>/ranked.json
"""
import json, statistics, pathlib, argparse, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DAY = 86400


def score(reels, window_days=90, min_neighbours=5):
    w = window_days * DAY
    allplays = [r["play_count"] for r in reels if r.get("play_count")]
    global_median = statistics.median(allplays) if allplays else 1
    for r in reels:
        t, pc = r.get("taken_at"), r.get("play_count")
        if not t or not pc:
            r["baseline"], r["outlier"], r["baseline_n"] = None, None, 0
            continue
        near = [o["play_count"] for o in reels
                if o is not r and o.get("play_count") and o.get("taken_at")
                and abs(o["taken_at"] - t) <= w]
        if len(near) >= min_neighbours:
            base, n = statistics.median(near), len(near)
        else:
            base, n = global_median, 0
        r["baseline"] = base
        r["baseline_n"] = n
        r["outlier"] = round(pc / base, 3) if base else None
        eng = (r.get("like_count") or 0) + (r.get("comment_count") or 0)
        r["engagement_rate"] = round(eng / pc, 5) if pc else None
        r["comment_ratio"] = round((r.get("comment_count") or 0) / pc, 5) if pc else None
    return reels


def main(handle, top, bottom, window):
    d = ROOT / "data" / handle
    idx = json.loads((d / "index.json").read_text())
    reels = [p for p in idx["posts"] if p.get("is_reel") and p.get("play_count")]
    if not reels:
        sys.exit("no reels with play counts in index.json")
    score(reels, window)
    ranked = sorted([r for r in reels if r["outlier"] is not None],
                    key=lambda r: r["outlier"], reverse=True)
    winners = ranked[:top]
    controls = ranked[-bottom:] if len(ranked) >= top + bottom else []
    for r in winners:
        r["cohort"] = "winner"
    for r in controls:
        r["cohort"] = "control"
    out = {
        "handle": handle,
        "profile": idx.get("profile"),
        "reel_count": len(reels),
        "window_days": window,
        "median_plays": statistics.median([r["play_count"] for r in reels]),
        "study_set": winners + controls,
        "all_ranked": ranked,
    }
    (d / "ranked.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"{len(reels)} reels | median {out['median_plays']:,.0f} plays", file=sys.stderr)
    print(f"study set: {len(winners)} winners + {len(controls)} controls", file=sys.stderr)
    for r in winners[:10]:
        cap = r["caption"].replace("\n", " ")[:52]
        print(f"  W {r['outlier']:>5.2f}x {r['play_count']:>8,}  {r['code']}  {cap}",
              file=sys.stderr)
    for r in controls[:5]:
        cap = r["caption"].replace("\n", " ")[:52]
        print(f"  C {r['outlier']:>5.2f}x {r['play_count']:>8,}  {r['code']}  {cap}",
              file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("handle")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--bottom", type=int, default=15)
    ap.add_argument("--window", type=int, default=90)
    a = ap.parse_args()
    main(a.handle.lstrip("@"), a.top, a.bottom, a.window)
