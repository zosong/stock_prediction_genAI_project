import time
import requests
import os

API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY")
if not API_KEY:
    raise RuntimeError("Please set ALPHAVANTAGE_API_KEY in your environment.")

# ---- Rate limits (free tier) ----
MAX_CALLS_PER_MIN = 5
MIN_SECONDS_BETWEEN_CALLS = 1.2   # Alpha Vantage suggests 1 req/sec

WINDOW_START_TS = 0.0
CALLS_THIS_MINUTE = 0
LAST_REQUEST_TS = 0.0

def alpha_vantage_get(params: dict):
    global WINDOW_START_TS, CALLS_THIS_MINUTE, LAST_REQUEST_TS

    now = time.time()

    # Enforce >= 1 sec between calls (burst limit)
    gap = now - LAST_REQUEST_TS
    if gap < MIN_SECONDS_BETWEEN_CALLS:
        time.sleep(MIN_SECONDS_BETWEEN_CALLS - gap)

    now = time.time()

    # Reset per-minute window
    if now - WINDOW_START_TS >= 60:
        WINDOW_START_TS = now
        CALLS_THIS_MINUTE = 0

    # Enforce 5 calls per minute
    if CALLS_THIS_MINUTE >= MAX_CALLS_PER_MIN:
        sleep_for = 60 - (now - WINDOW_START_TS)
        if sleep_for > 0:
            time.sleep(sleep_for)
        WINDOW_START_TS = time.time()
        CALLS_THIS_MINUTE = 0

    CALLS_THIS_MINUTE += 1
    LAST_REQUEST_TS = time.time()

    url = "https://www.alphavantage.co/query"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # Alpha Vantage throttle/error messages come back as HTTP 200 JSON
    if "Information" in data or "Note" in data:
        msg = data.get("Information") or data.get("Note")
        raise RuntimeError(f"Alpha Vantage throttled: {msg}")

    if "Error Message" in data:
        raise RuntimeError(f"Alpha Vantage error: {data['Error Message']}")

    return data



