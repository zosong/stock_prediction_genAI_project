import time
import requests

# ============================================================
# 1. Rate-Limited Alpha Vantage GET
# ============================================================
LAST_CALL_TS = 0
CALLS_THIS_MINUTE = 0

def alpha_vantage_get(params: dict):
    global LAST_CALL_TS, CALLS_THIS_MINUTE

    now = time.time()
    # reset counter every 60 seconds
    if now - LAST_CALL_TS > 60:
        CALLS_THIS_MINUTE = 0

    # if we already hit 5 req/min, sleep until window resets
    if CALLS_THIS_MINUTE >= 5:
        sleep_for = 60 - (now - LAST_CALL_TS)
        if sleep_for > 0:
            time.sleep(sleep_for)
        CALLS_THIS_MINUTE = 0

    LAST_CALL_TS = time.time()
    CALLS_THIS_MINUTE += 1

    url = "https://www.alphavantage.co/query"
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


