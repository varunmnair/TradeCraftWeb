import requests
import time
import json
from datetime import datetime, timezone

BASE = "https://www.nseindia.com"

# Common browser-like headers (important for NSE endpoints)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}


def make_nse_session() -> requests.Session:
    """
    Creates an NSE session by first hitting the homepage to get cookies.
    NSE endpoints often return 401/403 without these cookies/headers.
    """
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)

    # Step 1: get cookies from homepage
    r = s.get(BASE, timeout=15)
    r.raise_for_status()

    # Small delay helps avoid throttling
    time.sleep(0.5)
    return s


def get_equity_quote(session: requests.Session, symbol: str) -> dict:
    """
    Fetch live equity quote JSON.
    Endpoint commonly used by unofficial wrappers.
    """
    url = f"{BASE}/api/quote-equity"
    params = {"symbol": symbol.upper()}
    r = session.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def get_equity_candles(session: requests.Session, symbol: str) -> dict:
    """
    Fetch intraday chart candles for an equity.
    NSE commonly serves OHLCV-like series via chart endpoint.

    Returned structure may vary slightly; usually includes arrays under keys like:
    - 'grapthData' / 'graphData' / 'data'
    where each item is [timestamp(ms), price] or OHLC points depending on endpoint variant.
    """
    url = f"{BASE}/api/chart-databyindex"
    # For equities, NSE often uses "symbols" param like: "TCS" or "SBIN"
    # Some variants accept "index" or "symbol". We'll try the commonly working param.
    params = {"index": symbol.upper()}  # in practice, works for many equities/indices
    r = session.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def pretty_print_quote(quote: dict):
    """
    Extract common fields from /api/quote-equity response.
    """
    info = quote.get("info", {})
    price = quote.get("priceInfo", {})
    meta = quote.get("metadata", {})

    print("=== QUOTE ===")
    print("Symbol:", info.get("symbol"))
    print("Company:", info.get("companyName"))
    print("Last Price:", price.get("lastPrice"))
    print("Change:", price.get("change"), "(", price.get("pChange"), "% )")
    print("Day High/Low:", price.get("intraDayHighLow", {}))
    print("Prev Close:", price.get("previousClose"))
    print("As of:", meta.get("lastUpdateTime"))


def normalize_chart_points(chart_json: dict):
    """
    Best-effort normalization for common NSE chart responses.
    Some NSE chart endpoints return:
      - graphData: [[ts_ms, price], ...]
    Others might return OHLC arrays.

    This function returns a list of dict points for easy use.
    """
    # Try a few common keys seen in community wrappers
    candidates = ["graphData", "grapthData", "data", "candles", "chartData"]
    series = None
    for k in candidates:
        if k in chart_json and isinstance(chart_json[k], list):
            series = chart_json[k]
            break

    if not series:
        return []

    points = []
    for item in series:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            ts_ms = item[0]
            val = item[1]
            ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            points.append({"time_utc": ts.isoformat(), "value": val})
        elif isinstance(item, dict):
            points.append(item)
        else:
            # unknown shape
            continue
    return points


def main():
    symbol = "TCS"  # change to e.g. RELIANCE, INFY, SBIN, etc.

    s = make_nse_session()

    # 1) Live quote
    quote = get_equity_quote(s, symbol)
    pretty_print_quote(quote)

    # 2) Chart (candle-like) data
    chart = get_equity_candles(s, symbol)
    points = normalize_chart_points(chart)

    print("\n=== CHART POINTS (first 10) ===")
    for p in points[:10]:
        print(p)

    # Save raw responses for inspection
    with open(f"{symbol}_quote.json", "w", encoding="utf-8") as f:
        json.dump(quote, f, indent=2)
    with open(f"{symbol}_chart.json", "w", encoding="utf-8") as f:
        json.dump(chart, f, indent=2)

    print(f"\nSaved: {symbol}_quote.json and {symbol}_chart.json")


if __name__ == "__main__":
    main()