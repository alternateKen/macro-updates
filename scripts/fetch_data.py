#!/usr/bin/env python3
"""Fetch free market data and write docs/data.json. Standard library only."""
import csv, io, json, sys, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET

UA = {"User-Agent": "Mozilla/5.0 (macro-dashboard)"}

# (symbol, label) grouped by dashboard section
YAHOO = {
    "Futures": [("ES=F", "S&P 500 fut"), ("NQ=F", "Nasdaq 100 fut"), ("YM=F", "Dow fut"), ("RTY=F", "Russell 2000 fut")],
    "US Indices": [("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq Comp"), ("^DJI", "Dow Jones"), ("^RUT", "Russell 2000"), ("^VIX", "VIX")],
    "Global Indices": [("^FTSE", "FTSE 100"), ("^STOXX50E", "Euro Stoxx 50"), ("^GDAXI", "DAX"), ("^N225", "Nikkei 225"), ("^HSI", "Hang Seng"), ("000001.SS", "Shanghai Comp")],
    "Sectors (SPDR ETFs)": [("XLK", "Technology"), ("XLC", "Comm Services"), ("XLY", "Cons Discretionary"), ("XLF", "Financials"),
                            ("XLI", "Industrials"), ("XLV", "Health Care"), ("XLP", "Cons Staples"), ("XLE", "Energy"),
                            ("XLB", "Materials"), ("XLU", "Utilities"), ("XLRE", "Real Estate")],
    "Rates (Yahoo, intraday)": [("^IRX", "US 13-wk"), ("^FVX", "US 5y"), ("^TNX", "US 10y"), ("^TYX", "US 30y")],
    "Energy": [("CL=F", "WTI crude"), ("BZ=F", "Brent crude"), ("NG=F", "Natural gas"), ("RB=F", "Gasoline")],
    "Metals": [("GC=F", "Gold"), ("SI=F", "Silver"), ("HG=F", "Copper"), ("PL=F", "Platinum")],
    "Agriculture": [("ZC=F", "Corn"), ("ZW=F", "Wheat"), ("ZS=F", "Soybeans")],
    "Other commodities": [("CC=F", "Cocoa"), ("KC=F", "Coffee"), ("SB=F", "Sugar"), ("CT=F", "Cotton")],
    "FX": [("DX-Y.NYB", "US Dollar Index"), ("EURUSD=X", "EUR/USD"), ("USDJPY=X", "USD/JPY"), ("GBPUSD=X", "GBP/USD"),
           ("USDCNY=X", "USD/CNY"), ("AUDUSD=X", "AUD/USD"), ("USDCAD=X", "USD/CAD"), ("USDMXN=X", "USD/MXN"), ("USDCHF=X", "USD/CHF")],
    "Volatility & Credit ETFs": [("^VIX3M", "VIX 3-month"), ("^MOVE", "MOVE (bond vol)"), ("HYG", "High-yield bonds"), ("LQD", "IG corporate bonds"),
                                 ("TLT", "20y+ Treasuries"), ("IEF", "7-10y Treasuries"), ("SHY", "1-3y Treasuries"), ("EMB", "EM bonds USD")],
    "Mega-caps & Themes": [("AAPL", "Apple"), ("MSFT", "Microsoft"), ("NVDA", "Nvidia"), ("AMZN", "Amazon"), ("GOOGL", "Alphabet"),
                           ("META", "Meta"), ("TSLA", "Tesla"), ("RSP", "S&P equal-weight"), ("SMH", "Semiconductors"), ("KRE", "Regional banks")],
    "Crypto": [("BTC-USD", "Bitcoin"), ("ETH-USD", "Ethereum")],
}

# FRED series for the Treasury curve (percent), plus spreads / credit
CURVE = [("DGS1MO", "1M"), ("DGS3MO", "3M"), ("DGS6MO", "6M"), ("DGS1", "1Y"), ("DGS2", "2Y"), ("DGS3", "3Y"),
         ("DGS5", "5Y"), ("DGS7", "7Y"), ("DGS10", "10Y"), ("DGS20", "20Y"), ("DGS30", "30Y")]
OTHER_FRED = [("T10Y2Y", "10y-2y spread"), ("T10Y3M", "10y-3m spread"), ("DFII10", "10y real yield"),
              ("T10YIE", "10y breakeven"), ("DFF", "Fed funds effective"), ("BAMLH0A0HYM2", "High-yield spread (OAS)"),
              ("BAMLC0A0CM", "IG corporate spread (OAS)")]

NEWS = [
    ("CNBC Markets", "https://www.cnbc.com/id/20910258/device/rss/rss.html"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_marketpulse"),
    ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
]


def get(url, tries=2, timeout=10):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1 + i)
    raise last


def yahoo(symbol):
    q = urllib.parse.quote(symbol)
    raw = None
    for host in ("query1", "query2"):
        try:
            raw = get(f"https://{host}.finance.yahoo.com/v8/finance/chart/{q}?range=1y&interval=1d&includePrePost=false", tries=1)
            break
        except Exception as e:  # noqa: BLE001
            err = e
    if raw is None:
        raise err
    res = json.loads(raw)["chart"]["result"][0]
    meta = res["meta"]
    ts = res["timestamp"]
    closes = res["indicators"]["quote"][0]["close"]
    pts = [(t, c) for t, c in zip(ts, closes) if c is not None]
    last = meta.get("regularMarketPrice", pts[-1][1])
    # previous close = last completed daily close before the latest bar
    # the last daily bar is the latest session (live or final), so the one before it is the prior close
    prev = pts[-2][1] if len(pts) >= 2 else meta.get("chartPreviousClose")
    series = [c for _, c in pts]
    if series:
        series[-1] = last

    def ago(n):
        return series[-1 - n] if len(series) > n else None

    def pct(a, b):
        return None if a is None or not b else (a / b - 1) * 100

    year = datetime.now(timezone.utc).year
    ytd_base = next((c for t, c in pts if datetime.fromtimestamp(t, timezone.utc).year == year), None)
    prior = [c for t, c in pts if datetime.fromtimestamp(t, timezone.utc).year < year]
    if prior:
        ytd_base = prior[-1]
    return {
        "symbol": symbol, "last": last, "prev": prev,
        "chg": None if prev is None else last - prev,
        "pct": pct(last, prev), "w1": pct(last, ago(5)), "m1": pct(last, ago(21)),
        "ytd": pct(last, ytd_base),
        "hi52": max(series), "lo52": min(series),
        "spark": [round(x, 4) for x in series[-45:]],
        "asof": datetime.fromtimestamp(meta.get("regularMarketTime", pts[-1][0]), timezone.utc).isoformat(),
    }


def fred(series_id, start_days=420):
    start = (datetime.now(timezone.utc) - timedelta(days=start_days)).strftime("%Y-%m-%d")
    raw = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}").decode()
    rows = []
    for r in list(csv.reader(io.StringIO(raw)))[1:]:
        if len(r) == 2 and r[1] not in (".", ""):
            rows.append((r[0], float(r[1])))
    return rows


def value_on_or_before(rows, days_back):
    target = (datetime.strptime(rows[-1][0], "%Y-%m-%d") - timedelta(days=days_back)).strftime("%Y-%m-%d")
    cand = [v for d, v in rows if d <= target]
    return cand[-1] if cand else None


def news(name, url, limit=8):
    root = ET.fromstring(get(url))
    items = []
    for it in root.iter("item"):
        items.append({"source": name, "title": (it.findtext("title") or "").strip(),
                      "link": (it.findtext("link") or "").strip(), "time": (it.findtext("pubDate") or "").strip()})
        if len(items) >= limit:
            break
    return items


def main():
    out = {"generated": datetime.now(timezone.utc).isoformat(), "sections": {}, "curve": [], "fred": [], "news": [], "errors": []}

    def safe(fn, *a):
        try:
            return fn(*a), None
        except Exception as e:  # noqa: BLE001
            return None, f"{a[0]}: {e}"

    with ThreadPoolExecutor(max_workers=8) as ex:
        yfut = {sec: [(label, ex.submit(safe, yahoo, sym)) for sym, label in items] for sec, items in YAHOO.items()}
        cfut = [(sid, label, ex.submit(safe, fred, sid)) for sid, label in CURVE]
        ffut = [(sid, label, ex.submit(safe, fred, sid)) for sid, label in OTHER_FRED]
        nfut = [ex.submit(safe, news, name, url) for name, url in NEWS]

        for sec, lst in yfut.items():
            rows = []
            for label, fu in lst:
                d, err = fu.result()
                if err:
                    out["errors"].append(err)
                else:
                    d["label"] = label
                    rows.append(d)
            out["sections"][sec] = rows
        for sid, label, fu in cfut:
            r, err = fu.result()
            if err:
                out["errors"].append(err)
            else:
                out["curve"].append({"id": sid, "label": label, "date": r[-1][0], "now": r[-1][1],
                                     "w1": value_on_or_before(r, 7), "m1": value_on_or_before(r, 30),
                                     "y1": value_on_or_before(r, 365)})
        for sid, label, fu in ffut:
            r, err = fu.result()
            if err:
                out["errors"].append(err)
            else:
                out["fred"].append({"id": sid, "label": label, "date": r[-1][0], "now": r[-1][1],
                                    "d1": r[-1][1] - r[-2][1] if len(r) > 1 else None,
                                    "w1": value_on_or_before(r, 7), "m1": value_on_or_before(r, 30),
                                    "spark": [v for _, v in r[-60:]]})
        for fu in nfut:
            r, err = fu.result()
            if err:
                out["errors"].append("news " + err)
            else:
                out["news"].extend(r)
    total = sum(len(v) for v in out["sections"].values())
    if total == 0 and not out["curve"]:
        print("No data fetched at all; keeping previous data.json", file=sys.stderr)
        for e in out["errors"][:10]:
            print(e, file=sys.stderr)
        sys.exit(1)
    path = sys.argv[1] if len(sys.argv) > 1 else "docs/data.json"
    with open(path, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"wrote {path}: {total} quotes, {len(out['curve'])} curve pts, {len(out['news'])} headlines, {len(out['errors'])} errors")


if __name__ == "__main__":
    main()
