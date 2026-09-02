#!/usr/bin/env python3
"""Who else should I be studying?

Every other command in this tool answers a question about a creator you have
already chosen. This one answers the question that comes before that, and it is
the question people actually get stuck on: the niche is full of accounts and
you do not know which fifteen are worth an hour of transcription.

Instagram's own "related accounts" would settle it, and the scraper asks for
them -- but that endpoint has been returning 401 for a while, and a tool that
only works when a third party feels like answering is not a tool.

So this reads what is already on disk. Creators tag each other, run collabs,
and name each other in captions, and every one of those handles is sitting in
index.json already paid for. A handle that shows up across several catalogues
is a neighbour by the niche's own reckoning rather than by anybody's guess.

Then, optionally, it checks them. `--probe` pulls each candidate's timeline --
no transcription, no whisper, just the index -- and reports median plays and
posting rate, because the discovery is worthless if half the names turn out to
be accounts nobody watches. That check has already killed one candidate that
looked perfect and turned out to run 150 plays a reel.

  python3 bin/neighbours.py                    every catalogue on disk
  python3 bin/neighbours.py <handle>           just this one's neighbours
  python3 bin/neighbours.py --probe --top 8    and check whether they are worth it
"""
import json, re, sys, pathlib, argparse, collections, statistics, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BIN = ROOT / "bin"

MENTION = re.compile(r"@([A-Za-z0-9._]{2,30})")

# Handles that are companies, not creators. A neighbour list dominated by
# @openai and @google is technically correct and completely useless -- everyone
# in this niche tags the labs they are talking about, so those handles carry no
# information about who makes similar CONTENT. The tool's whole premise is
# studying people who face the same audience you do.
CORPORATE = re.compile(
    r"^(?:openai|openaidevs|chatgpt|claudeai|anthropic|google|googleindia|"
    r"googledeepmind|googleforstartups|meta|metaai|instagram|youtube|tiktok|"
    r"microsoft|nvidia|apple|adobe|canva|notionhq|figma|slack|zapier|n8n\.io|"
    r"make\.hq|elevenlabsio|midjourney|perplexity\.ai|grok|xai|manus|"
    r"higgsfield\.ai|invideo\.io|runwayml|lumalabsai|krea\.ai|openart\.ai|"
    r"paypalopen|amazon|aws|linkedin)$", re.I)


def posts_of(handle):
    f = DATA / handle / "index.json"
    if not f.exists():
        return []
    d = json.loads(f.read_text())
    return d["posts"] if isinstance(d, dict) else d


def cited(handle):
    """Every other account this creator points at, and how often.

    Three signals, deliberately not weighted the same. A co-tag or a collab is
    a working relationship -- they were in the room. An @-mention in a caption
    is weaker: it is often just crediting the tool being demoed. Counting them
    equally buries the people under the products."""
    strong, weak = collections.Counter(), collections.Counter()
    for p in posts_of(handle):
        for key in ("coauthors", "tagged", "sponsors"):
            for u in (p.get(key) or []):
                u = u if isinstance(u, str) else (u.get("username") or "")
                if u:
                    strong[u.lstrip("@").rstrip(".")] += 1
        for u in MENTION.findall(p.get("caption") or ""):
            weak[u.rstrip(".")] += 1
    for c in (strong, weak):
        for h in list(c):
            if h.lower() == handle.lower() or CORPORATE.match(h):
                del c[h]
    return strong, weak


def gather(handles):
    """Rank candidates across every catalogue on disk.

    Appearing in two different creators' catalogues counts for far more than
    appearing twice in one, so `sources` sorts ahead of raw count. One account
    tagging someone 900 times is a business partner; two unrelated accounts
    both naming the same person is a niche."""
    rows = collections.defaultdict(
        lambda: {"strong": 0, "weak": 0, "sources": set()})
    for h in handles:
        strong, weak = cited(h)
        for u, n in strong.items():
            rows[u]["strong"] += n
            rows[u]["sources"].add(h)
        for u, n in weak.items():
            rows[u]["weak"] += n
            rows[u]["sources"].add(h)
    known = {h.lower() for h in handles}
    out = []
    for u, r in rows.items():
        if u.lower() in known:
            continue
        out.append({"handle": u, "strong": r["strong"], "weak": r["weak"],
                    "sources": sorted(r["sources"]),
                    "score": r["strong"] * 3 + r["weak"]})
    out.sort(key=lambda r: (-len(r["sources"]), -r["score"], r["handle"]))
    return out


# Pages to pull when probing. A screening question does not need a catalogue:
# three pages is roughly the last three dozen posts, which is plenty to tell an
# account with an audience from one without. Pulling everything turned a
# ten-candidate screen into a twenty-minute job, and the whole point of the
# screen is that it happens before you commit.
PROBE_PAGES = 3


def probe(handle):
    """Pull a sample of the timeline and say whether this account is worth an hour.

    Cheap on purpose: no transcription, and only the first few pages. The
    number that decides it is median plays -- an account whose reels do 150
    views has nothing to teach about reach, however good the content reads.

    A partial index is written to disk like any other, and `./framezero
    profile <handle>` will reuse it. That is deliberate for speed and wrong for
    analysis, so the index records how it was made and the caller is told to
    re-pull before studying anyone seriously."""
    d = DATA / handle / "index.json"
    partial = False
    if not d.exists():
        r = subprocess.run(
            [sys.executable, str(BIN / "scrape.py"), handle,
             "--max-pages", str(PROBE_PAGES)],
            capture_output=True, text=True)
        if r.returncode != 0:
            return {"handle": handle, "error": "no such account, or private"}
        partial = True
    posts = posts_of(handle)
    plays = sorted(p["play_count"] for p in posts
                   if p.get("is_reel") and p.get("play_count"))
    if not plays:
        return {"handle": handle, "reels": 0,
                "error": "no reels with play counts"}
    return {"handle": handle, "posts": len(posts), "reels": len(plays),
            "median_plays": int(statistics.median(plays)), "best": max(plays),
            "partial": partial}


# A median below this is not a creator to learn reach from. It is deliberately
# low -- the point is to catch accounts with no audience at all, not to rank
# the ones that have one.
FLOOR = 5_000


def markdown(rows, probes, handles):
    L = [f"# Neighbours — {', '.join('@' + h for h in handles)}", "",
         "Accounts these creators tag, collaborate with, or name in captions. "
         "This is the niche's own account of who belongs to it, taken from "
         "catalogues already on disk — no requests, no guessing.", "",
         "**sources** is how many of your creators point at them, and it is "
         "the column that matters. One account tagging somebody four hundred "
         "times is a business partner; two unrelated accounts naming the same "
         "person is a niche.", "",
         "| | handle | sources | collabs | mentions |",
         "|---|---|---:|---:|---:|"]
    for i, r in enumerate(rows, 1):
        L.append(f"| {i} | @{r['handle']} | {len(r['sources'])} "
                 f"| {r['strong']} | {r['weak']} |")
    if probes:
        L += ["", "## Worth studying?", "",
              "Each candidate's timeline, pulled and measured. No "
              "transcription — this is the cheap check that comes before the "
              "expensive one. An account below "
              f"{FLOOR:,} median plays is not a creator to learn reach from, "
              "however good the writing looks.", "",
              f"Newly-probed accounts are sampled at {PROBE_PAGES} pages, not "
              "pulled in full — enough to screen, not enough to study. Delete "
              "`data/<handle>/index.json` and re-pull before you analyse one.", "",
              "| handle | reels | median plays | best | verdict |",
              "|---|---:|---:|---:|---|"]
        for p in probes:
            if p.get("error"):
                L.append(f"| @{p['handle']} | — | — | — | {p['error']} |")
                continue
            ok = p["median_plays"] >= FLOOR
            L.append(f"| @{p['handle']} | {p['reels']} "
                     f"| **{p['median_plays']:,}** | {p['best']:,} "
                     f"| {'**study**' if ok else 'skip — no audience'} |")
    L += ["", "## What this cannot tell you", "",
          "- A tag is not an endorsement and not a similarity. Somebody your "
          "creator ran one collab with may make nothing like them.",
          "- Accounts nobody tags are invisible here, and the best creator in "
          "a niche is often the one who never collabs.",
          "- Corporate handles are filtered out by name. A company account "
          "not on that list will show up as a person.",
          "- Median plays says an account has an audience. It says nothing "
          "about whether they make what you want to make — read "
          "`data/<handle>/profile.md` before adding them to a project.", "",
          "## Next", "",
          "- `./framezero profile <handle>` — the full dossier, still free",
          "- add the ones that survive to `projects/<name>.json`"]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("handles", nargs="*", help="default: every catalogue on disk")
    ap.add_argument("--probe", action="store_true",
                    help="pull each candidate's timeline and check it has an audience")
    ap.add_argument("--top", type=int, default=10, help="candidates to keep")
    ap.add_argument("--min-sources", type=int, default=1,
                    help="only candidates cited by at least this many creators")
    a = ap.parse_args()

    handles = [h.lstrip("@") for h in a.handles] or sorted(
        p.parent.name for p in DATA.glob("*/index.json"))
    if not handles:
        sys.exit("no catalogues on disk — run ./framezero profile <handle> first")

    rows = [r for r in gather(handles) if len(r["sources"]) >= a.min_sources]
    rows = rows[:a.top]
    if not rows:
        sys.exit("no neighbours found in those catalogues")

    probes = []
    if a.probe:
        for r in rows:
            print(f"  probing @{r['handle']}…", file=sys.stderr, flush=True)
            probes.append(probe(r["handle"]))

    out = DATA / "_neighbours.md"
    out.write_text(markdown(rows, probes, handles))
    (DATA / "_neighbours.json").write_text(
        json.dumps({"from": handles, "candidates": rows, "probes": probes},
                   indent=2) + "\n")
    print(f"  neighbours: {len(rows)} candidates"
          f"{f', {len(probes)} probed' if probes else ''} -> {out}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
