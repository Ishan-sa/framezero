#!/usr/bin/env python3
"""Describe a whole account, not just its winning reels.

The rest of the pipeline answers "what should I write?". This answers the
question that comes before it: "who is this person, and are they even worth
studying?"

Everything here comes out of the index scrape -- no extra requests, no
transcription, no whisper. That matters: a dossier lands in about a minute,
where a full run takes the better part of an hour. So you can look at six
creators cheaply and commit the expensive pass to the two that earn it.

Three things it is honest about, because the data does not exist:

  * Follower history. Instagram gives one number, today. Growth is inferred
    from the play-count trajectory, which is a proxy and is labelled as one.
  * Undisclosed sponsorship. `paid_partnership` is the disclosed flag only.
    Brand handles in captions and tags catch more, never all.
  * Location. Present only where the creator tagged it, which is usually not.

Writes data/<handle>/profile.md, profile.json, posts.csv
"""
import json, pathlib, argparse, sys, re, csv, datetime as dt
import statistics as st
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent

HASHTAG = re.compile(r"#(\w+)")
MENTION = re.compile(r"@([A-Za-z0-9_.]+)")
WORD = re.compile(r"[A-Za-z']+")

# Caption CTAs. The closing beat of a script is a business decision, not a
# stylistic one, so it is worth knowing which one this account actually runs.
CTAS = [
    ("comment-to-DM", re.compile(r"\bcomment\s+[\"'‘“]?[A-Z0-9]{2,}\b|\bcomment\s+the\s+word\b", re.I)),
    ("link in bio", re.compile(r"\blink\s+in\s+(?:my\s+)?bio\b", re.I)),
    ("DM me", re.compile(r"\bdm\s+(?:me|us)\b", re.I)),
    ("follow", re.compile(r"\bfollow\s+(?:me|us|@|for\b)", re.I)),
    ("save this", re.compile(r"\bsave\s+(?:this|it)\b", re.I)),
    ("share/tag", re.compile(r"\b(?:tag|send)\s+(?:a|someone|this)\b", re.I)),
    ("free giveaway", re.compile(r"\b(?:completely\s+)?free\b.{0,24}\b(?:template|workflow|guide|course|blueprint|copy)\b", re.I)),
]

# A brand handle is one that shows up tagged or credited but is not the
# creator, not a person they collaborate with once, and recurs.
GENERIC_TAGS = {"instagram", "reels", "meta", "explore", "explorepage"}


def load(handle):
    f = ROOT / "data" / handle / "index.json"
    if not f.exists():
        sys.exit(f"no index for @{handle} — run: python3 bin/scrape.py {handle}")
    return json.loads(f.read_text())


def when(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc) if ts else None


def quarter(ts):
    d = when(ts)
    return f"{d.year} Q{(d.month - 1) // 3 + 1}" if d else None


def pct(n, d):
    return 100.0 * n / d if d else 0.0


def bar(v, hi, width=22):
    """A plain-text bar. The markdown is read by humans and agents both, and
    a shape is faster to read than a column of numbers."""
    n = 0 if not hi else max(1, round(width * v / hi)) if v else 0
    return "█" * n


def spread(reels):
    """Is there anything to learn from this account?

    An account whose reels all perform about the same has no signal in it --
    the winners are not doing anything different, they just got luckier. The
    ratio of the top decile to the median is the cheapest test of that, and
    it is the number that decides whether the expensive pass is worth running.
    """
    plays = sorted(p["play_count"] for p in reels if p.get("play_count"))
    if len(plays) < 12:
        return None
    med = st.median(plays)
    p90 = plays[int(len(plays) * 0.9)]
    p10 = plays[int(len(plays) * 0.1)]
    return {"median": int(med), "p90": p90, "p10": p10,
            "top_decile_multiple": p90 / med if med else 0,
            "bottom_decile_multiple": p10 / med if med else 0}


def cadence(posts):
    """Posts per month over the reachable catalogue."""
    by = Counter(quarter(p.get("taken_at")) for p in posts if p.get("taken_at"))
    return dict(sorted(by.items()))


def trajectory(reels):
    """Median plays per quarter. This is the growth proxy -- it is not follower
    history, and it moves with the algorithm as well as with the audience."""
    buckets = defaultdict(list)
    for p in reels:
        if p.get("play_count") and p.get("taken_at"):
            buckets[quarter(p["taken_at"])].append(p["play_count"])
    return {q: {"posts": len(v), "median_plays": int(st.median(v))}
            for q, v in sorted(buckets.items())}


def monetisation(posts, handle):
    disclosed = [p for p in posts if p.get("paid_partnership")]
    sponsors = Counter()
    for p in posts:
        sponsors.update(p.get("sponsors") or [])
    tagged = Counter()
    for p in posts:
        for h in (p.get("tagged") or []) + (p.get("coauthors") or []):
            if h and h.lower() != handle.lower() and h.lower() not in GENERIC_TAGS:
                tagged[h] += 1
    mentions = Counter()
    for p in posts:
        for h in MENTION.findall(p.get("caption") or ""):
            if h.lower() != handle.lower() and h.lower() not in GENERIC_TAGS:
                mentions[h] += 1
    ctas = Counter()
    for p in posts:
        cap = p.get("caption") or ""
        for name, rx in CTAS:
            if rx.search(cap):
                ctas[name] += 1
    return {
        "disclosed_partnerships": len(disclosed),
        "disclosed_rate_pct": round(pct(len(disclosed), len(posts)), 1),
        "sponsor_tags": sponsors.most_common(10),
        "recurring_tags": [(h, c) for h, c in tagged.most_common(12) if c > 1],
        "recurring_mentions": [(h, c) for h, c in mentions.most_common(12) if c > 1],
        "ctas": ctas.most_common(),
    }


def content_mix(posts):
    tags = Counter()
    for p in posts:
        tags.update(t.lower() for t in HASHTAG.findall(p.get("caption") or ""))
    kinds = Counter()
    for p in posts:
        kinds[p.get("product_type") or ("photo" if p.get("media_type") == 1
                                        else f"type{p.get('media_type')}")] += 1
    audio = Counter(((p.get("audio") or {}).get("type") or "unknown")
                    for p in posts if p.get("is_reel"))
    aspect = Counter()
    for p in posts:
        w, h = p.get("width"), p.get("height")
        if w and h:
            aspect[f"{round(w / h, 2)}"] += 1
    return {"hashtags": tags.most_common(20), "post_types": kinds.most_common(),
            "audio": audio.most_common(), "aspect": aspect.most_common(4)}


def durations(reels):
    d = sorted(p["duration"] for p in reels if p.get("duration"))
    if not d:
        return None
    return {"n": len(d), "median": round(st.median(d), 1),
            "p10": round(d[int(len(d) * 0.1)], 1),
            "p90": round(d[int(len(d) * 0.9)], 1),
            "min": round(d[0], 1), "max": round(d[-1], 1)}


def build(handle):
    idx = load(handle)
    prof = idx.get("profile") or {}
    posts = idx.get("posts") or []
    reels = [p for p in posts if p.get("is_reel")]
    played = [p for p in reels if p.get("play_count")]

    if posts and "paid_partnership" not in posts[0]:
        print("  note: this index predates the profile fields — re-scrape for "
              "brand deals, audio and tags (delete index.json, rerun scrape.py)",
              file=sys.stderr)

    plays = [p["play_count"] for p in played]
    eng = [(p.get("like_count", 0) or 0) + (p.get("comment_count", 0) or 0)
           for p in played]
    first, last = None, None
    ts = [p["taken_at"] for p in posts if p.get("taken_at")]
    if ts:
        first, last = when(min(ts)), when(max(ts))

    reach = {}
    if plays:
        reach = {
            "reels_with_plays": len(plays),
            "median_plays": int(st.median(plays)),
            "mean_plays": int(st.mean(plays)),
            "p90_plays": int(sorted(plays)[int(len(plays) * 0.9)]),
            "best_plays": max(plays),
            "worst_plays": min(plays),
            "total_plays": sum(plays),
            # Engagement against plays, not followers. Followers is a single
            # snapshot and would misprice every older reel.
            "engagement_pct_of_plays": round(
                100.0 * sum(eng) / sum(plays), 2) if sum(plays) else None,
            "plays_per_follower": round(
                st.median(plays) / prof["followers"], 2)
            if prof.get("followers") else None,
        }

    out = {
        "handle": handle,
        "generated_at": int(dt.datetime.now(dt.timezone.utc).timestamp()),
        "scraped_at": idx.get("scraped_at"),
        "identity": {
            "name": prof.get("full_name"),
            "bio": prof.get("biography"),
            "category": prof.get("category"),
            "verified": prof.get("is_verified"),
            "professional": prof.get("is_professional"),
            "followers": prof.get("followers"),
            "following": prof.get("following"),
            "posts_total": prof.get("post_count"),
            "posts_reachable": len(posts),
            "external_url": prof.get("external_url"),
            "bio_links": prof.get("bio_links") or [],
        },
        "catalogue": {
            "reels": len(reels),
            "non_reels": len(posts) - len(reels),
            "earliest_reachable": first.strftime("%Y-%m-%d") if first else None,
            "latest": last.strftime("%Y-%m-%d") if last else None,
            "complete": len(posts) >= (prof.get("post_count") or 0),
            "by_quarter": cadence(posts),
        },
        "reach": reach,
        "spread": spread(reels),
        "trajectory": trajectory(reels),
        "duration": durations(reels),
        "content": content_mix(posts),
        "monetisation": monetisation(posts, handle),
        "neighbours": prof.get("related_profiles") or [],
    }
    return out


def markdown(d):
    h = d["handle"]
    i, c, r = d["identity"], d["catalogue"], d["reach"]
    L = [f"# Profile — @{h}", ""]

    L += ["## Identity", "",
          f"**{i['name'] or h}**" + ("  ✔︎ verified" if i["verified"] else ""),
          ""]
    if i["bio"]:
        L += ["> " + i["bio"].replace("\n", "  \n> "), ""]
    L += ["| | |", "|---|---|",
          f"| followers | **{i['followers']:,}** |" if i["followers"] else "",
          f"| following | {i['following']:,} |" if i["following"] else "",
          f"| category | {i['category'] or '—'} |",
          f"| posts | {i['posts_total']:,} total, {i['posts_reachable']:,} reachable |"
          if i["posts_total"] else "",
          f"| link | {i['external_url']} |" if i["external_url"] else "", ""]
    if i["bio_links"]:
        L += ["Bio links: " + ", ".join(
            f"[{b['title'] or b['url']}]({b['url']})" for b in i["bio_links"]), ""]

    L += ["## Reach", ""]
    if r:
        L += ["| | |", "|---|---|",
              f"| median plays | **{r['median_plays']:,}** |",
              f"| mean plays | {r['mean_plays']:,} |",
              f"| top decile | {r['p90_plays']:,} |",
              f"| best / worst | {r['best_plays']:,} / {r['worst_plays']:,} |",
              f"| engagement | {r['engagement_pct_of_plays']}% of plays "
              "(likes + comments) |",
              f"| median plays per follower | {r['plays_per_follower']} |"
              if r.get("plays_per_follower") else "", "",
              "<sub>Engagement is measured against plays, not followers. "
              "Followers is a single snapshot taken today and would misprice "
              "every older reel.</sub>", ""]
    else:
        L += ["No play counts — the clips pass returned nothing for this "
              "account.", ""]

    s = d["spread"]
    L += ["## Is there anything to learn here?", ""]
    if not s:
        L += ["Fewer than 12 reels with play counts. Too few to judge.", ""]
    else:
        m = s["top_decile_multiple"]
        verdict = ("**Yes — wide spread.** Their best reels run "
                   f"{m:.1f}× their own median, so something separates them "
                   "and it is worth transcribing to find out."
                   if m >= 2.5 else
                   "**Marginal.** Their best reels run only "
                   f"{m:.1f}× their median. The winners may not be doing "
                   "anything different — study them, but expect thin findings."
                   if m >= 1.6 else
                   "**Probably not.** Their best reels run "
                   f"{m:.1f}× their median. That is a flat catalogue: there is "
                   "no meaningful winner/control delta to extract.")
        L += [verdict, "",
              f"- top decile: {s['p90']:,} ({m:.1f}× median)",
              f"- median: {s['median']:,}",
              f"- bottom decile: {s['p10']:,} "
              f"({s['bottom_decile_multiple']:.2f}× median)", ""]

    t = d["trajectory"]
    if t:
        hi = max(v["median_plays"] for v in t.values())
        L += ["## Trajectory", "",
              "Median plays per quarter. A growth *proxy* — Instagram gives no "
              "follower history, and this moves with the algorithm as well as "
              "with the audience.", "",
              "| quarter | reels | median plays | |", "|---|---:|---:|---|"]
        for q, v in t.items():
            L.append(f"| {q} | {v['posts']} | {v['median_plays']:,} | "
                     f"`{bar(v['median_plays'], hi)}` |")
        L.append("")

    L += ["## Catalogue", "",
          f"- **{c['reels']:,} reels**, {c['non_reels']:,} other posts",
          f"- reachable range: {c['earliest_reachable']} → {c['latest']}",
          f"- {'full catalogue reached' if c['complete'] else 'partial — Instagram paginates only so far back, so the true start is earlier'}",
          ""]
    types = d["content"]["post_types"]
    if types:
        L += ["Post types: " + ", ".join(f"`{k}` {v}" for k, v in types), ""]
    du = d["duration"]
    if du:
        L += [f"Reel duration: median **{du['median']}s**, "
              f"p10–p90 {du['p10']}–{du['p90']}s, range {du['min']}–{du['max']}s",
              ""]
    aud = d["content"]["audio"]
    if aud:
        tot = sum(v for _, v in aud)
        L += ["Audio: " + ", ".join(f"{k} {pct(v, tot):.0f}%" for k, v in aud), ""]

    L += ["## Content mix", ""]
    tags = d["content"]["hashtags"]
    if tags:
        L += ["Top hashtags:", "",
              " ".join(f"`#{t}`×{n}" for t, n in tags[:20]), ""]
    else:
        L += ["No hashtags in captions.", ""]

    m = d["monetisation"]
    L += ["## Monetisation", "",
          f"- **{m['disclosed_partnerships']} disclosed paid partnerships** "
          f"({m['disclosed_rate_pct']}% of posts)",
          "", "<sub>Disclosed only. Undisclosed sponsorship carries no flag; "
          "the tags and mentions below catch more of it, never all.</sub>", ""]
    if m["sponsor_tags"]:
        L += ["Sponsors: " + ", ".join(f"@{h} ×{n}" for h, n in m["sponsor_tags"]), ""]
    if m["recurring_tags"]:
        L += ["Recurring tagged accounts: "
              + ", ".join(f"@{h} ×{n}" for h, n in m["recurring_tags"]), ""]
    if m["recurring_mentions"]:
        L += ["Recurring @mentions in captions: "
              + ", ".join(f"@{h} ×{n}" for h, n in m["recurring_mentions"]), ""]
    if m["ctas"]:
        L += ["", "Caption CTAs — how they actually convert attention:", "",
              "| CTA | posts |", "|---|---:|"]
        L += [f"| {k} | {v} |" for k, v in m["ctas"]]
        L.append("")

    n = d["neighbours"]
    if n:
        L += ["## Who else to study", "",
              "Instagram's own related accounts for this profile. The cheapest "
              "shortlist of creators in the same lane.", "",
              ", ".join(f"@{x['handle']}" + ("✔︎" if x["verified"] else "")
                        for x in n if x.get("handle")), ""]

    L += ["## Next", "",
          f"- `./framezero run <project> --only {h}` — transcribe the winners "
          "and controls, and find what separates them",
          f"- `./framezero voice {h}` — measure how they sound",
          f"- `data/{h}/posts.csv` — every post, one row each, opens in Excel "
          "or Sheets", ""]
    return "\n".join(x for x in L if x is not None)


CSV_COLS = ["code", "url", "taken_at_iso", "is_reel", "product_type",
            "play_count", "like_count", "comment_count", "duration",
            "paid_partnership", "sponsors", "location", "audio_type",
            "caption"]


def write_csv(handle, path):
    """He asked for a spreadsheet. CSV is the version of that which needs no
    dependency and which an agent can also read."""
    idx = load(handle)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLS)
        for p in idx.get("posts") or []:
            d = when(p.get("taken_at"))
            w.writerow([
                p.get("code"), p.get("url"),
                d.strftime("%Y-%m-%d %H:%M") if d else "",
                p.get("is_reel"), p.get("product_type"), p.get("play_count"),
                p.get("like_count"), p.get("comment_count"), p.get("duration"),
                p.get("paid_partnership"), ";".join(p.get("sponsors") or []),
                p.get("location"), (p.get("audio") or {}).get("type"),
                (p.get("caption") or "").replace("\n", " ")[:500],
            ])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("handle")
    a = ap.parse_args()
    handle = a.handle.lstrip("@")

    d = build(handle)
    out = ROOT / "data" / handle
    (out / "profile.json").write_text(json.dumps(d, indent=2, ensure_ascii=False))
    (out / "profile.md").write_text(markdown(d))
    write_csv(handle, out / "posts.csv")
    print(f"  wrote data/{handle}/profile.md, profile.json, posts.csv",
          file=sys.stderr)
