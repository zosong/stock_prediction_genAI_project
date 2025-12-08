
def get_company_id_for_symbol(conn, symbol: str) -> int:
    """
    Look up company_id from the company table using stock_ticker.
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
