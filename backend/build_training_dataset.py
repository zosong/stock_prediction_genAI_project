import pandas as pd
from db import get_connection


def fetch_daily_features() -> pd.DataFrame:
    conn = get_connection()
    try:
        query = """
        SELECT
            ph.company_id,
            c.stock_ticker,
            ph.trade_date,
            ph.open_price,
            ph.close_price,
            ph.volume,
            COALESCE(COUNT(a.article_id), 0) AS num_articles,
            COALESCE(AVG(s.sentiment_score), 0.0) AS avg_sentiment_day
        FROM price_history ph
        JOIN company c
          ON ph.company_id = c.company_id
        LEFT JOIN article_company_link acl
          ON acl.company_id = ph.company_id
        LEFT JOIN article a
          ON a.article_id = acl.article_id
         AND DATE(a.publication_date) = ph.trade_date
        LEFT JOIN articlesentiment s
          ON s.article_id = a.article_id
        WHERE c.stock_ticker IN ('AAPL','AMZN','TSLA')
        GROUP BY
            ph.company_id,
            c.stock_ticker,
            ph.trade_date,
            ph.open_price,
            ph.close_price,
            ph.volume
        ORDER BY
            ph.company_id,
            ph.trade_date;
        """
        df = pd.read_sql(query, conn)
        return df
    finally:
        conn.close()

def add_labels_and_tech_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each company_id, compute:
      - next-day return
      - binary label_up
      - simple rolling features
    """
    # Ensure sorted
    df = df.sort_values(["company_id", "trade_date"]).copy()

    # 1) next day's close per company
    df["next_close"] = df.groupby("company_id")["close_price"].shift(-1)

    # 2) next-day return
    df["return_next_day"] = (df["next_close"] - df["close_price"]) / df["close_price"]

    # 3) binary label: 1 if next day up, else 0
    df["label_up"] = (df["return_next_day"] > 0).astype(int)

    # 4) same-day return feature
    df["return_today"] = (df["close_price"] - df["open_price"]) / df["open_price"]

    # 5) rolling 3-day avg sentiment (per company)
    df["avg_sentiment_3d"] = (
        df.groupby("company_id")["avg_sentiment_day"]
          .rolling(window=3, min_periods=1)
          .mean()
          .reset_index(level=0, drop=True)
    )

    # 6) rolling 5-day average volume
    df["volume_5d_mean"] = (
        df.groupby("company_id")["volume"]
          .rolling(window=5, min_periods=1)
          .mean()
          .reset_index(level=0, drop=True)
    )

    # 7) drop rows where we don't have next_close (no label)
    df = df[df["next_close"].notna()].reset_index(drop=True)

    return df

if __name__ == "__main__":
    df = fetch_daily_features()
    print("[DATASET] Raw daily rows:", len(df))

    df = add_labels_and_tech_features(df)
    print("[DATASET] Rows with label:", len(df))
    print(df.head())

    df.to_csv("training_dataset.csv", index=False)
    print("[DATASET] Saved to training_dataset.csv")
