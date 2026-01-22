# get_social_media_posts.py
import os
import time
import requests
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict, Any

X_BEARER = os.environ["X_BEARER_TOKEN"]
ENDPOINT = "https://api.x.com/2/tweets/search/recent"

def x_recent_search(
    query: str,
    next_token: Optional[str] = None,
    max_results: int = 100,
    start_time: Optional[str] = None,   # ISO8601 UTC, e.g. "2026-01-12T00:00:00Z"
) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {X_BEARER}"}
    params = {
        "query": query,
        "max_results": min(max(max_results, 10), 100),
        "tweet.fields": "created_at,public_metrics,author_id",
        "expansions": "author_id",
        "user.fields": "username",
    }
    if next_token:
        params["next_token"] = next_token
    if start_time:
        params["start_time"] = start_time

    # retry loop for transient errors / throttling
    backoff = 5
    for attempt in range(1, 6):
        r = requests.get(ENDPOINT, headers=headers, params=params, timeout=30)

        if r.status_code in (401, 403):
            # Token/permissions/plan issues are common at first
            raise RuntimeError(
                f"X API auth/permission error ({r.status_code}). "
                f"Response: {r.text}"
            )

        if r.status_code == 429:
            reset = r.headers.get("x-rate-limit-reset")
            remaining = r.headers.get("x-rate-limit-remaining")
            limit = r.headers.get("x-rate-limit-limit")

            msg = f"[429] Rate limited. remaining={remaining} limit={limit} reset={reset}"
            if reset and reset.isdigit():
                reset_local = datetime.fromtimestamp(int(reset), tz=timezone.utc).astimezone()
                msg += f" (local reset: {reset_local.isoformat()})"
            raise RuntimeError(msg)


        if 500 <= r.status_code < 600:
            print(f"[{r.status_code}] Server error. Sleeping {backoff}s (attempt {attempt}/5)...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
            continue

        if not r.ok:
            # X usually returns a JSON body with details under "errors"
            try:
                details = r.json()
            except Exception:
                details = r.text
            raise RuntimeError(
                f"X API error {r.status_code}\n"
                f"URL: {r.url}\n"
                f"Response: {details}"
            )

        return r.json()


    raise RuntimeError("Failed after retries due to throttling or server errors.")

def normalize(resp: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    users = {u["id"]: u for u in resp.get("includes", {}).get("users", [])}
    out: List[Dict[str, Any]] = []

    for t in resp.get("data", []) or []:
        author_id = t.get("author_id", "")
        username = users.get(author_id, {}).get("username", "")
        metrics = t.get("public_metrics", {}) or {}
        tid = t.get("id", "")

        out.append({
            "platform": "x",
            "external_post_id": tid,
            "user_id": author_id,
            "author_handle": username,
            "content": t.get("text", ""),
            "post_time": t.get("created_at"),
            "url": f"https://x.com/{username}/status/{tid}" if username and tid else None,
            "like_count": int(metrics.get("like_count", 0)),
            "repost_count": int(metrics.get("retweet_count", 0)),
        })

    next_token = resp.get("meta", {}).get("next_token")
    return out, next_token

def preview(rows: List[Dict[str, Any]], n: int = 5) -> None:
    print(f"Fetched {len(rows)} posts. Showing {min(n, len(rows))}:\n")
    for i, r in enumerate(rows[:n], start=1):
        text = (r["content"] or "").replace("\n", " ")
        if len(text) > 180:
            text = text[:180] + "..."
        print(f"{i}. {r['post_time']}  @{r['author_handle']}  likes={r['like_count']} rts={r['repost_count']}")
        print(f"   id={r['external_post_id']}")
        print(f"   {text}")
        print(f"   {r['url']}\n")

def fetch_pages(query: str, pages: int = 2, max_results: int = 50, start_time: Optional[str] = None):
    all_rows: List[Dict[str, Any]] = []
    next_token: Optional[str] = None

    for p in range(pages):
        resp = x_recent_search(
            query=query,
            next_token=next_token,
            max_results=max_results,
            start_time=start_time,
        )
        rows, next_token = normalize(resp)
        all_rows.extend(rows)

        print(f"Page {p+1}/{pages}: got {len(rows)} rows. next_token={'yes' if next_token else 'no'}")
        if not next_token:
            break

    # de-dupe by external_post_id just for display sanity
    seen = set()
    deduped = []
    for r in all_rows:
        if r["external_post_id"] in seen:
            continue
        seen.add(r["external_post_id"])
        deduped.append(r)

    return deduped

def main():
    queries = {
        "TSLA": "($TSLA OR TSLA OR Tesla) -is:retweet lang:en",
        "AMZN": "($AMZN OR AMZN OR Amazon) -is:retweet lang:en",
        "AAPL": "($AAPL OR AAPL OR Apple) -is:retweet lang:en",
    }

#     queries = {
#     "TSLA": "($TSLA OR Tesla) -is:retweet lang:en",
# }
#     start_time = None
#     rows = fetch_pages(queries, pages=1, max_results=10, start_time=start_time)
#     preview(rows, n=5)

    # # optional: start_time for “today UTC” testing
    # # start_time = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")
    start_time = None

    for ticker, q in queries.items():
        print("=" * 80)
        print(f"{ticker} query: {q}")
        rows = fetch_pages(q, pages=2, max_results=50, start_time=start_time)
        preview(rows, n=5)

if __name__ == "__main__":
    main()

