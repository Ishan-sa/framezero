#!/usr/bin/env python3
"""Download the study set's videos and extract 16kHz mono WAV for whisper.

Instagram's CDN URLs are signed and expire in hours, so this must run soon
after scrape. If a URL is dead we refresh it from the public media info
endpoint before giving up.

Writes data/<handle>/media/<code>.wav
"""
import json, subprocess, urllib.request, urllib.error, pathlib, argparse, sys, time

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
APP_ID = "936619743392459"
ROOT = pathlib.Path(__file__).resolve().parent.parent


def refresh_url(pk, handle):
    """Signed URL expired — ask Instagram for a fresh one."""
    req = urllib.request.Request(
        f"https://www.instagram.com/api/v1/media/{pk}/info/",
        headers={"User-Agent": UA, "X-IG-App-ID": APP_ID,
                 "Referer": f"https://www.instagram.com/{handle}/"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        return d["items"][0]["video_versions"][0]["url"]
    except Exception as e:
        print(f"    refresh failed: {e}", file=sys.stderr)
        return None


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 16):
            f.write(chunk)
    return dest.stat().st_size


def to_wav(mp4, wav):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4),
                    "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)],
                   check=True)


def main(handle, keep_mp4):
    d = ROOT / "data" / handle
    ranked = json.loads((d / "ranked.json").read_text())
    media = d / "media"
    media.mkdir(parents=True, exist_ok=True)
    ok = fail = skip = 0
    for r in ranked["study_set"]:
        code, wav = r["code"], media / f"{r['code']}.wav"
        if wav.exists() and wav.stat().st_size > 1000:
            skip += 1
            continue
        mp4 = media / f"{code}.mp4"
        url = r.get("video_url")
        for attempt in (1, 2):
            try:
                if not url:
                    raise ValueError("no url")
                size = download(url, mp4)
                to_wav(mp4, wav)
                if not keep_mp4:
                    mp4.unlink(missing_ok=True)
                print(f"  ok  {code} [{r['cohort']}] {r['outlier']}x "
                      f"{size/1e6:.1f}MB", file=sys.stderr, flush=True)
                ok += 1
                break
            except Exception as e:
                if attempt == 1:
                    print(f"  .. {code} stale ({type(e).__name__}) — refreshing",
                          file=sys.stderr, flush=True)
                    url = refresh_url(r["pk"], handle)
                    time.sleep(3)
                else:
                    print(f"  FAIL {code}: {e}", file=sys.stderr, flush=True)
                    fail += 1
        time.sleep(1.5)
    print(f"fetched ok={ok} skipped={skip} failed={fail} -> {media}", file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("handle")
    ap.add_argument("--keep-mp4", action="store_true")
    a = ap.parse_args()
    main(a.handle.lstrip("@"), a.keep_mp4)
