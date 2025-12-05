import os
import requests
from datetime import date, timedelta, datetime
import time
import pandas as pd

API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY")

if not API_KEY:
    raise RuntimeError("Please set ALPHAVANTAGE_API_KEY in your environment.")



def get_daily_history(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetch daily OHLCV for a stock symbol between start_date and end_date
    using Alpha Vantage TIME_SERIES_DAILY (adjusted close).

    Dates are strings in 'YYYY-MM-DD' format.
    Returns a pandas DataFrame with columns:
    [date, open, high, low, close, volume]
    """

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": "compact",   # full history; use 'compact' for last 100 days
        "apikey": API_KEY,
    }

    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()

    if "Time Series (Daily)" not in data:
        raise RuntimeError(f"Alpha Vantage error for {symbol}: {data}")

    ts = data["Time Series (Daily)"]

    # Convert to DataFrame
    df = (
        pd.DataFrame.from_dict(ts, orient="index")
        .rename(
            columns={
                "1. open": "open",
                "2. high": "high",
                "3. low": "low",
                "4. close": "close",
                "5. volume": "volume",
            }
        )
        .reset_index()
        .rename(columns={"index": "date"})
    )

    # Convert types
    df["date"] = pd.to_datetime(df["date"])
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    df["volume"] = df["volume"].astype(int)

    # Filter by date range
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    df = df[(df["date"] >= start) & (df["date"] <= end)]

    # Sort by date ascending
    df = df.sort_values("date").reset_index(drop=True)

    return df


def write_to_file(df: pd.DataFrame, filename: str):
    df.to_csv(filename, index=False)
    print(f"Wrote {len(df)} rows to {filename}")


if __name__ == "__main__":
    # Example: from 2020-01-01 to yesterday
    symbol = "AAPL"
    start = "2020-01-01"
    end = str(date.today() - timedelta(days=1))

    df_prices = get_daily_history(symbol, start, end)
    write_to_file(df_prices, f"{symbol}_daily_prices.csv")
    print(df_prices.head())