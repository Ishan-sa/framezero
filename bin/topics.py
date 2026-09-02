#!/usr/bin/env python3
"""Which SUBJECTS beat this creator's own baseline — across the whole catalogue.

The rest of the pipeline studies ~30 reels in depth and asks "how is this
written?". This asks the cheaper, blunter question first: **what is it about?**

A creator averaging 10,000 plays who reliably hits 50,000 on one subject has
told you something you can act on tomorrow, and you do not need a single
transcript to find it. Captions and play counts are already on disk for every
reel in the index, so this stage makes no requests and costs nothing to re-run.

Topics are found through three independent lenses, because no one of them is
trustworthy alone:

  * **declared** — topics YOU define in a spec file. The only lens that knows
    your niche's real vocabulary. Use it.
  * **hashtags** — what the creator says the reel is about. Cheap and explicit,
    but hashtag blocks are often copy-pasted boilerplate that describes the
    account rather than the reel.
  * **terms** — words and pairs mined from the caption body. Finds subjects the
    creator never tagged, including product and tool names, at the cost of
    noise.

Every topic is scored in **outlier** units — a reel's plays over the median of
its own neighbours within ±90 days — so a topic cannot look good merely because
the creator posted about it while they were growing.

Two guards do the real work here, because without them this stage is a random
number generator with a confident tone:

  * **Significance.** Testing 600 mined terms against one catalogue guarantees
    that some clear any fixed threshold by luck. Each topic gets a rank-sum
    test against the rest of the catalogue, and the whole family is then held
    to a Benjamini-Hochberg false-discovery rate. A topic that does not survive
    is reported as inconclusive, not as a finding.
  * **Nouniness.** A bare lowercase word is nearly always an adjective or a
    verb — "easy", "complex", "remove" — and those are framing, not subject.
    Single words are kept only when the creator capitalises them mid-sentence,
    which is the free test for a product, brand or place name. Phrases are kept
    regardless, since two words together are usually about something.

Three things it is honest about:

  * A caption is not the video. A reel can be about something its caption never
    mentions, and this lens will miss it.
  * Median, never mean, and a hit rate alongside it. One viral reel should not
    be able to promote a topic on its own.
  * Correlation. A topic that overperforms was not necessarily the *cause*;
    it is a place to look, which is all a brief can honestly be.

Writes data/<handle>/topics.md, topics.json, topics.csv
"""
import json, pathlib, argparse, sys, re, csv, math
import statistics as st
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import rank

ROOT = pathlib.Path(__file__).resolve().parent.parent

HASHTAG = re.compile(r"#(\w+)")
URL = re.compile(r"https?://\S+")
MENTION = re.compile(r"@[A-Za-z0-9_.]+")
RAWWORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’+.-]*")
SENTENCE = re.compile(r"[.!?\n•|·–—:;]+")

# Ordinary English. Nothing here can ever be a topic.
STOP = set("""
a about above after again against all am an and any are aren't as at be because
been before being below between both but by can can't cannot could couldn't did
didn't do does doesn't doing don't down during each few for from further had
hadn't has hasn't have haven't having he her here hers herself him himself his
how i i'm i've if in into is isn't it it's its itself just let's me more most
mustn't my myself no nor not of off on once only or other ought our ours
ourselves out over own same shan't she should shouldn't so some such than that
that's the their theirs them themselves then there these they this those through
to too under until up very was wasn't we were weren't what when where which
while who whom why with won't would wouldn't you your yours yourself yourselves
i'm we're they're you're he's she's there's who's isn't wasn't don't didn't
""".split())

# Adjectives, adverbs and all-purpose verbs. These describe HOW something is
# framed, never what it is about, and left in they dominate the table --
# "easy", "crazy" and "insane" outrank every actual subject.
FRAMING = set("""
easy easier easiest hard harder hardest simple simpler simply quick quicker
quickly fast faster fastest slow slowly instant instantly crazy insane wild
unreal amazing incredible awesome perfect perfectly powerful mad nuts sick
huge massive tiny small big bigger biggest little great good better best bad
worse worst nice cool weird strange scary terrifying beautiful gorgeous stunning
complex complicated advanced basic entire whole full complete completely total
totally absolutely literally actually really honestly seriously definitely
probably maybe almost nearly barely hardly quite pretty super ultra mega
new newer newest old older oldest latest recent current modern future
free cheap expensive worth
make makes made making build builds built building create creates created
creating use uses used using get gets got getting take takes took taking
give gives gave giving go goes going went come comes came coming
see sees saw seeing look looks looked looking watch watches watched
show shows showed showing tell tells told telling say says said saying
want wants wanted need needs needed try tries tried trying start starts started
starting stop stops stopped keep keeps kept turn turns turned
know knows knew think thinks thought find finds found run runs ran
add adds added remove removes removed change changes changed
work works worked working help helps helped let lets
be been being is are was were am do does did done have has had
can could will would should must may might shall
one two three four five ten hundred thousand million billion first second
last next final another other others every each all any both same different
thing things stuff way ways time times day days week weeks month months year
years today tomorrow yesterday now then never always ever again still yet
here there where when why how what who which whose
guy guys man men woman women people person someone anyone everyone nobody
lot lots bit much many more less least most few several
""".split())

# Social-media boilerplate. These words describe the ACT of posting, not the
# subject of the post, and they otherwise dominate every caption corpus.
BOILERPLATE = set("""
comment comments commenting dm dms link links bio follow follows following
followers save saved saves share shares shared tag tags tagged subscribe
subscribed like likes liked video videos reel reels reelsinstagram post posts
posted content watch watching full below above word send sending sent
drop dropping check checking click swipe caption story stories page account
profile hey welcome back thanks thank please info details copy paste
steps step tutorial breakdown guide access join grab download link's
credit credits repost ig instagram viral trending fyp explore explorepage
""".split())

DROP = STOP | FRAMING | BOILERPLATE

# The verdict bands. A topic must clear a real margin AND survive the
# false-discovery correction before it is called a finding.
OVER, UNDER = 1.30, 0.77
HIT = 1.5      # a reel "hits" when it beats its neighbourhood by half again
NOUNY = 0.45   # share of mid-sentence uses that must be capitalised
MIN_OCC = 3    # occurrences before the capitalisation test means anything


# ---------------------------------------------------------------- statistics

def normal_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def rank_map(reels):
    """Average ranks of every reel's outlier score, computed once.

    Every topic test is then a sum of lookups rather than a re-sort, which is
    what makes testing six hundred candidates cheap."""
    vals = sorted((r["outlier"], r["code"]) for r in reels)
    ranks, ties, i = {}, [], 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j + 1][0] == vals[i][0]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[vals[k][1]] = avg
        if j > i:
            ties.append(j - i + 1)
        i = j + 1
    return ranks, ties


def ranksum(codes, ranks, n_all, ties):
    """Mann-Whitney U, normal approximation with tie correction.

    Asks: if these n reels had been drawn at random from the catalogue, how
    often would they rank this high? Rank-based on purpose -- play counts are
    violently skewed and a t-test on them would believe anything."""
    n1 = len(codes)
    n2 = n_all - n1
    if n1 < 3 or n2 < 3:
        return None, 1.0
    r1 = sum(ranks[c] for c in codes)
    u = r1 - n1 * (n1 + 1) / 2.0
    mu = n1 * n2 / 2.0
    tie = sum(t ** 3 - t for t in ties)
    var = (n1 * n2 / (n_all * (n_all - 1.0))) * (
        (n_all ** 3 - n_all) / 12.0 - tie / 12.0)
    if var <= 0:
        return None, 1.0
    z = (u - mu) / math.sqrt(var)
    return round(z, 2), 2.0 * (1.0 - normal_cdf(abs(z)))


def bh_threshold(pvals, q):
    """Benjamini-Hochberg: the largest p that still controls the false
    discovery rate at q across this family of tests.

    Bonferroni would be the conservative choice and would return nothing on a
    catalogue this size. FDR is the honest middle: of the topics reported,
    about q of them are expected to be noise, and that is stated in the output
    rather than hidden."""
    m = len(pvals)
    if not m:
        return 0.0
    thr = 0.0
    for i, p in enumerate(sorted(pvals), 1):
        if p <= i / m * q:
            thr = p
    return thr


# ------------------------------------------------------------------- lenses

def load(handle, since=None):
    f = ROOT / "data" / handle / "index.json"
    if not f.exists():
        sys.exit(f"no index for @{handle} — run: python3 bin/scrape.py {handle}")
    idx = json.loads(f.read_text())
    reels = [p for p in idx.get("posts") or []
             if p.get("is_reel") and p.get("play_count")]
    if since:
        cut = datetime.strptime(since, "%Y-%m-%d").replace(
            tzinfo=timezone.utc).timestamp()
        reels = [r for r in reels if (r.get("taken_at") or 0) >= cut]
    if not reels:
        sys.exit(f"no reels with play counts for @{handle}")
    # The same baseline the rest of the tool uses. A topic measured in raw
    # views would just rediscover when the creator was growing.
    rank.score(reels, window_days=90)
    return idx, [r for r in reels if r.get("outlier") is not None]


def body(caption):
    """The caption minus the machinery: links, @s, and the hashtag block.

    Hashtags get their own lens. Leaving them in the body too would let one
    copy-pasted tag block masquerade as a recurring subject."""
    t = caption or ""
    t = URL.sub(" ", t)
    t = MENTION.sub(" ", t)
    return HASHTAG.sub(" ", t)


def tokens(text):
    """(word, starts_a_sentence) over a caption body.

    The flag is the whole point: a capital letter at the start of a sentence
    says nothing, and one in the middle says "this is a name"."""
    for sent in SENTENCE.split(text.replace("\u2019", "'")):
        ws = RAWWORD.findall(sent)
        for i, w in enumerate(ws):
            yield w.strip(".'’-+"), i == 0


def nouny(reels):
    """Which single words the creator capitalises mid-sentence.

    In an AI niche this returns the tool names; in real estate it returns the
    neighbourhoods. Either way it is the free, language-agnostic way to keep
    "Sora" and drop "easy" without shipping a part-of-speech tagger."""
    seen, caps = Counter(), Counter()
    for r in reels:
        toks = list(tokens(body(r.get("caption"))))
        mid = [w for w, start in toks if not start and w]
        if not mid:
            continue
        # A caption written in ALL CAPS or Title Case carries no signal here,
        # and there are enough of those to poison the count.
        if sum(1 for w in mid if w[:1].isupper()) > 0.6 * len(mid):
            continue
        for w in mid:
            seen[w.lower()] += 1
            if w[:1].isupper():
                caps[w.lower()] += 1
    return {w: caps[w] / n for w, n in seen.items() if n >= MIN_OCC}


def terms(text, names):
    """Unigrams and adjacent bigrams. Single words must look like names."""
    words = [w.lower() for w, _ in tokens(text) if w]
    words = [w for w in words if len(w) > 2 and not w.isdigit()]
    out = set()
    for i, w in enumerate(words):
        if w not in DROP and names.get(w, 0.0) >= NOUNY:
            out.add(w)
        if i + 1 < len(words):
            a, b = w, words[i + 1]
            # A phrase survives only if neither half is a function word or
            # posting boilerplate. "china just" and "it's called" are
            # fragments of a sentence; "new cohort" is a subject, so framing
            # words are still allowed to modify a noun.
            if a not in STOP and b not in STOP \
                    and a not in BOILERPLATE and b not in BOILERPLATE:
                out.add(f"{a} {b}")
    return out


def measure(rows, med_plays, ranks, n_all, ties):
    """The stat block for one topic. Median, never mean."""
    o = sorted(r["outlier"] for r in rows)
    p = sorted(r["play_count"] for r in rows)
    codes = [r["code"] for r in rows]
    best = max(rows, key=lambda r: r["outlier"])
    lift = st.median(o)
    z, pv = ranksum(codes, ranks, n_all, ties)
    return {
        "reels": len(rows),
        "lift": round(lift, 2),
        "median_plays": int(st.median(p)),
        "vs_account_plays": round(st.median(p) / med_plays, 2)
        if med_plays else None,
        "hit_rate": round(sum(1 for x in o if x >= HIT) / len(rows), 2),
        "z": z, "p": pv,
        "best_outlier": round(best["outlier"], 2),
        "best_plays": best["play_count"],
        "best_code": best["code"],
        "verdict": "inconclusive",   # decided once the whole family is known
        "codes": codes,
    }


def by_membership(reels, assign, min_reels, med_plays, ranks, ties):
    buckets = defaultdict(list)
    for r in reels:
        for name in assign(r):
            buckets[name].append(r)
    return {name: measure(rows, med_plays, ranks, len(reels), ties)
            for name, rows in buckets.items() if len(rows) >= min_reels}


def prune(topics):
    """Drop a single word when a phrase containing it covers the same reels.

    Without this the table says "agent 1.8x" directly above "ai agent 1.8x"
    and wastes the reader's most valuable rows on a duplicate."""
    sets = {k: set(v["codes"]) for k, v in topics.items()}
    drop = set()
    for k in topics:
        if " " not in k:
            continue
        for w in k.split():
            s = sets.get(w)
            if s and len(s & sets[k]) >= 0.7 * len(s):
                drop.add(w)
    return {k: v for k, v in topics.items() if k not in drop}


def label_score(name):
    """How much of a name is actually about something."""
    return sum(1 for w in name.split() if w not in DROP)


def dedupe(items, overlap=0.8):
    """Collapse topics that cover the same reels.

    Eleven rows reading "new cohort", "cohort are", "webinar explain" are one
    boilerplate caption seen eleven ways, and they crowd every other finding
    off the page. Widest coverage and the most contentful label wins; the rest
    are recorded as aliases so nothing is silently thrown away."""
    order = sorted(items.items(),
                   key=lambda kv: (-kv[1]["reels"], -label_score(kv[0]),
                                   len(kv[0])))
    kept, sets = {}, {}
    for name, v in order:
        s = set(v["codes"])
        for k in sets:
            if len(s & sets[k]) >= overlap * min(len(s), len(sets[k])):
                kept[k]["aliases"].append(name)
                break
        else:
            v["aliases"] = []
            kept[name], sets[name] = v, s
    return kept


def read_spec(path):
    """User-defined topics — the lens that actually knows your niche.

    JSON: {"market update": ["market update", "interest rate"]}
    or plain text, one per line:  market update: market update, interest rate
    """
    p = pathlib.Path(path)
    if not p.exists():
        sys.exit(f"no topic spec at {path}")
    if p.suffix == ".json":
        spec = json.loads(p.read_text())
    else:
        spec = {}
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            name, kws = line.split(":", 1)
            spec[name.strip()] = [k.strip() for k in kws.split(",") if k.strip()]
    return {name: [re.compile(r"\b" + re.escape(k.lower()) + r"\b"
                              if k[:1].isalnum() else re.escape(k.lower()))
                   for k in kws]
            for name, kws in spec.items() if kws}


def judge(items, q):
    """Assign verdicts within ONE lens.

    The correction is applied per lens, not across all of them together: your
    declared topics are a handful of stated hypotheses, and holding them to the
    same correction as six hundred mined guesses would punish them for noise
    they did not generate."""
    thr = bh_threshold([v["p"] for v in items.values()], q)
    for v in items.values():
        v["significant"] = v["p"] <= thr
        if not v["significant"]:
            v["verdict"] = "inconclusive"
        elif v["lift"] >= OVER:
            v["verdict"] = "overperforms"
        elif v["lift"] <= UNDER:
            v["verdict"] = "underperforms"
        else:
            v["verdict"] = "at baseline"
    return {"threshold": thr, "tests": len(items)}


def build(handle, min_reels, spec_path, since, top, q):
    idx, reels = load(handle, since)
    med_plays = st.median([r["play_count"] for r in reels])
    ranks, ties = rank_map(reels)
    names = nouny(reels)

    lenses, stats = {}, {}
    lenses["hashtags"] = by_membership(
        reels,
        lambda r: {t.lower() for t in HASHTAG.findall(r.get("caption") or "")},
        min_reels, med_plays, ranks, ties)
    lenses["terms"] = prune(by_membership(
        reels, lambda r: terms(body(r.get("caption")), names),
        min_reels, med_plays, ranks, ties))
    if spec_path:
        spec = read_spec(spec_path)
        lenses["declared"] = by_membership(
            reels,
            lambda r: {n for n, rxs in spec.items()
                       if any(rx.search((r.get("caption") or "").lower())
                              for rx in rxs)},
            max(3, min_reels // 2), med_plays, ranks, ties)

    for name, items in lenses.items():
        stats[name] = judge(items, q)
        items = dedupe(items)
        lenses[name] = dict(sorted(items.items(), key=lambda kv: -kv[1]["lift"]))

    # The brief: surviving topics from any lens, deduped by the reels they
    # cover so three phrasings of one subject do not fill all five slots.
    def pick(verdict, reverse, limit=5):
        pool = [{"lens": ln, "topic": n, **v}
                for ln, items in lenses.items() for n, v in items.items()
                if v["verdict"] == verdict]
        pool.sort(key=lambda x: (-x["lift"] if reverse else x["lift"],
                                 -x["reels"]))
        out, seen = [], []
        for cand in pool:
            s = set(cand["codes"])
            if any(len(s & prev) >= 0.6 * min(len(s), len(prev))
                   for prev in seen):
                continue
            seen.append(s)
            out.append(cand)
            if len(out) >= limit:
                break
        return out

    brief = pick("overperforms", True)
    costs = pick("underperforms", False, 3)

    return {
        "handle": handle,
        "generated_at": int(datetime.now(timezone.utc).timestamp()),
        "reels_scored": len(reels),
        "median_plays": int(med_plays),
        "min_reels": min_reels,
        "fdr_q": q,
        "since": since,
        "spec": spec_path,
        "top": top,
        "names_detected": len(names),
        "lens_stats": stats,
        "brief": brief,
        "costs": costs,
        "lenses": lenses,
    }


# ------------------------------------------------------------------ output

def fmt_p(p):
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def rows_md(items, top):
    L = ["| topic | reels | lift | median plays | hit rate | p | best |",
         "|---|---:|---:|---:|---:|---:|---:|"]
    for name, v in list(items.items())[:top]:
        alias = v.get("aliases") or []
        name = name + (f" <sub>+{len(alias)} more phrasings</sub>" if alias else "")
        L.append(f"| {name} | {v['reels']} | **{v['lift']:.2f}×** | "
                 f"{v['median_plays']:,} | {int(v['hit_rate']*100)}% | "
                 f"{fmt_p(v['p'])} | {v['best_plays']:,} |")
    return L


def markdown(d):
    h, med = d["handle"], d["median_plays"]
    L = [f"# Topics — @{h}", "",
         f"What **{d['reels_scored']:,} reels** say about which subjects work "
         f"for this account. Their median reel does **{med:,} plays**.", "",
         "**lift** is the topic's median outlier score. A reel's outlier is its "
         "plays over the median of its own neighbours within ±90 days, so 1.00 "
         "is exactly typical *for this creator at the time they posted* and "
         "2.00 is double. **hit rate** is the share of that topic's reels that "
         f"beat their own neighbourhood by {HIT}× or more — the guard against "
         "one viral reel carrying a topic it does not deserve. **p** is a "
         "rank-sum test against the rest of the catalogue.", "",
         "Only topics that survive a Benjamini-Hochberg correction at "
         f"q={d['fdr_q']} appear as findings. Everything else is listed as "
         "inconclusive, because testing hundreds of candidate topics against "
         "one catalogue will always throw up a few spectacular coincidences.",
         ""]

    if d["brief"]:
        L += ["## The brief", "",
              "Surviving topics from any lens, deduplicated so three phrasings "
              "of one subject do not fill the list. This is the part to act on.",
              ""]
        for i, b in enumerate(d["brief"], 1):
            L.append(
                f"{i}. **{b['topic']}** — {b['reels']} reels at "
                f"**{b['lift']:.2f}× baseline**, median {b['median_plays']:,} "
                f"plays against {med:,} for the account. "
                f"{int(b['hit_rate']*100)}% of them beat their own "
                f"neighbourhood. Best: {b['best_plays']:,}. "
                f"<sub>({b['lens']} lens, p={fmt_p(b['p'])})</sub>")
        L.append("")
        if d["costs"]:
            L += ["**And what costs them:**", ""]
            for c in d["costs"]:
                L.append(
                    f"- **{c['topic']}** — {c['reels']} reels at only "
                    f"**{c['lift']:.2f}× baseline**, median "
                    f"{c['median_plays']:,} plays. "
                    f"<sub>({c['lens']} lens, p={fmt_p(c['p'])})</sub>")
            L.append("")
    else:
        L += ["## The brief", "",
              "**No subject survives the correction.** No topic with at least "
              f"{d['min_reels']} reels both runs {OVER}× this creator's "
              "baseline and clears the false-discovery threshold.", "",
              "That is a finding, not a failure: what separates this account's "
              "winners is not *what they are about*. Look at how they open and "
              f"how they are built instead — `./framezero hooks {h}` and "
              "`report.md`.", ""]

    order = [("declared", "Your topics",
              "The topics you defined. The only lens that knows your niche's "
              "real vocabulary — every other lens is inferring subject matter "
              "from word counts."),
             ("terms", "Mined from captions",
              "Phrases lifted from caption bodies, plus single words the "
              "creator capitalises mid-sentence — which is how tool, brand and "
              "place names get in while adjectives stay out."),
             ("hashtags", "By hashtag",
              "What the creator says each reel is about. Explicit, but hashtag "
              "blocks are often pasted wholesale and then describe the account "
              "rather than the reel.")]
    for key, title, note in order:
        items = d["lenses"].get(key)
        if not items:
            continue
        s = d["lens_stats"][key]
        L += [f"## {title}", "", note, ""]
        over = {k: v for k, v in items.items() if v["verdict"] == "overperforms"}
        under = {k: v for k, v in items.items() if v["verdict"] == "underperforms"}
        if over:
            L += ["**Make more of these**", ""] + rows_md(over, d["top"]) + [""]
        if under:
            L += ["**These cost them**", ""] + rows_md(
                dict(sorted(under.items(), key=lambda kv: kv[1]["lift"])),
                d["top"]) + [""]
        if not over and not under:
            L += [f"Nothing survives. {s['tests']} topics tested, none both "
                  "significant and outside the baseline band.", ""]
        L += [f"<sub>{s['tests']} topics tested in this lens; "
              + (f"p ≤ {s['threshold']:.4g} required to survive."
                 if s["threshold"] else
                 "none cleared the correction.") + "</sub>", ""]

    L += ["## What this cannot tell you", "",
          "- A caption is not the video. A reel about something its caption "
          "never names is invisible to every lens here.",
          "- These are correlations. A topic that overperforms is a place to "
          "look, not a proven cause — the hook and the structure travel with "
          "the subject.",
          f"- Topics under {d['min_reels']} reels are never tested. Lower "
          "`--min-reels` to see them, and trust them less.",
          f"- About {int(d['fdr_q']*100)}% of the topics reported above are "
          "expected to be noise. That is what the correction buys you: not "
          "certainty, a known error rate.",
          "- Nothing here is transferable *wording*. Take the subject, write it "
          f"in your own voice — `./framezero check draft.txt --like {h}`.", "",
          "## Next", "",
          f"- `data/{h}/topics.csv` — every topic, one row each, opens in Excel",
          f"- `./framezero hooks {h}` — how the winners open, not what they cover",
          f"- `./framezero run <project> --only {h}` — transcribe and find the "
          "structural deltas", ""]
    return "\n".join(L)


CSV_COLS = ["lens", "topic", "reels", "lift", "median_plays", "vs_account_plays",
            "hit_rate", "z", "p", "significant", "verdict",
            "best_outlier", "best_plays", "best_code"]


def write_csv(d, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLS)
        for lens, items in d["lenses"].items():
            for name, v in items.items():
                w.writerow([lens, name] + [v.get(c) for c in CSV_COLS[2:]])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("handle")
    ap.add_argument("--min-reels", type=int, default=6,
                    help="never test a topic with fewer reels (default 6)")
    ap.add_argument("--define", help="your own topic spec (.json or .txt) — the "
                                     "lens that knows your niche")
    ap.add_argument("--since", help="ignore reels before YYYY-MM-DD")
    ap.add_argument("--top", type=int, default=15,
                    help="rows per table (default 15)")
    ap.add_argument("--q", type=float, default=0.10,
                    help="false-discovery rate to hold topics to (default 0.10)")
    a = ap.parse_args()
    handle = a.handle.lstrip("@")

    d = build(handle, a.min_reels, a.define, a.since, a.top, a.q)
    out = ROOT / "data" / handle
    out.mkdir(parents=True, exist_ok=True)
    (out / "topics.json").write_text(json.dumps(d, indent=2, ensure_ascii=False))
    (out / "topics.md").write_text(markdown(d))
    write_csv(d, out / "topics.csv")
    tested = sum(s["tests"] for s in d["lens_stats"].values())
    kept = sum(1 for v in d["lenses"].values() for x in v.values()
               if x["verdict"] in ("overperforms", "underperforms"))
    print(f"  topics: {tested} tested, {kept} survived, "
          f"{len(d['brief'])} in the brief -> data/{handle}/topics.md",
          file=sys.stderr)
