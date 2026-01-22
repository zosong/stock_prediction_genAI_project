# article_sentiment_llm.py

from typing import Tuple, List
from db import get_connection
import os
from openai import OpenAI
import json

openai_api_key = os.environ.get("OPENAI_API_KEY")
if not openai_api_key:
    raise RuntimeError("OPENAI_API_KEY environment variable not set.")

llm = OpenAI(api_key=openai_api_key)

# ---------- LLM sentiment analysis with real LLM calls ---------- 
def analyze_sentiment_with_llm(title: str, summary: str) -> Tuple[str, float]:
    """
    Analyze sentiment of a news article using an LLM.
    Returns (label, score) where label is one of 'bullish', 'neutral', 'bearish'
    and score is a float between -1.0 and 1.0
    """

    if not summary:
        summary = ""
    if not title:
        raise ValueError("Title cannot be empty for sentiment analysis. Article must have at least a title.")

    prompt = """
        Given the following news article about a public company:
        Title:
        {title}
        Summary:
        {summary}
        Classify the sentiment toward the company's stock price.
        Rules:
        - Output one of: bullish, neutral, bearish
        - Output a numeric score between -1.0 and 1.0
        - Positive means price-positive, negative means price-negative
        - Do NOT include explanations

        +1.0 strong positive stock impact (beats + raised guidance, major contract win) 
        +0.3 mild positive
        0.0 unclear/mixed
        -0.3 mild negative
        -1.0 strong negative (miss + cut guidance, major lawsuit/regulatory action)
    """

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "article_sentiment",
            "strict": True,
            "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "label": {"type": "string", "enum": ["bullish", "neutral", "bearish"]},
                "score": {"type": "number", "minimum": -1.0, "maximum": 1.0}
            },
            "required": ["label", "score"]
            }
        }
    }

    response = llm.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a financial sentiment classifier.",
            },
            {
                "role": "user",
                "content": prompt.format(title=title, summary=summary),
            },
        ],
        max_tokens=100,
        model="gpt-4o-mini",
        temperature=0,
        response_format=response_format,
    )
    text = response.choices[0].message.content.strip()
    
    try:
        result = json.loads(text)
        label = result["label"]
        score = float(result["score"])
        if label not in ("bullish", "neutral", "bearish"):
            raise ValueError(f"Invalid label: {label}")
        if not (-1.0 <= score <= 1.0):
            raise ValueError(f"Score out of range: {score}")
        return label, score
    except Exception as e:
        raise RuntimeError(f"Failed to parse LLM response: {text}\nError: {e}")


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
    # result = analyze_sentiment_with_llm(
    #     title="Tech Giant Reports Record Earnings Amid Market Uncertainty",
    #     summary="In a surprising turn of events, the leading technology company has reported record-breaking earnings for the fiscal quarter, defying market expectations and showcasing resilience in uncertain economic times."
    # )

    # print(f"Test sentiment analysis result: {result}")
