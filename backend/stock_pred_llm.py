# stock_pred_llm.py

from typing import Tuple, List
from db import get_connection
import db_helper
from datetime import datetime, date
import pandas as pd
import numpy as np
# ---------- Create feature pack ----------

def get_schema_version() -> int:
    """
    Retrieve the current schema version for feature packs.
    """
    return 1  # Example static version; in practice, this might be fetched from a config or database.

def get_identity(conn, company_id: int, as_of_date: date) -> dict:
    """
    Retrieve identity features for the given stock symbol as of the specified date.
    """

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT stock_ticker
            FROM company
            WHERE company_id = %s;
            """,
            (company_id,),
        )
        row = cur.fetchone()
        if row:
            return {
                "symbol": row[0],
                "as_of_date": as_of_date.isoformat(),
                "market_timezone": "America/New_York",
            }
        else:
            raise ValueError(f"No company found with id {company_id}")

TRADING_DAYS = 20

def get_price_data(conn, company_id: int, as_of_date: date) -> dict:
    """
    Retrieve price-related features for the given stock symbol as of the specified date.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT trade_date, close_price
                FROM price_history
                WHERE company_id = %s AND trade_date <= %s
                ORDER BY trade_date DESC
                LIMIT %s;
                """,
                (company_id, as_of_date, TRADING_DAYS),
            )
            rows = cur.fetchall()

            if not rows:
                raise ValueError("No price history available for the given company_id and date.")

            df = pd.DataFrame(rows, columns=['trade_date', 'close_price'])
            df = df.iloc[::-1].reset_index(drop=True) 

            recent_daily_returns = df["close_price"].pct_change().dropna().tolist()
            recent_daily_returns = [float(ret) for ret in recent_daily_returns]
            
            if len(df) >= 5:
                df["moving_average_5"] = df["close_price"].rolling(window=5).mean()
                moving_average_5 = df["moving_average_5"].iloc[-1]
                if pd.isna(moving_average_5):
                    moving_average_5 = None
                else:
                    moving_average_5 = float(moving_average_5)
            else:
                moving_average_5 = None

            if len(recent_daily_returns) == 0:
                recent_volatility = None
            else:
                recent_volatility = float(np.std(recent_daily_returns))

            last_close_price = float(df.loc[df.index[-1], "close_price"])
            recent_avg_price = float(df["close_price"].mean())

            relative_position = (last_close_price - recent_avg_price) / recent_avg_price

            prices = {
                "config": {"lookback_trading_days" : TRADING_DAYS, "order": "oldest_to_newest", "ma_window_days": 5, "volatility_std_ddof": 0},
                 "recent_closes": {"dates":  [r[0].isoformat() for r in rows[::-1]], "closes": [float(r[1]) for r in rows[::-1]]}, # close prices from most recent trading days
                 "recent_daily_returns": recent_daily_returns,
                 "moving_average_5": moving_average_5,
                 "recent_volatility": recent_volatility, # standard deviation of recent daily returns
                 "last_close": last_close_price,
                 "mean_close": recent_avg_price,
                 "relative_position": relative_position, # last price relative to recent average
                }
            return prices
    except Exception as e:
        print(f"[ERROR] Failed to fetch price data: {e}")  
        raise  RuntimeError("Failed to retrieve price data.") from e

def get_news_data(conn, company_id: int, as_of_date: date) -> dict:
    """
    Retrieve news-related features for the given stock symbol as of the specified date.
    """
    try:
        cutoff_tz = pd.Timestamp(as_of_date).tz_localize("America/New_York")
        cutoff_end = cutoff_tz + pd.Timedelta(days=1)
        window_start = cutoff_end - pd.Timedelta(days=7)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.article_id, a.publication_date, ase.sentiment_score
                FROM article_company_link acl
                JOIN article a 
                ON acl.article_id = a.article_id
                LEFT JOIN article_sentiment ase 
                ON a.article_id = ase.article_id
                WHERE acl.company_id = %s AND a.publication_date >= %s AND a.publication_date < %s;
                """,
                (company_id, window_start, cutoff_end),
            )
            rows = cur.fetchall()
            df = pd.DataFrame(rows, columns=['article_id', 'publication_date', 'sentiment_score'])

            article_count_7d = int(df.shape[0])

            scored = df['sentiment_score'].dropna()
            scored_count = len(scored)
            sentiment_scored_count_7d = scored_count

            if scored_count == 0:
                sentiment_mean_7d = None    
                sentiment_std_7d = None
            elif scored_count == 1:
                sentiment_std_7d = None
                sentiment_mean_7d = float(scored.iloc[0]) # only one scored article
            else:
                sentiment_std_7d = float(np.std(scored, ddof=0))
                sentiment_mean_7d = float(scored.mean())

            cur.execute(
                """
                SELECT a.article_id, a.title, a.summary, a.publication_date, ase.sentiment_score
                FROM article_company_link acl
                JOIN article a 
                ON acl.article_id = a.article_id
                LEFT JOIN article_sentiment ase 
                ON a.article_id = ase.article_id
                WHERE acl.company_id = %s AND a.publication_date >= %s AND a.publication_date < %s
                ORDER BY a.publication_date DESC
                LIMIT 10;
                """,
                (company_id, window_start, cutoff_end),
            )
            rows_sum = cur.fetchall()
            recent_articles = [{"article_id": r[0], "title": r[1], "summary": r[2], "publication_date": r[3], "sentiment_score": r[4]} for r in rows_sum]

            articles = {
                "config": {"lookback_window": 7, "market_timezone": "America/New_York", "max_articles": 10, "order": "most_recent_first", "sentiment_std_ddof": 0, "cutoff_rule": "publication_date < next_midnight_market_tz"},
                "article_count_7d": article_count_7d,
                "sentiment_mean_7d": sentiment_mean_7d,
                "sentiment_scored_count_7d": sentiment_scored_count_7d,
                "sentiment_std_7d": sentiment_std_7d,
                "recent_articles": recent_articles,
            }

            return articles
    except Exception as e:
        print(f"[ERROR] Failed to fetch news data: {e}")  
        raise RuntimeError("Failed to retrieve news data.") from e

MAX_POSTS = 1000
def get_social_data(conn, company_id: int, as_of_date: date) -> dict:
    """
    Retrieve social media-related features for the given stock symbol as of the specified date.
    """
    try:   
        cutoff_tz = pd.Timestamp(as_of_date).tz_localize("America/New_York")
        cutoff_end = cutoff_tz + pd.Timedelta(days=1)
        window_start = cutoff_end - pd.Timedelta(days=7)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT smp.post_id, smp.post_time, smp.content, spcl.company_id
                FROM social_media_post smp
                JOIN social_post_company_link spcl
                ON smp.post_id = spcl.post_id
                WHERE spcl.company_id = %s AND post_time >= %s AND post_time < %s
                ORDER BY post_time DESC
                LIMIT %s;
                """,
                (company_id, window_start, cutoff_end, MAX_POSTS),
            )
            rows = cur.fetchall()
            # df = pd.DataFrame(rows, columns=['post_id', 'post_time', 'content', 'company_id'])
            recent_posts_7d = [{"post_id": r[0], "post_time": r[1], "content_preview": r[2][:200] if r[2] else None, "company_id": r[3]} for r in rows]

            cur.execute(
                """
                SELECT COUNT(*), MAX(post_time)
                FROM social_media_post smp
                JOIN social_post_company_link spcl
                ON smp.post_id = spcl.post_id
                WHERE spcl.company_id = %s AND post_time >= %s AND post_time < %s;
                """,
                (company_id, window_start, cutoff_end),
            )
            count_row = cur.fetchone()
            post_count_7d = count_row[0] if count_row else 0 
            hours_since_last_post = None
            if count_row and count_row[1]:
                last_post_time = count_row[1]
                last_post_time = pd.Timestamp(last_post_time).tz_convert("America/New_York")
                time_diff = cutoff_end - last_post_time
                hours_since_last_post = time_diff.total_seconds() / 3600.0

            social = {
                "config": {"lookback_window": 7, "market_timezone": "America/New_York", "cutoff_rule": "post_time < next_midnight_market_tz", "max_posts": MAX_POSTS, "window_start": window_start.isoformat(), "cutoff_end": cutoff_end.isoformat()},
                "post_count_7d": post_count_7d,
                "recent_posts_7d": recent_posts_7d,
                "hours_since_last_post": hours_since_last_post,
            }

            return social
    except Exception as e:
        print(f"[ERROR] Failed to fetch social data: {e}")  
        raise RuntimeError("Failed to retrieve social data.") from e

def get_data_quality_metrics(conn, company_id: int, as_of_date: date) -> dict:
    """
    Retrieve data quality metrics for the given stock symbol as of the specified date.
    """
    # Placeholder implementation; in practice, compute based on data completeness and accuracy.
    return {
        "completeness": 0.95,
        "accuracy": 0.98,
    }

def get_as_of_date(conn, company_id) -> date:
    """
    Get the latest trading date in price_history for the company to be used as the 'as of' date for feature pack creation.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT max(trade_date)
            FROM price_history
            WHERE company_id = %s;
            """,
            (company_id,),
        )
        row = cur.fetchone()
        if row[0] is None:
            raise ValueError("No price history available for the given company_id.")
        return row[0]

def create_feature_pack(symbol: str) -> dict:
    """
    Create a feature pack for the given stock symbol as of the latest available trading date in the database.
    A feature pack is a set of deterministic features used for stock price prediction.
    """
    conn = get_connection()
    try:
        company_id = db_helper.get_company_id_for_symbol(conn, symbol)
        if company_id is None:
            raise ValueError(f"Company ID not found for symbol: {symbol}")
        
        # Get features
        as_of_date = get_as_of_date(conn, company_id)
        schema_version = get_schema_version()
        identity = get_identity(conn, company_id, as_of_date)
        price = get_price_data(conn, company_id, as_of_date)
        news = get_news_data(conn, company_id, as_of_date)
        social = get_social_data(conn, company_id, as_of_date)
        data_quality = get_data_quality_metrics(conn, company_id, as_of_date)
        
        feature_pack = {
            "schema_version": schema_version,
            "identity": identity,
            "price": price,
            "news": news,
            "social": social,
            "data_quality": data_quality,
        }
        
        print(f"[Feature Pack] Created feature pack for {symbol} as of {as_of_date}")
        return feature_pack
    finally:
        conn.close()

if __name__ == "__main__":
    print(get_as_of_date(get_connection(), 1))