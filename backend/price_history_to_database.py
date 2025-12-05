# price_history_to_database.py

from datetime import date, timedelta
import pandas as pd
from psycopg2.extras import execute_values

import get_price_history as gph
import db 

# ---------- DB helpers ----------

def get_company_id_for_symbol(conn, symbol: str) -> int:
    """
    Look up company_id from the company table using stock_ticker.
    Assumes the company row already exists.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT company_id FROM company WHERE stock_ticker = %s",
            (symbol,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"No company row found for ticker {symbol}")
        return row[0]


def upsert_pricehistory_from_df(df: pd.DataFrame, symbol: str):
    """
    Insert/Update rows in pricehistory for the given symbol.
    Uses UNIQUE (company_id, trade_date) on pricehistory.
    """
    conn = db.get_connection()
    try:
        company_id = get_company_id_for_symbol(conn, symbol)

        rows = []
        for _, r in df.iterrows():
            rows.append(
                (
                    company_id,
                    r["date"].date(),          # trade_date
                    round(r["open"], 2),       # open_price
                    round(r["high"], 2),       # high_price
                    round(r["low"], 2),        # low_price
                    round(r["close"], 2),      # close_price
                    int(r["volume"]),          # volume
                )
            )

        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO pricehistory
                    (company_id, trade_date, open_price, high_price, low_price, close_price, volume)
                VALUES %s
                ON CONFLICT (company_id, trade_date) DO UPDATE
                SET open_price  = EXCLUDED.open_price,
                    high_price  = EXCLUDED.high_price,
                    low_price   = EXCLUDED.low_price,
                    close_price = EXCLUDED.close_price,
                    volume      = EXCLUDED.volume;
                """,
                rows,
            )
        conn.commit()
        print(f"[DB] Inserted/updated {len(rows)} rows for {symbol}")
    finally:
        conn.close()


# ---------- Backfill (historical load) ----------

def backfill_pricehistory_for_symbols(symbols, start_date: str, end_date: str):
    """
    One-time or occasional backfill from start_date to end_date.
    Uses get_daily_history() from Alpha Vantage + upsert into DB.
    """
    for symbol in symbols:
        print(f"[BACKFILL] Fetching history for {symbol} from {start_date} to {end_date}...")
        df = gph.get_daily_history(symbol, start_date, end_date)
        print(f"[BACKFILL] {symbol}: {len(df)} rows fetched.")
        upsert_pricehistory_from_df(df, symbol)


# ---------- Incremental update (daily) ----------

def get_last_trade_date(conn, company_id: int):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT MAX(trade_date) FROM pricehistory WHERE company_id = %s;",
            (company_id,),
        )
        row = cur.fetchone()
        return row[0]  # may be None


def update_latest_for_symbols(symbols):
    """
    Incremental update: from last stored date up to yesterday.
    """
    today = date.today()
    end = today - timedelta(days=1)

    for symbol in symbols:
        conn = db.get_connection()
        try:
            company_id = get_company_id_for_symbol(conn, symbol)
            last_date = get_last_trade_date(conn, company_id)
        finally:
            conn.close()

        if last_date is None:
            print(f"[UPDATE] No data for {symbol}. Run backfill first.")
            continue

        start = last_date + timedelta(days=1)
        if start > end:
            print(f"[UPDATE] {symbol} already up to date (last_date={last_date})")
            continue

        print(f"[UPDATE] Updating {symbol} from {start} to {end}...")
        df = gph.get_daily_history(symbol, start.isoformat(), end.isoformat())
        if df.empty:
            print(f"[UPDATE] No new rows for {symbol}")
        else:
            upsert_pricehistory_from_df(df, symbol)


# ---------- Script entry point ----------

if __name__ == "__main__":
    symbols = ["AAPL"]

    # First time: run backfill
    start = "2020-01-01"
    end = str(date.today() - timedelta(days=1))
    backfill_pricehistory_for_symbols(symbols, start, end)

    # Later: comment backfill and just run incremental updates:
    # update_latest_for_symbols(symbols)
