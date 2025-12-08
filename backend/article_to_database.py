# article_to_database.py

from datetime import datetime

from db import get_connection
from get_news import get_news_for_symbol
import db_helper


# ---------- DB helpers ----------


def find_article_id_by_url(conn, url: str):
    """
    Returns article_id if URL exists, else None.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT article_id FROM article WHERE url = %s;",
            (url,),
        )
        row = cur.fetchone()
        return row[0] if row else None


def insert_or_update_article(conn, title, summary, pub_dt, url, source_location):
    """
    Insert a new article row if url not seen before; otherwise update fields.
    Returns article_id.
    """
    existing_id = find_article_id_by_url(conn, url)
    if existing_id:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE article
                SET title = %s,
                    summary = %s,
                    publication_date = %s,
                    source_location = %s
                WHERE article_id = %s;
                """,
                (title, summary, pub_dt, source_location, existing_id),
            )
        return existing_id

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO article (title, summary, publication_date, url, source_location)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING article_id;
            """,
            (title, summary, pub_dt, url, source_location),
        )
        article_id = cur.fetchone()[0]
    return article_id


def ensure_article_company_link(conn, article_id: int, company_id: int):
    """
    Insert into articlecompanylink; ignore if it already exists.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO articlecompanylink (article_id, company_id)
            VALUES (%s, %s)
            ON CONFLICT (article_id, company_id) DO NOTHING;
            """,
            (article_id, company_id),
        )


# ---------- Main loader ----------

def load_news_for_symbol(symbol: str, limit: int = 50):
    """
    Fetch recent news for a symbol and load into:
      - article (metadata + summary)
      - articlecompanylink (company mapping)

    For now:
      - summary = Alpha Vantage's summary snippet
      - source_location = publisher name (e.g. "Reuters", "CNBC")
    """
    conn = get_connection()
    try:
        company_id = db_helper.get_company_id_for_symbol(conn, symbol)
        news_items = get_news_for_symbol(symbol, limit=limit)
        count = 0

        for item in news_items:
            # time_published like "20251203T134500"
            time_str = item.get("time_published")
            if not time_str:
                continue
            try:
                pub_dt = datetime.strptime(time_str, "%Y%m%dT%H%M%S")
            except ValueError:
                continue

            title = (item.get("title") or "").strip()
            summary = (item.get("summary") or "").strip()
            url = (item.get("url") or "").strip()
            source = (item.get("source") or "").strip()

            if not url or not title:
                continue  # skip weird items

            # Insert/update article row
            article_id = insert_or_update_article(
                conn,
                title=title,
                summary=summary,
                pub_dt=pub_dt,
                url=url,
                source_location=source,  # we store publisher here for now
            )

            # Link to company
            ensure_article_company_link(conn, article_id, company_id)
            count += 1

        conn.commit()
        print(f"[NEWS] Stored/updated {count} articles for {symbol}")
    finally:
        conn.close()


if __name__ == "__main__":
    symbols = ["AAPL", "AMZN", "TSLA"]
    for sym in symbols:
        load_news_for_symbol(sym, limit=50)