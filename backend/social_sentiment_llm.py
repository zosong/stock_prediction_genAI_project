# social_sentiment_llm.py

from typing import Tuple, List
from db import get_connection
import os
from openai import OpenAI
import json
from db_helper import get_symbol_for_company_id

openai_api_key = os.environ.get("OPENAI_API_KEY")
if not openai_api_key:
    raise RuntimeError("OPENAI_API_KEY environment variable not set.")

llm = OpenAI(api_key=openai_api_key)

# ---------- LLM sentiment analysis with real LLM calls ---------- 
def analyze_social_sentiment_with_llm(content: str, company_id: int, symbol: str) -> Tuple[str, float]:
    """
    Analyze sentiment of social media posts using an LLM.
    Returns a tuple (label, score) where label is one of 'bullish', 'neutral', 'bearish'
    and score is a float between -1.0 and 1.0
    """

    if not content: 
        print("Empty content received for sentiment analysis. Returning neutral sentiment.")
        return "neutral", 0.0
    
    print(f"len={len(content)} preview={content[:120]!r}")
    
    prompt = """
        Target company: {symbol} (company_id={company_id})

        Task:
        Given the social media post below, infer the sentiment toward the target company's stock price over the near term (hours to days).

        Post:
        {post}

        Output requirements:
        - Return ONLY a JSON object with exactly these keys: "label" and "score".
        - "label" must be one of: bullish, neutral, bearish
        - "score" must be a REAL number in [-1.0, 1.0], rounded to 2 decimals.
        - Scores are CONTINUOUS. The example values below are reference points only; do NOT restrict yourself to them.
        - Do NOT include any explanation, commentary, or extra keys.

        Interpretation rules:
        1) Focus on price impact, not emotion. Product praise/complaints without a financial catalyst should usually be mild.
        2) If the post is unclear, vague, off-topic, or could refer to something other than the target company, choose neutral with a score near 0.00.
        3) If the post is pure hype/doomposting with no specific catalyst (no earnings, guidance, legal/regulatory news, major deal, major macro shock, etc.), keep the magnitude mild (generally within ±0.30).
        4) If the post describes a credible catalyst likely to move the stock, allow stronger magnitude (can exceed ±0.30).
        5) Treat sarcasm/irony as uncertain unless the direction is clearly indicated; otherwise prefer neutral near 0.00.

        Score calibration reference points (examples only):
        +1.00 = strong positive expected price impact (clear catalyst: earnings beat + raised guidance, major contract win, approval, etc.)
        +0.60 = moderately positive catalyst
        +0.20 = mildly positive / optimistic but weak evidence
        0.00 = mixed, unclear, or no clear price impact
        -0.20 = mildly negative / pessimistic but weak evidence
        -0.60 = moderately negative catalyst
        -1.00 = strong negative expected price impact (clear catalyst: earnings miss + cut guidance, major lawsuit/regulatory action, major product recall, etc.)

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
                    "content": "You are a financial sentiment classifier for social media posts.",
                },
                {
                    "role": "user",
                    "content": prompt.format(post=content, symbol=symbol, company_id=company_id),
                },
            ],
            max_tokens=100,
            model="gpt-4o-mini",
            temperature=0,
            response_format=response_format,
        )
        text = response.choices[0].message.content.strip()
        print("RAW:", text)
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
        


def fetch_posts_needing_sentiment_analysis(limit: int = 100) -> List[Tuple[int, str, int]]:
    """
    Fetch posts from the database that need sentiment analysis.
    Returns a list of (post_id, content) tuples.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sm.post_id, content, spcl.company_id
                FROM social_media sm
                LEFT JOIN social_post_sentiment sps ON sm.post_id = sps.post_id
                JOIN social_post_company_link spcl ON sm.post_id = spcl.post_id
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
    
    conn = get_connection()
    company_ids = {cid for _, _, cid in posts}
    company_symbol_cache = {}
    for cid in company_ids:
        sym = get_symbol_for_company_id(conn, cid)
        company_symbol_cache[cid] = sym if sym else "UNKNOWN"
    conn.close()

    for post_id, content, company_id in posts:
        print(f"Analyzing post_id={post_id}...")
        label, score = analyze_social_sentiment_with_llm(content[:1500], company_id, company_symbol_cache.get(company_id, "UNKNOWN"))  # Truncate to first 1500 chars
        print(f"  -> label={label}, score={score}")
        upsert_social_post_sentiment(post_id, label, round(score, 2))

    print(f"Processed sentiment for {len(posts)} posts.")

if __name__ == "__main__":
    run_sentiment_batch(batch_size=50)
    