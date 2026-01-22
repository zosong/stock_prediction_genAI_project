# posts_to_database.py
from db import get_connection
from get_social_media_posts import fetch_pages
import db_helper

def upsert_post(conn, post: dict) -> int:
    """
    Upsert into social_media using (platform, external_post_id) as the natural key.
    Returns the internal post_id (PK).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO social_media (
                platform, external_post_id, user_id, author_handle,
                content, post_time, url, like_count, repost_count
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (platform, external_post_id)
            DO UPDATE SET
                user_id = EXCLUDED.user_id,
                author_handle = EXCLUDED.author_handle,
                content = EXCLUDED.content,
                post_time = EXCLUDED.post_time,
                url = COALESCE(EXCLUDED.url, social_media.url),
                like_count = GREATEST(social_media.like_count, EXCLUDED.like_count),
                repost_count = GREATEST(social_media.repost_count, EXCLUDED.repost_count)
            RETURNING post_id;
            """,
            (
                post["platform"],
                post["external_post_id"],
                post["user_id"],
                post["author_handle"],
                post["content"],
                post["post_time"],
                post.get("url") or "",          # because url is NOT NULL in your schema
                post.get("like_count", 0),
                post.get("repost_count", 0),
            )
        )
        return cur.fetchone()[0]

def ensure_posts_company_link(conn, post_id: int, company_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO social_post_company_link (post_id, company_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
            """,
            (post_id, company_id),
        )

def fetch_and_store_posts_for_symbol(symbol: str, pages: int = 1, max_results: int = 10) -> None:
    """
    Fetch posts for one ticker and store them, linking to company_id.
    Keep calls small because the X free plan is heavily rate-limited.
    """
    queries = {
        "TSLA": '(TSLA OR "Tesla") -is:retweet lang:en',
        "AAPL": '(AAPL OR "Apple Inc" OR "Apple stock") -is:retweet lang:en',
        "AMZN": '(AMZN OR "Amazon" OR "Amazon stock") -is:retweet lang:en',
    }

    if symbol not in queries:
        print(f"Unsupported symbol: {symbol}")
        return

    conn = get_connection()
    try:
        company_id = db_helper.get_company_id_for_symbol(conn, symbol)

        query = queries[symbol]
        start_time = None

        posts = fetch_pages(query, pages=pages, max_results=max_results, start_time=start_time)

        stored = 0
        for post in posts:
            try:
                internal_post_id = upsert_post(conn, post)
                ensure_posts_company_link(conn, internal_post_id, company_id)
                stored += 1
            except Exception as e:
                print(f"Error storing post {post.get('external_post_id')} for {symbol}: {e}")

        conn.commit()
        print(f"{symbol}: fetched={len(posts)} stored/linked={stored}")

    finally:
        conn.close()

if __name__ == "__main__":
    # Keep it to ONE symbol per run on Free plan
    # fetch_and_store_posts_for_symbol("TSLA", pages=1, max_results=10)
    # fetch_and_store_posts_for_symbol("AAPL", pages=1, max_results=10)
    fetch_and_store_posts_for_symbol("AMZN", pages=1, max_results=10)
