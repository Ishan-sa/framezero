#!/usr/bin/env python3
"""Projects: a niche, a set of content modes, and creators studied per mode.

framezero started hardcoded to one person's niche. Three things were baked in
and all three are now per-project:

  * the whisper seed vocabulary (it was AI tool names)
  * the lexicon of "already-famous" entities used by report.py
  * the content modes themselves

A project is one JSON file. Creators are mapped to the mode you study them
FOR -- you follow someone for their funny reels and someone else for their
screen recordings, and pooling those together would compare two different
crafts. The same creator may appear under more than one mode.

  bin/project.py new  <name> --niche "..." --mode informational=a,b --mode funny=c
  bin/project.py show <name>
  bin/project.py lexicon <name>     # derive the niche's famous-entity list
"""
import json, pathlib, argparse, sys, re, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"

# Words that survive a capitalisation filter but name nothing.
STOP = set("""a an the and or but if then than that this these those there here
when where while what which who whom whose why how all any both each few more
most other some such no nor not only own same so too very can will just don
should now i you he she it we they me him her us them my your his its our their
is are was were be been being have has had do does did doing would could should
may might must shall to of in on at by for with about against between into
through during before after above below from up down out off over under again
further once ok okay yes hey hi so's let lets im ive dont didnt cant wont
new free best top get make made made use used using like really actually
first second third next last one two three four five six seven eight nine ten
today yesterday tomorrow year month week day monday tuesday wednesday thursday
friday saturday sunday january february march april may june july august
september october november december comment link bio dm follow share save
video reel post story guide full thing things people everyone someone
""".split())

TEMPLATE = {
    "name": None,
    "niche": {"label": None, "vocabulary": [], "seed_prompt": None},
    "modes": {},
    "baseline_window_days": 90,
    # Project-wide floor. Usually leave this null -- a niche pivot belongs to
    # one creator, not to everyone you study.
    "since": None,
    # Per-creator overrides, e.g. {"somehandle": {"since": "2025-06-01"}}.
    # Use this when a creator changed niche and their old content would
    # poison the baseline.
    "creators": {},
}


def path_for(name):
    return PROJECTS / f"{name}.json"


def load(name):
    p = path_for(name)
    if not p.exists():
        sys.exit(f"no such project: {name}\n"
                 f"  create one:  bin/project.py new {name} --niche \"...\" "
                 f"--mode informational=handle1,handle2")
    return json.loads(p.read_text())


def save(cfg):
    PROJECTS.mkdir(parents=True, exist_ok=True)
    path_for(cfg["name"]).write_text(json.dumps(cfg, indent=2, ensure_ascii=False))


def creators(cfg):
    """Every handle in the project, de-duplicated, order preserved."""
    seen, out = set(), []
    for spec in cfg["modes"].values():
        for h in spec.get("creators", []):
            if h not in seen:
                seen.add(h)
                out.append(h)
    return out


def modes_for(cfg, handle):
    return [m for m, spec in cfg["modes"].items()
            if handle in spec.get("creators", [])]


def since_for(cfg, handle):
    """A creator who changed niche needs their own cutoff. Applying one
    creator's pivot date to the whole project silently throws away other
    people's data -- which it did, dropping 121 of one creator's 395 reels."""
    return (cfg.get("creators", {}).get(handle, {}).get("since")
            or cfg.get("since"))


def seed_prompt(cfg):
    """whisper.cpp emits all-lowercase, unpunctuated text without an initial
    prompt. The seed fixes casing AND teaches it the niche's proper nouns, so
    it stops mangling names it has never heard. One flag, two wins."""
    if cfg["niche"].get("seed_prompt"):
        return cfg["niche"]["seed_prompt"]
    vocab = cfg["niche"].get("vocabulary") or []
    label = cfg["niche"].get("label") or "this topic"
    if not vocab:
        return (f"Here's what I want to show you about {label}. "
                f"We'll go through it step by step, and I'll explain exactly "
                f"how it works. Comment below and I'll send you the full "
                f"breakdown.")
    head = ", ".join(vocab[:14])
    tail = ", ".join(vocab[14:26])
    s = (f"Here's what I want to show you about {label}. I use {head} all the "
         f"time. ")
    if tail:
        s += f"We'll also cover {tail}. "
    s += ("I'll explain exactly how it works, step by step. Comment below and "
          "I'll send you the full breakdown.")
    return s


def derive_lexicon(cfg, top=40, min_posts=3, max_df=0.35):
    """Build the niche's 'already-famous entity' list from the data itself.

    A hardcoded list only ever works for one niche, so this counts proper
    nouns across every caption of every creator in the project. A name that
    recurs across a niche's biggest accounts is, operationally, a famous name
    in that niche -- which is exactly what the report needs to test.

    Two traps, both hit on the first attempt:

    1. Sentence-initial capitals are not proper nouns. Naive capitalisation
       matching returned "Think", "Want", "Boom" and "Instead". So a token
       only counts when it is capitalised somewhere OTHER than the start of a
       sentence, and it is dropped if it also appears lowercase elsewhere.
       Internal capitals or digits (ChatGPT, n8n, DeepSeek, Veo3) skip the
       test outright -- no common word looks like that.

    2. A name in almost every post cannot discriminate. "AI" appeared in 74%
       of captions in the first niche tested -- it is this niche's boilerplate,
       not a household name you borrow reach from. Anything above max_df is
       dropped for the same reason a search engine drops "the".

    3. Keep the list SHORT. It tests "is the subject a household name in this
       niche", and a long list makes every reel look famous: at 125 entities
       the feature saturated at 100% in both cohorts and measured nothing.

    Requires scraped data. Falls back to the declared vocabulary alone.
    """
    word = re.compile(r"[A-Za-z][A-Za-z0-9.\-]{1,20}")
    boundary = re.compile(r"[.!?:;\n\r\u2022\-]\s*$")
    odd = re.compile(r"^[a-z]+[A-Z0-9]|^[A-Z][a-z]*[A-Z]|\d")

    posts = collections.Counter()       # distinct posts a name appears in
    cap_mid = collections.Counter()     # capitalised, not sentence-initial
    lower = collections.Counter()       # seen lowercase at all
    shape = {}                          # canonical surface form
    per_creator = collections.defaultdict(set)

    for h in creators(cfg):
        idx = ROOT / "data" / h / "index.json"
        if not idx.exists():
            continue
        for post in json.loads(idx.read_text()).get("posts", []):
            cap = post.get("caption") or ""
            seen = set()
            for m in word.finditer(cap):
                w = m.group(0).strip(".-")
                if len(w) < 2:
                    continue
                k = w.lower()
                if k in STOP:
                    continue
                before = cap[max(0, m.start() - 2):m.start()]
                initial = m.start() == 0 or bool(boundary.search(before))
                if w[0].islower() and not odd.match(w):
                    lower[k] += 1
                    continue
                if odd.match(w) or not initial:
                    cap_mid[k] += 1
                    shape.setdefault(k, w)
                    seen.add(k)
            for k in seen:
                posts[k] += 1
                per_creator[k].add(h)

    total = sum(1 for h in creators(cfg)
                for _ in json.loads((ROOT / "data" / h / "index.json").read_text())
                .get("posts", [])
                if (ROOT / "data" / h / "index.json").exists()) or 1
    scored = []
    for k, n in posts.items():
        if n < min_posts or cap_mid[k] < 2:
            continue
        if n / total > max_df:           # niche boilerplate, not a name
            continue
        if lower[k] > cap_mid[k]:        # mostly a common word
            continue
        # breadth first: a name used by several creators is more famous than
        # one used often by a single account.
        scored.append((len(per_creator[k]), n, shape.get(k, k)))
    scored.sort(reverse=True)
    ranked = [w for _, _, w in scored][:top]

    declared = cfg["niche"].get("vocabulary") or []
    merged, seen = [], set()
    for w in declared + ranked:
        if w.lower() not in seen:
            seen.add(w.lower())
            merged.append(w)
    return merged, {w: posts.get(w.lower(), 0) for w in merged}


def cmd_new(a):
    cfg = json.loads(json.dumps(TEMPLATE))
    cfg["name"] = a.name
    cfg["niche"]["label"] = a.niche
    cfg["niche"]["vocabulary"] = [v.strip() for v in (a.vocabulary or "").split(",") if v.strip()]
    for spec in a.mode or []:
        if "=" not in spec:
            sys.exit(f"--mode needs mode=handle1,handle2 (got: {spec})")
        mode, handles = spec.split("=", 1)
        cfg["modes"][mode.strip()] = {
            "creators": [h.strip().lstrip("@") for h in handles.split(",") if h.strip()]
        }
    if a.since:
        cfg["since"] = a.since
    save(cfg)
    print(f"wrote {path_for(a.name)}")
    cmd_show(a)


def cmd_show(a):
    cfg = load(a.name)
    print(f"\nproject: {cfg['name']}   niche: {cfg['niche']['label']}")
    if cfg["niche"].get("vocabulary"):
        print(f"  vocabulary: {', '.join(cfg['niche']['vocabulary'][:12])}"
              f"{' …' if len(cfg['niche']['vocabulary']) > 12 else ''}")
    print()
    for mode, spec in cfg["modes"].items():
        hs = spec.get("creators", [])
        marks = []
        for h in hs:
            idx = ROOT / "data" / h / "index.json"
            if idx.exists():
                d = json.loads(idx.read_text())
                n = sum(1 for p in d["posts"] if p.get("is_reel"))
                t = len(list((ROOT / "data" / h / "transcripts").glob("*.txt"))) \
                    if (ROOT / "data" / h / "transcripts").exists() else 0
                marks.append(f"{h} ({n} reels, {t} transcribed)")
            else:
                marks.append(f"{h} (not scraped)")
        print(f"  {mode}:")
        for m in marks:
            print(f"    - {m}")
    print()


def cmd_lexicon(a):
    cfg = load(a.name)
    lex, counts = derive_lexicon(cfg, top=getattr(a, "top", 40))
    if not counts:
        print("no scraped data yet — lexicon is just the declared vocabulary",
              file=sys.stderr)
    cfg["niche"]["lexicon"] = lex
    save(cfg)
    print(f"derived {len(lex)} entities into {path_for(cfg['name'])}\n")
    for w in lex[:40]:
        print(f"  {w:<24} {counts.get(w, 0)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new"); n.add_argument("name")
    n.add_argument("--niche", required=True)
    n.add_argument("--vocabulary", help="comma-separated proper nouns of the niche")
    n.add_argument("--mode", action="append", help="mode=handle1,handle2 (repeatable)")
    n.add_argument("--since", help="ignore reels before YYYY-MM-DD")
    n.set_defaults(fn=cmd_new)
    s = sub.add_parser("show"); s.add_argument("name"); s.set_defaults(fn=cmd_show)
    l = sub.add_parser("lexicon"); l.add_argument("name")
    l.add_argument("--top", type=int, default=40,
                   help="how many entities count as famous (default 40; "
                        "a long list saturates and measures nothing)")
    l.set_defaults(fn=cmd_lexicon)
    a = ap.parse_args()
    a.fn(a)
