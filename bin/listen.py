#!/usr/bin/env python3
"""Transcribe the study set locally with whisper.cpp. Free, no API.

Two things matter here:

1. whisper.cpp emits ALL-LOWERCASE, unpunctuated text unless you give it a
   seed prompt. The seed is a normal capitalised, punctuated sentence, and
   whisper continues in that register.
2. We load the seed with the creator's actual vocabulary, so it stops
   writing "N8 N", "make dot com" and "cloud" for Claude. Same flag, two
   wins.

Writes data/<handle>/transcripts/<code>.json and .txt (timestamped)
"""
import json, subprocess, pathlib, argparse, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODEL = pathlib.Path.home() / ".whisper" / "models" / "ggml-large-v3-turbo.bin"

SEED = (
    "Here's how I built this with AI. I use ChatGPT, Claude, Gemini, "
    "Perplexity, and NotebookLM every day. For automation I use n8n, "
    "Make.com, Zapier, Notion, Airtable, Replit, Lovable, Cursor, and Canva. "
    "We'll cover prompts, APIs, agents, workflows, LLMs, and no-code tools, "
    "step by step. Comment below and I'll send you the full breakdown."
)


def stamp(ms):
    s = ms // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def transcribe(wav, outbase, threads):
    subprocess.run([
        "whisper-cli", "-m", str(MODEL), "-f", str(wav),
        "-l", "en", "-t", str(threads), "-oj", "-of", str(outbase),
        "--prompt", SEED, "-np",
    ], check=True, capture_output=True)


def to_text(js, meta):
    segs = js.get("transcription", [])
    head = (f"# {meta['code']} | {meta['cohort']} | {meta['outlier']}x baseline | "
            f"{meta['play_count']:,} plays | {meta.get('duration') or 0:.0f}s | "
            f"{meta.get('like_count',0):,} likes / {meta.get('comment_count',0):,} comments")
    lines = [head, ""]
    for s in segs:
        off = s.get("offsets", {})
        lines.append(f"[{stamp(off.get('from', 0))}] {s.get('text','').strip()}")
    lines += ["", "--- CAPTION ---", meta.get("caption", "")]
    return "\n".join(lines)


def main(handle, threads):
    d = ROOT / "data" / handle
    ranked = json.loads((d / "ranked.json").read_text())
    meta = {r["code"]: r for r in ranked["study_set"]}
    tdir = d / "transcripts"
    tdir.mkdir(parents=True, exist_ok=True)
    ok = skip = fail = 0
    for code, m in meta.items():
        wav = d / "media" / f"{code}.wav"
        txt = tdir / f"{code}.txt"
        if not wav.exists():
            continue
        if txt.exists() and txt.stat().st_size > 100:
            skip += 1
            continue
        t0 = time.time()
        try:
            transcribe(wav, tdir / code, threads)
            js = json.loads((tdir / f"{code}.json").read_text())
            txt.write_text(to_text(js, m))
            words = sum(len(s.get("text", "").split()) for s in js.get("transcription", []))
            print(f"  ok  {code} [{m['cohort']}] {words:>4} words "
                  f"in {time.time()-t0:.0f}s", file=sys.stderr, flush=True)
            ok += 1
        except subprocess.CalledProcessError as e:
            print(f"  FAIL {code}: {e.stderr.decode()[:200]}", file=sys.stderr, flush=True)
            fail += 1
    print(f"transcribed ok={ok} skipped={skip} failed={fail} -> {tdir}", file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("handle")
    ap.add_argument("--threads", type=int, default=8)
    a = ap.parse_args()
    main(a.handle.lstrip("@"), a.threads)
