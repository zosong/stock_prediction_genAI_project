
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
    
def get_symbol_for_company_id(conn, company_id: int) -> str:
    """
    Look up stock_ticker from the company table using company_id.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT stock_ticker FROM company WHERE company_id = %s",
            (company_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"No company row found for company_id {company_id}")
        return row[0]
    
def find_post_id_by_external_id(conn, external_post_id: str):
    """
    Returns post_id if external_post_id exists, else None.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT post_id FROM social_media_post WHERE external_post_id = %s;",
            (external_post_id,),
        )
        row = cur.fetchone()
        return row[0] if row else None
