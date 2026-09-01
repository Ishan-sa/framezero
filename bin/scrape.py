#!/usr/bin/env python3
"""Pull a public Instagram profile's post index (incl. reel play counts).

Logged-out public web API. No login, no cookies, no paid actor.
Instagram throttles this endpoint hard per-IP, so we go slow, back off on
401/429, save after every page, and resume from whatever we already have.

Writes data/<handle>/index.json
"""
import json, sys, time, random, urllib.request, urllib.error, pathlib, argparse

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
APP_ID = "936619743392459"
ROOT = pathlib.Path(__file__).resolve().parent.parent


def get(url, handle):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "X-IG-App-ID": APP_ID,
        "Referer": f"https://www.instagram.com/{handle}/",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def get_retry(url, handle, tries=12, base=45, cap=1800):
    """Back off through a throttle. IG's 401 here means 'slow down', not 'no'."""
    for n in range(tries):
        try:
            return get(url, handle)
        except urllib.error.HTTPError as e:
            if e.code not in (401, 429, 403, 500, 502, 503):
                raise
            wait = min(base * (2 ** n), cap) + random.uniform(0, 20)
            print(f"    HTTP {e.code} — backing off {wait:.0f}s "
                  f"(attempt {n+1}/{tries})", file=sys.stderr, flush=True)
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError) as e:
            wait = min(base * (2 ** n), cap)
            print(f"    {e} — retry in {wait:.0f}s", file=sys.stderr, flush=True)
            time.sleep(wait)
    return None


def profile_of(handle):
    d = get_retry(f"https://www.instagram.com/api/v1/users/web_profile_info/"
                  f"?username={handle}", handle)
    u = d["data"]["user"]
    return u["id"], {
        "handle": handle,
        "full_name": u.get("full_name"),
        "biography": u.get("biography"),
        "followers": u["edge_followed_by"]["count"],
        "following": u["edge_follow"]["count"],
        "post_count": u["edge_owner_to_timeline_media"]["count"],
    }


def normalize(item):
    vv = item.get("video_versions") or []
    cap = item.get("caption") or {}
    return {
        "code": item.get("code"),
        "pk": str(item.get("pk") or str(item.get("id", "")).split("_")[0]),
        "media_type": item.get("media_type"),
        "product_type": item.get("product_type"),
        "is_reel": item.get("product_type") == "clips",
        "taken_at": item.get("taken_at"),
        "play_count": item.get("play_count") or item.get("ig_play_count"),
        "like_count": item.get("like_count"),
        "comment_count": item.get("comment_count"),
        "duration": item.get("video_duration"),
        "caption": cap.get("text", "") or "",
        "video_url": vv[0]["url"] if vv else None,
        "url": f"https://www.instagram.com/p/{item.get('code')}/",
    }


def save(path, profile, posts, cursor, done):
    seen, uniq = set(), []
    for p in posts:                       # de-dupe, keep first occurrence
        if p["code"] and p["code"] not in seen:
            seen.add(p["code"])
            uniq.append(p)
    uniq.sort(key=lambda p: p.get("taken_at") or 0, reverse=True)
    path.write_text(json.dumps({
        "profile": profile, "scraped_at": int(time.time()),
        "cursor": cursor, "complete": done, "posts": uniq,
    }, indent=2, ensure_ascii=False))
    return uniq


TRIES = 12


def scrape(handle, max_pages=60, delay=25.0):
    out = ROOT / "data" / handle
    out.mkdir(parents=True, exist_ok=True)
    path = out / "index.json"

    posts, cursor, profile = [], None, None
    if path.exists():                     # resume
        prev = json.loads(path.read_text())
        posts, cursor, profile = prev["posts"], prev.get("cursor"), prev.get("profile")
        print(f"  resuming: {len(posts)} posts already on disk, cursor={bool(cursor)}",
              file=sys.stderr, flush=True)

    uid, prof = profile_of(handle)
    profile = prof
    print(f"  {handle}: id={uid} followers={prof['followers']:,} "
          f"posts={prof['post_count']}", file=sys.stderr, flush=True)

    page, done = 0, False
    while page < max_pages:
        url = f"https://www.instagram.com/api/v1/feed/user/{uid}/?count=33"
        if cursor:
            url += f"&max_id={cursor}"
        d = get_retry(url, handle, tries=TRIES)
        if d is None:
            print("  exhausted retries — saving what we have", file=sys.stderr, flush=True)
            break
        batch = d.get("items") or []
        posts += [normalize(i) for i in batch]
        page += 1
        cursor = d.get("next_max_id")
        uniq = save(path, profile, posts, cursor, False)
        reels = sum(1 for p in uniq if p["is_reel"])
        print(f"  page {page}: +{len(batch)} -> {len(uniq)} posts / {reels} reels",
              file=sys.stderr, flush=True)
        if not d.get("more_available") or not cursor:
            done = True
            break
        time.sleep(delay + random.uniform(0, delay * 0.4))

    uniq = save(path, profile, posts, cursor, done)
    reels = sum(1 for p in uniq if p["is_reel"])
    print(f"  DONE complete={done}: {len(uniq)} posts, {reels} reels -> {path}",
          file=sys.stderr, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("handle")
    ap.add_argument("--max-pages", type=int, default=60)
    ap.add_argument("--delay", type=float, default=25.0)
    ap.add_argument("--tries", type=int, default=12)
    a = ap.parse_args()
    globals()["TRIES"] = a.tries
    scrape(a.handle.lstrip("@"), a.max_pages, a.delay)
