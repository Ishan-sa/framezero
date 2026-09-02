#!/usr/bin/env python3
"""Which subjects and which openings hold up across MORE THAN ONE creator.

A topic that beats one creator's baseline is that creator's territory. It might
be their audience, their face, their timing, or luck that survived a
correction. The only way to find out whether it is a property of the *format*
is to ask whether it also holds for somebody else making the same kind of
content -- which is the same argument `aggregate.py` makes about structure,
applied to subject matter and to hooks.

The verdicts match the rest of the tool:

  REPLICATED   same direction for 2+ creators, none pointing the other way
  CONTESTED    creators disagree. Noise until resolved, never a rule.
  SINGLE       one creator's finding. A bet you can take knowingly.
  DEAD         tested for 2+ creators and flat for all of them.

Hooks replicate more meaningfully than topics do, and it is worth knowing why:
every creator is scored against the *same* archetype list, so the names line up
by construction. Topic names only line up when two creators happen to use the
same word for the same subject -- which is why the declared lens, where you
supply the names yourself, is the one to trust across creators.

Writes data/_projects/<project>/signals.md (or signals-<mode>.md)
"""
import json, pathlib, sys, argparse

BIN = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(BIN))
import project as P

ROOT = BIN.parent
UP, DOWN = "overperforms", "underperforms"


def load(handle, name):
    f = ROOT / "data" / handle / name
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except json.JSONDecodeError:
        return None


def collect_topics(handles, lens_order=("declared", "terms", "hashtags")):
    """topic -> {handle: (lift, verdict, reels, lens)} for every creator that
    tested it. A creator who never covered the subject is simply absent, which
    is not the same as a creator who covered it and saw nothing."""
    seen, missing = {}, []
    for h in handles:
        d = load(h, "topics.json")
        if not d:
            missing.append(h)
            continue
        for lens in lens_order:
            for name, v in (d.get("lenses") or {}).get(lens, {}).items():
                # First lens wins, so a name you declared beats the same name
                # mined out of captions.
                seen.setdefault(name, {}).setdefault(
                    h, (v["lift"], v["verdict"], v["reels"], lens))
    return seen, missing


def collect_hooks(handles):
    """archetype -> {handle: ...} from BOTH lenses, kept apart.

    The spoken lens is winners-against-controls on ~30 reels; the written lens
    is the whole catalogue. Averaging them would be dishonest, so they are
    reported side by side."""
    written, spoken, missing = {}, {}, []
    for h in handles:
        d = load(h, "hooks.json")
        if not d:
            missing.append(h)
            continue
        for name, v in ((d.get("written") or {}).get("archetypes") or {}).items():
            written.setdefault(name, {})[h] = (
                v["lift"], v["verdict"], v["reels"], "caption")
        sp = d.get("spoken") or {}
        for name, v in (sp.get("archetypes") or {}).items():
            # Winners-minus-controls as a share, so it reads on the same axis
            # as a lift: above 0 means the winners lean on it more.
            edge = (v["winners"] / max(v["winners_of"], 1)
                    - v["controls"] / max(v["controls_of"], 1))
            spoken.setdefault(name, {})[h] = (
                round(edge, 2),
                UP if edge >= 0.20 else DOWN if edge <= -0.20 else "at baseline",
                v["reels"], "spoken")
    return written, spoken, missing


def verdict(per_creator):
    up = [h for h, v in per_creator.items() if v[1] == UP]
    down = [h for h, v in per_creator.items() if v[1] == DOWN]
    n = len(per_creator)
    if up and down:
        return "CONTESTED", up, down
    if len(up) >= 2:
        return "REPLICATED", up, down
    if len(down) >= 2:
        return "REPLICATED", up, down
    if len(up) + len(down) == 1:
        return ("SINGLE", up, down) if n >= 2 else ("UNTESTED", up, down)
    return ("DEAD", up, down) if n >= 2 else ("UNTESTED", up, down)


def rank_all(table):
    out = []
    for name, per in table.items():
        v, up, down = verdict(per)
        out.append({"name": name, "verdict": v, "up": up, "down": down,
                    "creators": len(per), "per": per,
                    "direction": "up" if len(up) > len(down) else
                                 "down" if down else "flat"})
    order = {"REPLICATED": 0, "CONTESTED": 1, "SINGLE": 2, "DEAD": 3,
             "UNTESTED": 4}
    out.sort(key=lambda r: (order[r["verdict"]], -r["creators"], r["name"]))
    return out


def section(rows, handles, title, note, unit, keep, limit=25):
    picked = [r for r in rows if r["verdict"] in keep]
    L = [f"## {title}", "", note, ""]
    if not picked:
        L += ["Nothing in this class.", ""]
        return L
    L += ["| | verdict | creators | " + " | ".join(f"@{h}" for h in handles) + " |",
          "|---|---|---:|" + "---:|" * len(handles)]
    for r in picked[:limit]:
        cells = []
        for h in handles:
            v = r["per"].get(h)
            if not v:
                cells.append("—")
            else:
                mark = "**" if v[1] in (UP, DOWN) else ""
                cells.append(f"{mark}{v[0]:+.2f}{mark}" if unit == "edge"
                             else f"{mark}{v[0]:.2f}×{mark}")
        L.append(f"| {r['name']} | {r['verdict']} | {r['creators']} | "
                 + " | ".join(cells) + " |")
    L += ["", "<sub>Bold means that creator's own report called it a finding. "
              "An em dash means the creator was never tested on it — for a "
              "topic that usually means they do not cover it, which is not the "
              "same as covering it and seeing nothing.</sub>", ""]
    return L


def build(project, mode, only=None):
    # --handles exists so you can hold two creators against each other before
    # committing either of them to a project. Comparing is how you decide
    # whether a creator is worth keeping, so it should not require a config
    # edit first.
    if only:
        handles = [h.strip().lstrip("@") for h in only.split(",") if h.strip()]
    else:
        cfg = P.load(project)
        handles = P.creators(cfg)
        if mode:
            handles = [h for h in handles if mode in P.modes_for(cfg, h)]
    if not handles:
        sys.exit(f"no creators in {project}" + (f" for mode {mode}" if mode else ""))

    topics, t_missing = collect_topics(handles)
    written, spoken, h_missing = collect_hooks(handles)
    ready = [h for h in handles if h not in set(t_missing) | set(h_missing)]

    L = [f"# Signals that replicate — {project}"
         + (f" / {mode}" if mode else ""), ""]
    if len(ready) < 2:
        L += ["> [!WARNING]",
              f"> **Only {len(ready)} creator has topics and hooks on disk.** "
              "Replication is the entire point of this file and it needs at "
              "least two. Everything below is a single creator's findings with "
              "a more confident filename.",
              ">",
              "> Run `./framezero profile <handle>` for another creator in "
              "this niche first.", ""]
    L += [f"Creators compared: " + ", ".join(f"@{h}" for h in ready) + ".", ""]
    if t_missing or h_missing:
        gaps = sorted(set(t_missing) | set(h_missing))
        L += [f"<sub>No topics/hooks on disk for: "
              + ", ".join(f"@{g}" for g in gaps)
              + " — run `./framezero profile <handle>` for each.</sub>", ""]

    L += ["A finding here has cleared two bars: its own creator's "
          "false-discovery correction, and then agreement with a second "
          "creator making the same kind of content. That is the strongest "
          "claim this tool makes about anything.", ""]

    hooks_rows = rank_all(spoken)
    L += section(
        hooks_rows, ready, "Hook shapes — spoken",
        "How much more often the WINNERS open this way than the controls, as "
        "a share. `+0.25` means a quarter more of the winners used it. Every "
        "creator is scored against the same archetype list, so these names "
        "line up by construction — this is the most comparable table in the "
        "tool.", "edge", {"REPLICATED", "CONTESTED", "SINGLE", "DEAD"})

    L += section(
        rank_all(written), ready, "Hook shapes — caption openers",
        "The same archetypes measured on every caption in every catalogue, "
        "hundreds per creator, in lift against each creator's own baseline. "
        "Bigger samples, weaker proxy: this is what the creator wrote, not "
        "what the viewer heard.", "lift",
        {"REPLICATED", "CONTESTED", "SINGLE", "DEAD"})

    trows = rank_all(topics)
    L += section(
        trows, ready, "Subjects that replicate",
        "A subject two creators both beat their own baseline on is a property "
        "of the niche, not of one account. Read the caveat below before "
        "trusting a name here.", "lift", {"REPLICATED", "CONTESTED"})
    L += section(
        trows, ready, "Subjects that belong to one creator",
        "Strong for one, and the others either flat on it or not covering it "
        "at all. Take these knowingly — they are bets, not rules.", "lift",
        {"SINGLE"}, limit=15)

    L += ["## How to read this", "", 
          "1. **REPLICATED beats everything.** It is the only class here that "
          "should become a rule in a skill.",
          "2. **CONTESTED is not a weak REPLICATED.** Two creators pointing "
          "opposite ways means the effect belongs to something you have not "
          "measured. Leave it out.",
          "3. **Hook shapes travel; subjects travel less.** An archetype is a "
          "mechanic and will work in a niche it was never measured in. A "
          "subject is territory — it replicates within a niche and not "
          "outside it.",
          "4. **Nothing here is wording.** Take the shape and the subject; "
          "write the sentence yourself, then check it against a single "
          "creator's voice — never a blend of two.", "",
          "## What this cannot tell you", "",
          "- Topic names only line up when two creators use the same word for "
          "the same subject. One saying `pricing` and another saying `cost` "
          "reads here as two unrelated topics. Use `--define` with a shared "
          "spec across your creators and this stops being a problem.",
          "- Two creators is the minimum, not a comfortable sample. Three "
          "changes how much a REPLICATED verdict is worth.",
          "- The spoken lens is ~30 reels per creator, chosen as the two "
          "tails. Its edges are directional, not precise.", ""]
    return "\n".join(L), ready


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--mode", help="only creators studied for this mode")
    ap.add_argument("--handles", help="compare these handles instead, comma "
                                      "separated — no project edit needed")
    a = ap.parse_args()

    md, ready = build(a.project, a.mode, a.handles)
    out = ROOT / "data" / "_projects" / a.project
    out.mkdir(parents=True, exist_ok=True)
    name = ("signals-adhoc.md" if a.handles else
            f"signals-{a.mode}.md" if a.mode else "signals.md")
    (out / name).write_text(md)
    print(f"  signals: {len(ready)} creators -> data/_projects/{a.project}/{name}",
          file=sys.stderr)
