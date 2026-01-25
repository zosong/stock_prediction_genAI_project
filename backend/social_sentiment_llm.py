# social_sentiment_llm.py

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
def analyze_social_sentiment_with_llm(content: str) -> Tuple[str, float]:
    """
    Analyze sentiment of social media posts using an LLM.
    Returns a tuple (label, score) where label is one of 'bullish', 'neutral', 'bearish'
    and score is a float between -1.0 and 1.0
    """
    if not content: 
        print("Empty content received for sentiment analysis. Returning neutral sentiment.")
        return "neutral", 0.0
    
    prompt = """
        Given the following social media post about a public company:
        Post:
        {post}
        Classify the sentiment toward the company's stock price.
        Rules:
        - Output one of: bullish, neutral, bearish
        - Output a numeric score between -1.0 and 1.0
        - Bullish means price-positive, bearish means price-negative
        - Do NOT include explanations
        - If unclear or just commentary without financial signal → neutral near 0.0
        - Hype language without facts should be mild unless strongly directional
        - If the post is just cheering/doomposting with no specific catalyst, keep the score mild (e.g., within ±0.3)

        +1.0 strong positive stock impact (beats + raised guidance, major contract win) 
        +0.3 mild positive
        0.0 unclear/mixed
        -0.3 mild negative
        -1.0 strong negative (miss + cut guidance, major lawsuit/regulatory action)
    """

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "social_sentiment",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "label": {"type": "string", "enum": ['bullish', 'neutral', 'bearish']},
                    "score": {"type": "number", "minimum": -1.0, "maximum": 1.0}
                },
                "required": ["label", "score"]
            }
        }
    }

    text = None
    try: 
        response = llm.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a financial sentiment classifier.",
                },
                {
                    "role": "user",
                    "content": prompt.format(post=content),
                },
            ],
            max_tokens=100,
            model="gpt-4o-mini",
            temperature=0,
            response_format=response_format,
        )
        text = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"LLM call failed for sentiment analysis: {e}")
        return "neutral", 0.0
        # raise RuntimeError(f"LLM call failed for sentiment analysis: {text}.") from e

    try:
        result = json.loads(text)
        label = result["label"]
        score = float(result["score"])
        return label, score
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        print(f"Failed to parse LLM response for sentiment analysis: {e}")
        # raise RuntimeError(f"Failed to parse LLM response: {text}") from e
        return "neutral", 0.0
        


def fetch_posts_needing_sentiment_analysis(limit: int = 100) -> List[Tuple[int, str]]:
    """
    Fetch posts from the database that need sentiment analysis.
    Returns a list of (post_id, content) tuples.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sm.post_id, content
                FROM social_media sm
                LEFT JOIN social_post_sentiment sps ON sm.post_id = sps.post_id
                WHERE sps.post_id IS NULL
                ORDER BY sm.post_time DESC
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()
            return rows
    finally:
        conn.close()

def upsert_social_post_sentiment(post_id: int, label: str, score: float) -> None:
    """
    Insert or update sentiment for a social media post.
    """
    conn = get_connection()

    try:
        with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO social_post_sentiment (post_id, sentiment_label, sentiment_score, scored_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (post_id)
                    DO UPDATE SET
                        sentiment_label = EXCLUDED.sentiment_label,
                        sentiment_score = EXCLUDED.sentiment_score,
                        scored_at = NOW();
                    """,
                    (post_id, label, score),
                )
                conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Failed to upsert sentiment for post_id={post_id}: {e}. Continuing with next post.")
    finally:
        conn.close()

def run_sentiment_batch(batch_size: int = 50) -> None:
    """
    Fetch posts needing sentiment analysis, analyze them with the LLM,
    and store the results back in the database.
    """
    posts = fetch_posts_needing_sentiment_analysis(limit=batch_size)
    if not posts:
        print("No posts need sentiment analysis.")
        return

    for post_id, content in posts:
        print(f"Analyzing post_id={post_id}...")
        label, score = analyze_social_sentiment_with_llm(content[:1500])  # Truncate to first 1500 chars
        print(f"  -> label={label}, score={score}")
        upsert_social_post_sentiment(post_id, label, score)

    print(f"Processed sentiment for {len(posts)} posts.")

if __name__ == "__main__":
    run_sentiment_batch(batch_size=50)
    