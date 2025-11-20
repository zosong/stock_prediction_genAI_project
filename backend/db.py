import os
import psycopg2

def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        port=5432,
    )

def test_get_companies():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT company_id, company_name, stock_ticker FROM Company LIMIT 5;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

if __name__ == "__main__":
    print(test_get_companies())
