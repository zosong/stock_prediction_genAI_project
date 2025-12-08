from typing import List, Dict

from alpha_vantage_helper import alpha_vantage_get, API_KEY  # low-level HTTP helper


def get_news_for_symbol(symbol: str, limit: int = 50) -> List[Dict]:
    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": symbol,
        "limit": limit,
        "apikey": API_KEY,
    }

    data = alpha_vantage_get(params)
    return data.get("feed", [])


if __name__ == "__main__":
    items = get_news_for_symbol("AAPL", limit=5)
    print(f"Got {len(items)} news items")
    for item in items:
        print(item.get("time_published"), "-", item.get("title"))