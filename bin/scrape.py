#!/usr/bin/env python3
"""Pull a public Instagram profile's full post index, logged out.

Instagram gated the old REST timeline (/api/v1/feed/user/) for logged-out
clients. It answers 401 with {"message":"Please wait a few minutes...",
"require_login":true,"igweb_rollout":true} on the very first request from a
cold IP. That string is a lie -- it is not a throttle, it is a retired
surface, and no amount of backing off will clear it. Do not go back there.

What does work anonymously, today, is two GraphQL calls joined on `code`:

  A. PolarisProfilePostsQuery  -> the timeline: captions, timestamps, likes,
     comments, and video_versions[] with direct CDN URLs. `view_count` is in
     the schema but always null when logged out, which is why we need B.
  B. clips user connection     -> real play_count per reel, but no video URLs
     and no taken_at. Hence the join.

The only header that matters is the CSRF pair: fetch the profile page first,
keep the csrftoken cookie, echo it back as X-CSRFToken. Cookie alone is
rejected with a 403 HTML body. Browser User-Agent, X-IG-App-ID, X-ASBD-ID,
Referer, Sec-Fetch-* are all cargo cult on this endpoint -- though X-IG-App-ID
IS required for the one REST call we still make, to resolve the user id.

doc_ids rotate every two to four weeks, so a hardcoded pair will eventually
rot. When one stops working we scrape the current value out of Instagram's own
JS bundle rather than failing.

Writes data/<handle>/index.json
"""
import json, sys, time, random, re, urllib.request, urllib.parse, urllib.error
import http.cookiejar, pathlib, argparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
APP_ID = "936619743392459"
GRAPHQL = "https://www.instagram.com/graphql/query"

# Known-good as of 2026-08-31. Auto-refreshed from the JS bundle if they rot.
DOC_POSTS = "28534843459473863"   # PolarisProfilePostsQuery
DOC_CLIPS = "27234427476213202"   # clips user connection v2

RELAY_PROVIDERS = {
    "__relay_internal__pv__PolarisMultiCaptionCarouselEnabledrelayprovider": False,
    "__relay_internal__pv__PolarisShortDramaEnabledrelayprovider": False,
    "__relay_internal__pv__PolarisReelsRecoDebugOverlayEnabledrelayprovider": False,
}


class IG:
    """A warmed guest session. Holds the cookie jar and the csrf token."""

    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = None

    def _open(self, req, timeout=30):
        return self.opener.open(req, timeout=timeout)

    def warm(self, handle):
        """GET the profile page so Instagram hands us a csrftoken."""
        req = urllib.request.Request(f"https://www.instagram.com/{handle}/",
                                     headers={"User-Agent": UA})
        with self._open(req) as r:
            html = r.read().decode("utf-8", "replace")
        for c in self.jar:
            if c.name == "csrftoken":
                self.csrf = c.value
        if not self.csrf:
            raise RuntimeError("no csrftoken from profile page — cannot proceed")
        return html

    def graphql(self, doc_id, variables):
        body = urllib.parse.urlencode({
            "doc_id": doc_id,
            "variables": json.dumps(variables),
            "server_timestamps": "true",
        }).encode()
        req = urllib.request.Request(GRAPHQL, data=body, headers={
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": self.csrf,
        })
        with self._open(req) as r:
            return json.load(r)

    def user_id(self, handle):
        """Identity, the rich way. Needs X-IG-App-ID.

        This is a REST surface, and REST surfaces here are being retired one by
        one -- /api/v1/feed/user/ went first and this one now answers 401 with
        the same "Please wait a few minutes" string, which is not a wait and
        never clears. So every caller must be able to survive losing it; see
        user_id_from_timeline below.
        """
        req = urllib.request.Request(
            "https://www.instagram.com/api/v1/users/web_profile_info/"
            f"?username={handle}",
            headers={"User-Agent": UA, "X-IG-App-ID": APP_ID})
        with self._open(req) as r:
            u = json.load(r)["data"]["user"]
        return u["id"], {
            "handle": handle,
            "full_name": u.get("full_name"),
            "biography": u.get("biography"),
            "followers": u["edge_followed_by"]["count"],
            "following": u["edge_follow"]["count"],
            "post_count": u["edge_owner_to_timeline_media"]["count"],
            # Everything below is free -- it rides on the same response. It is
            # what profile.py needs to describe the account rather than just
            # rank its reels.
            "category": u.get("category_name"),
            "business_category": u.get("business_category_name"),
            "is_verified": u.get("is_verified"),
            "is_professional": u.get("is_professional_account"),
            "is_business": u.get("is_business_account"),
            "external_url": u.get("external_url"),
            "bio_links": [{"title": b.get("title"), "url": b.get("url")}
                          for b in (u.get("bio_links") or []) if b.get("url")],
            # Instagram's own "similar accounts". The cheapest answer to
            # "who else should I be studying?" that exists.
            "related_profiles": [
                {"handle": e["node"].get("username"),
                 "name": e["node"].get("full_name"),
                 "verified": e["node"].get("is_verified")}
                for e in (u.get("edge_related_profiles") or {}).get("edges", [])
                if not e["node"].get("is_private")],
        }


def user_id_from_timeline(ig, handle, doc_id):
    """Identity, the durable way.

    Every timeline post carries its owner. That is less than the profile
    endpoint gives -- no follower count, no bio, no category, no related
    accounts -- but it is enough for the pipeline to run, and it comes from
    the GraphQL surface that still answers. One post is all we ask for.
    """
    v = {"data": {"count": 1}, "username": handle,
         "__relay_internal__pv__PolarisIsLoggedInrelayprovider": False,
         **RELAY_PROVIDERS}
    d = ig.graphql(doc_id, v)
    conn = ((d.get("data") or {})
            .get("xdt_api__v1__feed__user_timeline_graphql_connection")) or {}
    edges = conn.get("edges") or []
    if not edges:
        raise RuntimeError(f"no posts returned for @{handle}")
    u = (edges[0].get("node") or {}).get("user") or {}
    uid = u.get("pk") or u.get("id")
    if not uid:
        raise RuntimeError(f"timeline carried no owner for @{handle}")
    return str(uid), {
        "handle": handle,
        "full_name": u.get("full_name"),
        "biography": None,
        "followers": None,
        "following": None,
        "post_count": None,
        "category": None,
        "business_category": None,
        "is_verified": u.get("is_verified"),
        "is_professional": None,
        "is_business": None,
        "external_url": None,
        "bio_links": [],
        "related_profiles": [],
        # Says out loud which fields could not be filled, so the dossier can
        # report a gap instead of implying the creator has no bio and no
        # followers.
        "partial": True,
        "partial_reason": "Instagram's profile endpoint returned 401; "
                          "identity came from the post timeline instead.",
    }


def discover_doc_ids(ig, html):
    """doc_ids rotate. Pull the live ones out of Instagram's own JS modules."""
    found = {}
    urls = sorted(set(re.findall(
        r'https://static\.cdninstagram\.com/rsrc\.php/[^"\\]+\.js', html)))
    pat = re.compile(r'__d\("(Polaris\w+Query)_instagramRelayOperation".{0,160}?'
                     r'exports\s*=\s*"(\d+)"', re.S)
    for u in urls[:60]:
        try:
            req = urllib.request.Request(u.replace("\\/", "/"),
                                         headers={"User-Agent": UA})
            with ig._open(req, timeout=20) as r:
                js = r.read().decode("utf-8", "replace")
        except Exception:
            continue
        for name, doc in pat.findall(js):
            found.setdefault(name, doc)
        if "PolarisProfilePostsQuery" in found:
            break
    return found


DUR_RE = re.compile(r'mediaPresentationDuration="PT([\d.]+)S"')


def duration_of(n):
    """The GraphQL timeline drops video_duration, but the DASH manifest it
    ships carries mediaPresentationDuration. Same number, no extra request."""
    if n.get("video_duration"):
        return n["video_duration"]
    m = DUR_RE.search(n.get("video_dash_manifest") or "")
    return float(m.group(1)) if m else None


def handles_in(tags):
    """usertags / sponsor_tags / coauthors all wrap the account differently."""
    out = []
    for t in (tags or []):
        if isinstance(t, str):
            out.append(t.lstrip("@")); continue
        u = t.get("user") or t.get("sponsor") or t
        h = u.get("username") if isinstance(u, dict) else None
        if h:
            out.append(h)
    return out


def audio_of(n):
    """original_sounds vs a licensed track is a real format choice, and it is
    the difference between a reel that can be reused and one that cannot."""
    cm = n.get("clips_metadata") or {}
    mi = (cm.get("music_info") or {}).get("music_asset_info") or {}
    return {
        "type": cm.get("audio_type"),
        "track": mi.get("title"),
        "artist": mi.get("display_artist"),
    }


def norm_post(n):
    vv = n.get("video_versions") or []
    cap = n.get("caption") or {}
    ut = n.get("usertags") or {}
    loc = n.get("location") or {}
    return {
        "code": n.get("code"),
        "pk": str(n.get("pk") or ""),
        "media_type": n.get("media_type"),
        "product_type": n.get("product_type"),
        "is_reel": n.get("product_type") == "clips",
        "taken_at": n.get("taken_at"),
        "play_count": None,                 # filled from the clips pass
        "like_count": n.get("like_count"),
        "comment_count": n.get("comment_count"),
        "duration": duration_of(n),
        "caption": cap.get("text", "") or "",
        "video_url": vv[0]["url"] if vv else None,
        "url": f"https://www.instagram.com/p/{n.get('code')}/",
        # Kept for profile.py. All of it rides on the response we already made.
        "title": n.get("title"),
        "paid_partnership": bool(n.get("is_paid_partnership")),
        "sponsors": handles_in(n.get("sponsor_tags")),
        "coauthors": handles_in(n.get("coauthor_producers")
                                or n.get("invited_coauthor_producers")),
        "tagged": handles_in((ut.get("in") if isinstance(ut, dict) else ut) or []),
        "location": loc.get("name") if isinstance(loc, dict) else None,
        "audio": audio_of(n),
        "width": n.get("original_width"),
        "height": n.get("original_height"),
    }


def page_timeline(ig, handle, doc_id, delay, max_pages):
    posts, after, page = [], None, 0
    while page < max_pages:
        v = {"after": after, "before": None,
             "data": {"count": 33, "include_reel_media_seen_timestamp": True,
                      "include_relationship_info": True,
                      "latest_besties_reel_media": True,
                      "latest_reel_media": True},
             "first": 33, "last": None, "username": handle, **RELAY_PROVIDERS}
        d = ig.graphql(doc_id, v)
        conn = ((d.get("data") or {})
                .get("xdt_api__v1__feed__user_timeline_graphql_connection"))
        if not conn:
            raise RuntimeError(f"timeline: unexpected shape {str(d)[:200]}")
        posts += [norm_post(e["node"]) for e in conn.get("edges", [])]
        page += 1
        pi = conn.get("page_info") or {}
        print(f"  timeline p{page}: {len(posts)} posts", file=sys.stderr, flush=True)
        if not pi.get("has_next_page"):
            return posts, False
        after = pi.get("end_cursor")
        time.sleep(delay + random.uniform(0, 1))
    # Fell out of the loop with more to fetch: the cap truncated the catalogue.
    return posts, True


def page_clips(ig, uid, doc_id, delay, max_pages):
    """Real play counts. Reels only, keyed by code.

    page_size is a request, not a promise: the server returns 12 whatever you
    ask for. So a 1,300-reel catalogue is ~110 requests, and the page cap has
    to be generous or the ranking silently runs on a truncated set.
    """
    plays, max_id, page = {}, None, 0
    while page < max_pages:
        data = {"include_feed_video": True, "page_size": 12,
                "target_user_id": str(uid)}
        if max_id is not None:
            data["max_id"] = max_id
        d = ig.graphql(doc_id, {"data": data})
        conn = ((d.get("data") or {})
                .get("xdt_api__v1__clips__user__connection_v2"))
        if not conn:
            raise RuntimeError(f"clips: unexpected shape {str(d)[:200]}")
        for e in conn.get("edges", []):
            m = (e.get("node") or {}).get("media") or e.get("node") or {}
            if m.get("code"):
                plays[m["code"]] = m.get("play_count") or m.get("ig_play_count")
        page += 1
        pi = conn.get("page_info") or {}
        print(f"  clips p{page}: {len(plays)} play counts", file=sys.stderr, flush=True)
        if not pi.get("has_next_page"):
            return plays, False
        max_id = pi.get("end_cursor")
        time.sleep(delay + random.uniform(0, 1))
    return plays, True


def scrape(handle, delay=2.0, max_pages=400):
    out = ROOT / "data" / handle
    out.mkdir(parents=True, exist_ok=True)

    ig = IG()
    html = ig.warm(handle)

    doc_posts, doc_clips = DOC_POSTS, DOC_CLIPS
    try:
        uid, profile = ig.user_id(handle)
    except (urllib.error.HTTPError, KeyError, ValueError) as e:
        code = getattr(e, "code", None)
        print(f"  profile endpoint unavailable ({code or type(e).__name__}) — "
              "falling back to the timeline for identity",
              file=sys.stderr, flush=True)
        try:
            uid, profile = user_id_from_timeline(ig, handle, doc_posts)
        except (urllib.error.HTTPError, RuntimeError):
            found = discover_doc_ids(ig, html)
            doc_posts = found.get("PolarisProfilePostsQuery", doc_posts)
            uid, profile = user_id_from_timeline(ig, handle, doc_posts)

    followers = (f"{profile['followers']:,}" if profile.get("followers")
                 else "unknown")
    print(f"  {handle}: id={uid} followers={followers} "
          f"posts={profile.get('post_count') or '?'}",
          file=sys.stderr, flush=True)
    try:
        posts, cut_posts = page_timeline(ig, handle, doc_posts, delay, max_pages)
    except (urllib.error.HTTPError, RuntimeError) as e:
        print(f"  timeline doc_id looks stale ({e}) — discovering from JS bundle",
              file=sys.stderr, flush=True)
        found = discover_doc_ids(ig, html)
        doc_posts = found.get("PolarisProfilePostsQuery", doc_posts)
        print(f"  using doc_id={doc_posts}", file=sys.stderr, flush=True)
        posts, cut_posts = page_timeline(ig, handle, doc_posts, delay, max_pages)

    try:
        plays, cut_plays = page_clips(ig, uid, doc_clips, delay, max_pages)
    except (urllib.error.HTTPError, RuntimeError) as e:
        print(f"  clips pass failed ({e}) — continuing without play counts",
              file=sys.stderr, flush=True)
        plays, cut_plays = {}, False

    for p in posts:
        if p["code"] in plays:
            p["play_count"] = plays[p["code"]]

    posts.sort(key=lambda p: p.get("taken_at") or 0, reverse=True)
    (out / "index.json").write_text(json.dumps({
        "profile": profile, "scraped_at": int(time.time()),
        "doc_ids": {"posts": doc_posts, "clips": doc_clips},
        # A truncated catalogue is not a complete one. Getting this wrong is
        # worse than the truncation itself: rank.py would then compute a
        # baseline from a slice and present it as the creator's median.
        "complete": not (cut_posts or cut_plays),
        "truncated": {"timeline": cut_posts, "clips": cut_plays,
                      "max_pages": max_pages},
        "posts": posts,
    }, indent=2, ensure_ascii=False))

    reels = [p for p in posts if p["is_reel"]]
    withpc = [p for p in reels if p["play_count"]]
    print(f"  DONE: {len(posts)} posts, {len(reels)} reels, "
          f"{len(withpc)} with play counts -> {out/'index.json'}",
          file=sys.stderr, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("handle")
    ap.add_argument("--delay", type=float, default=2.0)
    # A safety valve, not a budget. Both passes stop on their own when the
    # cursor runs out; this only bounds a runaway. The clips pass is the
    # binding one -- 12 reels a page means a 1,300-reel account needs ~110.
    ap.add_argument("--max-pages", type=int, default=400)
    a = ap.parse_args()
    scrape(a.handle.lstrip("@"), a.delay, a.max_pages)
