# article_sentiment_llm.py

from typing import Tuple, List
from db import get_connection


# Placeholder for LLM sentiment analysis, to be replaced with real LLM calls later.
def analyze_sentiment_with_llm(title: str, summary: str) -> Tuple[str, float]:
    """
    Replace this later with a real LLM call.
    For now, simple keyword-based dummy logic so we can test the pipeline.
    """
    text = f"{title}\n{summary}".lower()

    if "all-time high" in text or "record" in text or "beats" in text:
        return "bullish", 0.7
    if "downgrade" in text or "cuts rating" in text or "misses" in text:
        return "bearish", -0.6
    return "neutral", 0.0


# Fetch articles that don't have sentiment yet
def fetch_articles_needing_sentiment(limit: int = 50) -> List[tuple]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.article_id, a.title, a.summary
                FROM article a
                LEFT JOIN article_sentiment s ON a.article_id = s.article_id
                WHERE s.article_id IS NULL
                ORDER BY a.publication_date DESC
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()
        return rows
    finally:
        conn.close()


# Insert/update sentiment row
def upsert_article_sentiment(article_id: int, label: str, score: float):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO article_sentiment (article_id, sentiment_label, sentiment_score)
                VALUES (%s, %s, %s)
                ON CONFLICT (article_id) DO UPDATE
                SET sentiment_label = EXCLUDED.sentiment_label,
                    sentiment_score = EXCLUDED.sentiment_score;
                """,
                (article_id, label, score),
            )
        conn.commit()
    finally:
        conn.close()


def run_sentiment_batch(batch_size: int = 30):
    rows = fetch_articles_needing_sentiment(limit=batch_size)
    if not rows:
        print("[SENTIMENT] No articles need sentiment.")
        return

    for article_id, title, summary in rows:
        print(f"[SENTIMENT] Analyzing article_id={article_id}...")
        label, score = analyze_sentiment_with_llm(title, summary)
        print(f"  -> label={label}, score={score}")
        upsert_article_sentiment(article_id, label, score)


if __name__ == "__main__":
    run_sentiment_batch(batch_size=30)
