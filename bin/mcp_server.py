#!/usr/bin/env python3
"""framezero as MCP tools, so an assistant can drive it without shell archaeology.

Nobody is going to use this tool raw. They are going to point Claude, Cursor or
Codex at it and say "study this creator". Reading AGENTS.md and shelling out
works, but it makes the assistant guess: which stage runs first, which file
holds the findings, whether a draft has been checked. Typed tools remove the
guessing.

Speaks MCP over stdio -- JSON-RPC 2.0, one message per line. No dependency; the
protocol is small enough that adding one would cost more than it saved, and the
rest of this repo is standard library only.

Register it (Claude Code):

    claude mcp add framezero -- python3 /abs/path/to/bin/mcp_server.py

Or in any client's JSON config:

    {"mcpServers": {"framezero": {"command": "python3",
                                  "args": ["/abs/path/to/bin/mcp_server.py"]}}}
"""
import json, sys, subprocess, pathlib, os

ROOT = pathlib.Path(__file__).resolve().parent.parent
BIN = ROOT / "bin"
PROTOCOL = "2025-06-18"

# Reads are cheap and safe. Anything that hits the network or costs an hour of
# transcription is marked, so a client that surfaces annotations can prompt.
def tool(name, desc, props, required=(), read_only=True, slow=False):
    return {
        "name": name,
        "description": desc,
        "inputSchema": {"type": "object", "properties": props,
                        "required": list(required)},
        "annotations": {"readOnlyHint": read_only,
                        "openWorldHint": not read_only,
                        "title": name.replace("_", " ")},
        "_slow": slow,
    }


HANDLE = {"type": "string", "description": "Instagram handle, without the @"}
PROJECT = {"type": "string", "description": "project name"}

TOOLS = [
    tool("list_projects",
         "List every framezero project on disk and the creators in each, with "
         "how many reels are scraped and transcribed. Start here when you do "
         "not know what already exists.", {}),
    tool("profile_creator",
         "Full dossier for one public Instagram creator: identity, bio, "
         "follower count, median/best/worst plays, engagement, growth "
         "trajectory by quarter, posting cadence, reel durations, hashtags, "
         "disclosed brand partnerships, recurring sponsor tags, caption CTAs, "
         "and Instagram's own related accounts. Also answers whether the "
         "account has a wide enough performance spread to be worth studying "
         "at all. Scrapes the index if it is not already on disk (about a "
         "minute); does NOT transcribe anything.",
         {"handle": HANDLE,
          "refresh": {"type": "boolean",
                      "description": "re-pull the index even if one exists"}},
         ["handle"], read_only=False),
    tool("findings",
         "Which structural findings REPLICATED across the creators studied "
         "for a mode, and which are one creator's bet. Read this BEFORE any "
         "transcript: only REPLICATED findings belong in a skill as rules.",
         {"project": PROJECT,
          "mode": {"type": "string", "description": "e.g. informational"}},
         ["project", "mode"]),
    tool("creator_report",
         "One creator's countable winner-vs-control deltas — the structural "
         "features that separate their best reels from their worst.",
         {"handle": HANDLE}, ["handle"]),
    tool("voice_profile",
         "How a creator SOUNDS: 16 measured dials with target bands, plus the "
         "phrases they reach for that other creators in the project do not. "
         "Use this to write in their voice.",
         {"handle": HANDLE}, ["handle"]),
    tool("check_script",
         "Score a draft script against a creator's voice. Returns runtime at "
         "the writer's own speaking rate, and which of the 16 dials are out of "
         "band and in which direction. ALWAYS run this before showing a draft "
         "to the user. Fix a failing dial by rewriting a beat, not by tuning "
         "words; if runtime is over, cut a whole beat.",
         {"script": {"type": "string", "description": "the draft script text"},
          "like": {"type": "string",
                   "description": "handle, or comma-separated handles to pool"},
          "wpm": {"type": "number",
                  "description": "the WRITER's speaking rate, not the "
                                 "creator's. Default 210 is the studied "
                                 "creators' median and is faster than most "
                                 "people talk."}},
         ["script", "like"]),
    tool("transcripts",
         "The transcripts themselves, for one creator and one cohort. Read "
         "LAST — after findings and report — because reading transcripts first "
         "makes you find patterns whether or not they are there.",
         {"handle": HANDLE,
          "cohort": {"type": "string", "enum": ["winner", "control"]},
          "limit": {"type": "integer", "description": "default 5"}},
         ["handle"]),
    tool("run_pipeline",
         "SLOW (20-60 minutes). Scrape, rank, download, transcribe and analyse "
         "every creator in a project. Confirm with the user before calling. "
         "Safe to repeat — every stage skips work already on disk.",
         {"project": PROJECT,
          "mode": {"type": "string"}, "only": HANDLE},
         ["project"], read_only=False, slow=True),
]


def read(path, missing):
    f = ROOT / path
    return f.read_text() if f.exists() else missing


def run(script, *args, timeout=None):
    r = subprocess.run([sys.executable, str(BIN / script), *map(str, args)],
                       capture_output=True, text=True, timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


def call(name, a):
    if name == "list_projects":
        pj = sorted(p.stem for p in (ROOT / "projects").glob("*.json"))
        if not pj:
            return ("No projects yet. Create one with:\n"
                    "  ./framezero new <name> --niche \"...\" "
                    "--mode informational=handle_a,handle_b")
        return "\n\n".join(run("project.py", "show", n) for n in pj)

    if name == "profile_creator":
        h = a["handle"].lstrip("@")
        idx = ROOT / "data" / h / "index.json"
        if a.get("refresh") and idx.exists():
            idx.unlink()
        if not idx.exists():
            out = run("scrape.py", h, timeout=1800)
            if not idx.exists():
                return f"scrape failed for @{h}\n{out[-1500:]}"
        run("profile.py", h)
        return read(f"data/{h}/profile.md", f"no profile for @{h}")

    if name == "findings":
        p, m = a["project"], a["mode"]
        return read(f"data/_projects/{p}/{m}.md",
                    f"no findings for {p}/{m} — run: ./framezero run {p}")

    if name == "creator_report":
        h = a["handle"].lstrip("@")
        return read(f"data/{h}/report.md",
                    f"no report for @{h} — it needs transcripts first")

    if name == "voice_profile":
        h = a["handle"].lstrip("@")
        got = read(f"data/{h}/voice.md", "")
        if got:
            return got
        run("voice.py", "profile", h)
        return read(f"data/{h}/voice.md",
                    f"no voice profile for @{h} — needs at least 3 "
                    "transcribed winners")

    if name == "check_script":
        tmp = ROOT / "data" / ".mcp_draft.txt"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(a["script"])
        try:
            args = ["check", str(tmp), "--like", a["like"]]
            if a.get("wpm"):
                args += ["--wpm", a["wpm"]]
            # The scorecard names the file it read; the caller passed text,
            # so a temp path in the output would just be noise.
            return run("voice.py", *args).replace(str(tmp), "draft")
        finally:
            tmp.unlink(missing_ok=True)

    if name == "transcripts":
        h = a["handle"].lstrip("@")
        body = read(f"data/{h}/corpus.md", "")
        if not body:
            return f"no corpus for @{h}"
        cohort, limit = a.get("cohort"), a.get("limit") or 5
        blocks = body.split("\n## ")
        keep = [b for b in blocks[1:]
                if not cohort or cohort.lower() in b[:400].lower()][:limit]
        return blocks[0] + "".join("\n## " + b for b in keep)

    if name == "run_pipeline":
        args = ["run", a["project"]]
        for k in ("mode", "only"):
            if a.get(k):
                args += [f"--{k}", a[k]]
        r = subprocess.run([sys.executable, str(ROOT / "framezero"), *args],
                           capture_output=True, text=True, timeout=14400)
        return (r.stdout or "") + (r.stderr or "")

    return f"unknown tool: {name}"


def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        mid, method, params = req.get("id"), req.get("method"), req.get("params") or {}

        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "framezero", "version": "1.0.0"},
                "instructions":
                    "Study a creator, then write like them. Order matters: "
                    "profile_creator to decide if they are worth studying, "
                    "findings before any transcript, transcripts last. Only "
                    "REPLICATED findings become rules — a finding from one "
                    "creator is a bet. Never blend two creators' voices. "
                    "Always check_script a draft before showing it, at the "
                    "USER's speaking rate, not the default 210."}})
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "tools": [{k: v for k, v in t.items() if not k.startswith("_")}
                          for t in TOOLS]}})
        elif method == "tools/call":
            n = params.get("name")
            try:
                text = call(n, params.get("arguments") or {})
                err = False
            except Exception as e:
                text, err = f"{type(e).__name__}: {e}", True
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": text[:400000]}],
                "isError": err}})
        elif mid is not None:
            send({"jsonrpc": "2.0", "id": mid,
                  "error": {"code": -32601, "message": f"no method {method}"}})


if __name__ == "__main__":
    main()
