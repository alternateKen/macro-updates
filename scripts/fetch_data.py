#!/usr/bin/env python3
"""Fetch free market data and write docs/data.json. Standard library only."""
import csv, io, json, os, re, sys, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "text/csv,application/json,text/html;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}

# (symbol, label) grouped by dashboard section
YAHOO = {
    "Futures": [("ES=F", "S&P 500 fut"), ("NQ=F", "Nasdaq 100 fut"), ("YM=F", "Dow fut"), ("RTY=F", "Russell 2000 fut")],
    "US Indices": [("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq Comp"), ("^DJI", "Dow Jones"), ("^RUT", "Russell 2000"), ("^VIX", "VIX")],
    "Europe Indices": [("^FTSE", "FTSE 100"), ("^STOXX50E", "Euro Stoxx 50"), ("^GDAXI", "DAX"), ("^FCHI", "CAC 40")],
    # Asia-Pacific: every key starting "Asia: " is shown together on the page, grouped by market.
    # These have all closed by the 6:15am New York refresh, so the figures are the final session.
    "Asia: Japan": [("^N225", "Nikkei 225"), ("1306.T", "TOPIX (NEXT FUNDS ETF)")],
    "Asia: Korea": [("^KS11", "KOSPI"), ("^KQ11", "KOSDAQ")],
    "Asia: Taiwan": [("^TWII", "TAIEX")],
    "Asia: China H-shares": [("^HSI", "Hang Seng"), ("^HSCE", "HS China Enterprises (H-shares)"), ("3032.HK", "Hang Seng Tech (ETF 3032)")],
    "Asia: China A-shares": [("000001.SS", "Shanghai Composite"), ("399001.SZ", "Shenzhen Component"), ("000300.SS", "CSI 300"), ("399006.SZ", "ChiNext")],
    "Asia: Singapore": [("^STI", "Straits Times")],
    "Asia: Southeast Asia": [("^JKSE", "Indonesia (Jakarta Comp)"), ("^KLSE", "Malaysia (KLCI)"), ("^SET.BK", "Thailand (SET)"),
                             ("EPHE", "Philippines (iShares ETF)"), ("VNM", "Vietnam (VanEck ETF)")],
    "Asia: Australia": [("^AXJO", "ASX 200"), ("^AORD", "All Ordinaries")],
    "Asia: India": [("^NSEI", "Nifty 50"), ("^BSESN", "Sensex"), ("^NSEBANK", "Nifty Bank")],
    "Asia FX": [("KRW=X", "USD/KRW"), ("TWD=X", "USD/TWD"), ("CNH=X", "USD/CNH"), ("INR=X", "USD/INR"), ("SGD=X", "USD/SGD"),
                ("IDR=X", "USD/IDR"), ("THB=X", "USD/THB"), ("MYR=X", "USD/MYR"), ("PHP=X", "USD/PHP")],
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

# Treasury par-yield columns (normalised, see treasury()) and display labels
CURVE = [("1mo", "1M"), ("3mo", "3M"), ("6mo", "6M"), ("1yr", "1Y"), ("2yr", "2Y"), ("3yr", "3Y"),
         ("5yr", "5Y"), ("7yr", "7Y"), ("10yr", "10Y"), ("20yr", "20Y"), ("30yr", "30Y")]
# Credit spreads are only published by FRED, which times out from GitHub's servers. Best effort:
# one 15-second try, page copes if missing (HYG / LQD in the Volatility & Credit table are the substitute).
OAS = [("BAMLH0A0HYM2", "High-yield spread (OAS)"), ("BAMLC0A0CM", "IG corporate spread (OAS)")]

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


def rsi14(closes):
    """Wilder RSI(14), the same smoothing TradingView uses by default."""
    if len(closes) < 15:
        return None
    gains, losses = [], []
    for a, b in zip(closes, closes[1:]):
        d = b - a
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag, al = sum(gains[:14]) / 14, sum(losses[:14]) / 14
    for g, l in zip(gains[14:], losses[14:]):
        ag, al = (ag * 13 + g) / 14, (al * 13 + l) / 14
    return 100.0 if al == 0 else 100.0 - 100.0 / (1 + ag / al)


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
    vols_raw = res["indicators"]["quote"][0].get("volume") or []
    vols = [v for c, v in zip(closes, vols_raw) if c is not None and v is not None]
    base = sum(vols[-21:-1]) / 20 if len(vols) >= 21 else 0
    vol_x = vols[-1] / base if base else None

    def ma(n):
        return sum(series[-n:]) / n if len(series) >= n else None

    return {
        "ma50": ma(50), "ma200": ma(200), "vol_x": vol_x, "rsi": rsi14(series),
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
    raw = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}", tries=1, timeout=15).decode()
    rows = []
    for r in list(csv.reader(io.StringIO(raw)))[1:]:
        if len(r) == 2 and r[1] not in (".", ""):
            rows.append((r[0], float(r[1])))
    return rows


def value_on_or_before(rows, days_back):
    target = (datetime.strptime(rows[-1][0], "%Y-%m-%d") - timedelta(days=days_back)).strftime("%Y-%m-%d")
    cand = [v for d, v in rows if d <= target]
    return cand[-1] if cand else None



def _num(x):
    try:
        return float(str(x).strip())
    except Exception:  # noqa: BLE001
        return None


def treasury(kind, years):
    """US Treasury daily par yield / real yield curve. Returns {normalised column: [(iso date, value)]} ascending."""
    cols = {}
    for y in years:
        url = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/"
               f"{y}/all?type={kind}&field_tdr_date_value={y}&page&_format=csv")
        raw = get(url, timeout=20).decode("utf-8-sig")
        for row in csv.DictReader(io.StringIO(raw)):
            try:
                d = datetime.strptime(row["Date"].strip(), "%m/%d/%Y").strftime("%Y-%m-%d")
            except Exception:  # noqa: BLE001
                continue
            for k, v in row.items():
                if k == "Date":
                    continue
                n = _num(v)
                if n is not None:
                    cols.setdefault(k.lower().replace(" ", ""), []).append((d, n))
    return {k: sorted(v) for k, v in cols.items()}


def effr():
    raw = json.loads(get("https://markets.newyorkfed.org/api/rates/unsecured/effr/last/70.json"))
    return sorted((r["effectiveDate"], float(r["percentRate"])) for r in raw["refRates"])


def _parse_mof(raw):
    rows = list(csv.reader(io.StringIO(raw)))
    hi = next(i for i, r in enumerate(rows) if r and r[0].strip().lower() == "date")
    head = [h.strip() for h in rows[hi]]
    cols = {h: [] for h in head[1:]}
    for r in rows[hi + 1:]:
        if not r or not r[0].strip():
            continue
        try:
            d = datetime.strptime(r[0].strip(), "%Y/%m/%d").strftime("%Y-%m-%d")
        except Exception:  # noqa: BLE001
            continue
        for h, v in zip(head[1:], r[1:]):
            n = _num(v)
            if n is not None:
                cols[h].append((d, n))
    return cols


def jgb():
    """Japan MOF JGB yields, merged from every MOF file that loads (the full-history file is only
    updated monthly, the current file has the latest days). Returns {tenor: [(iso date, value)]}."""
    base = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/"
    merged, tried, ok = {}, [], []
    for name in ("historical/jgbcme_all.csv", "jgbcme.csv", "jgbcm.csv", "jgbcm_all.csv"):
        try:
            raw = get(base + name, tries=1, timeout=25).decode("utf-8-sig", "ignore")
            cols = _parse_mof(raw)
        except Exception as e:  # noqa: BLE001
            tried.append(f"{name}: {e}")
            continue
        ok.append(name)
        for tenor, rows in cols.items():
            merged.setdefault(tenor, {}).update(dict(rows))   # later (more current) files win
    if not merged:
        raise RuntimeError("; ".join(tried))
    print("JGB files used:", ", ".join(ok), "| failed:", len(tried))
    return {t: sorted(d.items())[-400:] for t, d in merged.items() if d}


def derive(a, b, fn):
    """Combine two (date, value) series on matching dates."""
    bm = dict(b)
    return [(d, fn(v, bm[d])) for d, v in a if d in bm]


def entry(sid, label, rows):
    return {"id": sid, "label": label, "date": rows[-1][0], "now": rows[-1][1],
            "d1": rows[-1][1] - rows[-2][1] if len(rows) > 1 else None,
            "w1": value_on_or_before(rows, 7), "m1": value_on_or_before(rows, 30),
            "spark": [v for _, v in rows[-60:]]}


def news(name, url, limit=8):
    root = ET.fromstring(get(url))
    items = []
    for it in root.iter("item"):
        items.append({"source": name, "title": (it.findtext("title") or "").strip(),
                      "link": (it.findtext("link") or "").strip(), "time": (it.findtext("pubDate") or "").strip()})
        if len(items) >= limit:
            break
    return items


# ---------------- Top movers (Dow, S&P 500, Nasdaq-100, China H/A, Taiwan, Korea) ----------------
# Bloomberg country suffix -> Yahoo suffixes to try in order (Taiwan: main board .TW or OTC board .TWO;
# Korea: KOSPI .KS or KOSDAQ .KQ)
BBG_SUFFIX = {"TT": [".TW", ".TWO"], "KS": [".KS", ".KQ"], "JP": [".T"], "HK": [".HK"], "NO": [".OL"], "LN": [".L"]}
US_SUFFIX = ("US", "UN", "UQ", "UW", "UA")
DOW_FALLBACK = ["AAPL", "AMGN", "AMZN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "GS", "HD", "HON", "IBM", "JNJ",
                "JPM", "KO", "MCD", "MMM", "MRK", "MSFT", "NKE", "NVDA", "PG", "SHW", "TRV", "UNH", "V", "VZ", "WMT"]


def yahoo_candidates(code):
    """'SHOP US' -> ['SHOP'];  '2330 TT' -> ['2330.TW', '2330.TWO'];  '0700 HK' -> ['0700.HK'];  '600519 CH' -> ['600519.SS']"""
    code = code.strip().upper()
    m = re.match(r"^(.+?)\s+([A-Z]{2})$", code)
    if not m:
        return [code.replace("/", "-").replace(" ", "")]
    base, cc = m.group(1).replace(" ", "").replace("/", "-"), m.group(2)
    if cc in US_SUFFIX:
        return [base]
    if cc in ("CH", "C1", "C2"):   # mainland China: 6xxxxx = Shanghai, otherwise Shenzhen
        return [base + (".SS" if base.startswith("6") else ".SZ")]
    if cc == "HK":
        base = base.lstrip("0").zfill(4)
    return [base + x for x in BBG_SUFFIX.get(cc, [""])]


class TableCollector(HTMLParser):
    """Collects every HTML table on a page as a list of rows (nested tables handled). Wikipedia's member
    tables have no reliable id, so the right one is picked afterwards by looking at its header and size."""
    def __init__(self):
        super().__init__()
        self.stack, self.tables = [], []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.stack.append({"rows": [], "row": None, "cell": None})
        elif self.stack:
            t = self.stack[-1]
            if tag == "tr":
                t["row"] = []
            elif tag in ("td", "th") and t["row"] is not None:
                t["cell"] = []
            elif tag == "br" and t["cell"] is not None:
                t["cell"].append(" ")

    def handle_endtag(self, tag):
        if not self.stack:
            return
        t = self.stack[-1]
        if tag == "table":
            self.tables.append(self.stack.pop()["rows"])
        elif tag in ("td", "th") and t["cell"] is not None and t["row"] is not None:
            t["row"].append(" ".join("".join(t["cell"]).split()))
            t["cell"] = None
        elif tag == "tr" and t["row"] is not None:
            if t["row"]:
                t["rows"].append(t["row"])
            t["row"] = None

    def handle_data(self, d):
        if self.stack and self.stack[-1]["cell"] is not None:
            self.stack[-1]["cell"].append(d)


def _clean(x):
    return re.sub(r"\[.*?\]", "", x).strip()


def wikipedia_members(url, min_rows=20):
    """-> [(yahoo symbol, company name)]: the largest table on the page that has a Symbol / Ticker column."""
    p = TableCollector()
    p.feed(get(url, tries=2, timeout=25).decode("utf-8", "ignore"))
    best = []
    for rows in p.tables:
        hi = next((i for i, r in enumerate(rows[:4]) if any(_clean(c).lower() in ("symbol", "ticker", "ticker symbol") for c in r)), None)
        if hi is None:
            continue
        head = [_clean(c).lower() for c in rows[hi]]
        si = next(i for i, h in enumerate(head) if h in ("symbol", "ticker", "ticker symbol"))
        ni = next((i for i, h in enumerate(head) if h in ("security", "company", "company name", "name")), None)
        seen, members = set(), []
        for r in rows[hi + 1:]:
            if len(r) <= si:
                continue
            sym = _clean(r[si]).split(":")[-1].strip().upper().replace(".", "-")
            if re.match(r"^[A-Z][A-Z0-9-]{0,6}$", sym) and sym not in seen:
                seen.add(sym)
                members.append((sym, _clean(r[ni]) if ni is not None and len(r) > ni else sym))
        if len(members) > len(best):
            best = members
    if len(best) < min_rows:
        raise ValueError(f"members table not found on page (best candidate had {len(best)} rows)")
    return best


def read_movers(path):
    """movers.txt -> [{"name", "wiki", "index", "weights", "weighting", "items": [(candidates, name, display)]}]"""
    unis, cur = [], None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip() if line.strip().startswith("@") else line.split("#")[0].strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                cur = {"name": line[1:-1].strip(), "wiki": None, "index": None, "weights": None, "weighting": "cap", "items": []}
                unis.append(cur)
            elif cur is None:
                continue
            elif line.startswith("@"):
                key, _, val = line[1:].partition(" ")
                key, val = key.lower(), val.strip()
                if key == "wikipedia":
                    cur["wiki"] = val
                elif key == "index":
                    cur["index"] = val
                elif key == "weights":
                    cur["weights"] = val
                elif key == "weighting":
                    cur["weighting"] = val.lower()
            else:
                code, _, name = line.partition("|")
                if code.strip():
                    cur["items"].append((yahoo_candidates(code), name.strip() or code.strip(), code.strip().upper().replace(" US", "")))
    return unis


def read_weights(path):
    """Bloomberg MEMB export (csv / tab / semicolon text) -> [(code, name, display, weight %)].
    Needs a ticker column and a weight column; headers like 'Ticker', 'Name', 'Index Weight', '% Wgt' are recognised."""
    raw = open(path, encoding="utf-8-sig", errors="ignore").read()
    delim = "\t" if raw.count("\t") > raw.count(",") else (";" if raw.count(";") > raw.count(",") else ",")
    rows = [r for r in csv.reader(io.StringIO(raw), delimiter=delim) if any(c.strip() for c in r)]
    hi = next((i for i, r in enumerate(rows[:10]) if any(re.search(r"weight|wgt", c, re.I) for c in r)), None)
    tcol, ncol, wcol = 0, None, None
    if hi is not None:
        for j, c in enumerate(rows[hi]):
            if wcol is None and re.search(r"weight|wgt", c, re.I):
                wcol = j
            elif ncol is None and re.search(r"^name$|security name|company", c, re.I):
                ncol = j
            elif re.search(r"ticker|member|security$", c, re.I) and tcol == 0:
                tcol = j
    out = []
    for r in rows[(hi + 1) if hi is not None else 0:]:
        if len(r) <= tcol:
            continue
        code = re.sub(r"\s+(EQUITY|INDEX)$", "", r[tcol].strip(), flags=re.I)
        wv = None
        for j in ([wcol] if wcol is not None else range(len(r) - 1, 0, -1)):
            if j is not None and j < len(r):
                try:
                    wv = float(r[j].replace("%", "").replace(",", "").strip())
                    break
                except ValueError:
                    continue
        if code and wv is not None and wv > 0:
            name = r[ncol].strip() if ncol is not None and len(r) > ncol and r[ncol].strip() else code
            out.append((code, name, code.upper().replace(" US", ""), wv))
    return out


def quick_quote(cands, deadline):
    """Last price and day % change from a small 5-day Yahoo request. Tries each candidate symbol in turn."""
    last_err = None
    for sym in cands:
        try:
            if time.time() > deadline:
                raise TimeoutError("movers time budget used")
            raw = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range=5d&interval=1d", tries=2, timeout=10)
            res = json.loads(raw)["chart"]["result"][0]
            closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
            if len(closes) < 2:
                raise ValueError("no previous close")
            last = res["meta"].get("regularMarketPrice") or closes[-1]
            return {"ysym": sym, "last": last, "pct": (last / closes[-2] - 1) * 100}
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise last_err


def yahoo_marketcaps(symbols, deadline):
    """{yahoo symbol: market cap in local currency} from Yahoo's quote endpoint (needs a cookie + crumb)."""
    import http.cookiejar
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    op.addheaders = list(UA.items())
    try:
        op.open("https://fc.yahoo.com", timeout=10).read()   # answers 404 but sets the cookie we need
    except Exception:  # noqa: BLE001
        pass
    crumb = op.open("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=10).read().decode().strip()
    if not crumb or len(crumb) > 40 or "<" in crumb:
        raise ValueError("no Yahoo crumb")
    syms = list(symbols)

    def batch(b):
        if time.time() > deadline:
            return {}
        try:
            url = "https://query1.finance.yahoo.com/v7/finance/quote?symbols=" + urllib.parse.quote(",".join(b)) + "&crumb=" + urllib.parse.quote(crumb)
            data = json.loads(op.open(url, timeout=20).read())
            return {r["symbol"]: float(r["marketCap"]) for r in data["quoteResponse"]["result"] if r.get("marketCap")}
        except Exception:  # noqa: BLE001
            return {}
    caps = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for res in ex.map(batch, [syms[i:i + 40] for i in range(0, len(syms), 40)]):
            caps.update(res)
    if len(caps) < len(syms) * 0.5:
        raise ValueError(f"only {len(caps)} of {len(syms)} market caps returned")
    return caps


DUAL_CLASS = {"GOOGL": "GOOG", "GOOG": "GOOGL", "FOXA": "FOX", "FOX": "FOXA", "NWSA": "NWS", "NWS": "NWSA"}
DOW_DIVISOR_FALLBACK = 0.1627   # used only if the live divisor cannot be derived (all 30 prices and the index level)


def rank_universe(u, rows, index_q, caps):
    """Adds weight w (% of the index) and contribution c to every row; returns (method, basis, unit, summary).
    c is the stock's contribution to the index move: bp of the index (weight % x move %), or index points for the Dow."""
    syms = {r["symbol"] for r in rows}
    if u["bbg"]:
        for r in rows:
            r["w"] = u["bbg"].get(r["symbol"])
            r["c"] = None if r["w"] is None else r["w"] * r["pct"]
        method, basis, unit = "Bloomberg index weights", "index", "bp"
    elif u["weighting"] == "price":   # Dow: price-weighted, so a $1 move counts the same in any member
        tot = sum(r["last"] for r in rows)
        div = tot / index_q["last"] if index_q and len(rows) == len(u["items"]) and index_q["last"] else DOW_DIVISOR_FALLBACK
        for r in rows:
            r["w"] = r["last"] / tot * 100
            r["c"] = (r["last"] - r["last"] / (1 + r["pct"] / 100)) / div
        method, basis, unit = "Price-weighted (Dow divisor)", "index", "pts"
    elif caps and sum(1 for r in rows if r["ysym"] in caps) >= 0.8 * len(rows):
        capv = {}
        for r in rows:
            c = caps.get(r["ysym"])
            if c and r["symbol"] in DUAL_CLASS and DUAL_CLASS[r["symbol"]] in syms:
                c = c / 2   # Yahoo reports the whole company's cap for each share class
            capv[r["symbol"]] = c
        tot = sum(v for v in capv.values() if v)
        for r in rows:
            r["w"] = capv[r["symbol"]] / tot * 100 if capv[r["symbol"]] else None
            r["c"] = None if r["w"] is None else r["w"] * r["pct"]
        method, basis, unit = "Market-cap weighted (Yahoo)", ("index" if u["wiki"] else "list"), "bp"
    else:
        for r in rows:
            r["w"], r["c"] = None, r["pct"]
        method, basis, unit = "Unweighted % move (no weights available)", "none", "%"
    summ = {}
    ranked = [r for r in rows if r["c"] is not None]
    if unit == "bp" and basis == "index":
        summ["explained"] = sum(r["c"] for r in ranked)
        if u["bbg"]:
            summ["covered"] = sum(r["w"] for r in ranked)
    elif unit == "bp" and basis == "list":
        summ["ret"] = sum(r["c"] for r in ranked) / 100
    elif unit == "pts":
        summ["explained"] = sum(r["c"] for r in ranked)
    return method, basis, unit, summ


def build_movers(path, errors, budget_seconds=240, top=5, caps_fn=yahoo_marketcaps):
    deadline = time.time() + budget_seconds
    root = os.path.dirname(os.path.abspath(path))
    unis = read_movers(path)
    for u in unis:
        u["bbg"] = {}
        wp = os.path.join(root, u["weights"]) if u["weights"] else None
        if wp and os.path.exists(wp):   # 1. Bloomberg index weights supplied by the user: exact, and also set the member list
            try:
                ws = read_weights(wp)
                if len(ws) >= 5:
                    u["items"] = [(yahoo_candidates(code), name, disp) for code, name, disp, w in ws]
                    u["bbg"] = {disp: w for code, name, disp, w in ws}
                    continue
                errors.append(f"movers {u['name']}: {u['weights']} has fewer than 5 usable rows, ignored")
            except Exception as e:  # noqa: BLE001
                errors.append(f"movers {u['name']}: {u['weights']} unreadable ({e})")
        if u["wiki"]:   # 2. live index members from Wikipedia
            try:
                u["items"] = [([s], n, s) for s, n in wikipedia_members(u["wiki"])]
            except Exception as e:  # noqa: BLE001
                errors.append(f"movers {u['name']}: Wikipedia list failed ({e})")
                if u["name"].startswith("Dow"):
                    u["items"] = [([s], s, s) for s in DOW_FALLBACK]
                    errors.append("movers Dow 30: used built-in fallback list")
    cache, jobs, idx = {}, [], {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        for u in unis:
            if u["index"] and u["index"] not in cache:
                cache[u["index"]] = ex.submit(quick_quote, [u["index"]], deadline)
            for cands, name, disp in u["items"]:
                key = tuple(cands)
                if key not in cache:   # a stock in several universes is fetched once
                    cache[key] = ex.submit(quick_quote, cands, deadline)
                jobs.append((u["name"], name, disp, cache[key]))
        by = {u["name"]: [] for u in unis}
        failed = {u["name"]: [] for u in unis}
        for uname, name, disp, fu in jobs:
            try:
                q = fu.result()
                by[uname].append({"symbol": disp, "label": name, "pct": q["pct"], "last": q["last"], "ysym": q["ysym"]})
            except Exception:  # noqa: BLE001
                failed[uname].append(disp)
        for u in unis:
            if u["index"]:
                try:
                    idx[u["name"]] = cache[u["index"]].result()
                except Exception as e:  # noqa: BLE001
                    errors.append(f"movers {u['name']}: index {u['index']} unavailable ({e})")
    need = {r["ysym"] for u in unis if not u["bbg"] and u["weighting"] != "price" for r in by[u["name"]]}
    caps = {}
    if need:   # 3. market caps (Yahoo) for universes without Bloomberg weights
        try:
            caps = caps_fn(sorted(need), deadline)
        except Exception as e:  # noqa: BLE001
            errors.append(f"movers: market-cap data unavailable ({e}); those cards fall back to unweighted % move")
    out = {}
    for u in unis:
        rows, total = by[u["name"]], len(u["items"])
        if failed[u["name"]]:
            errors.append(f"movers {u['name']}: {len(rows)}/{total} loaded; no data for {', '.join(failed[u['name']][:8])}"
                          + (" ..." if len(failed[u["name"]]) > 8 else ""))
        if len(rows) < max(5, total // 2):
            continue   # too little data to call anything a top mover
        method, basis, unit, summ = rank_universe(u, rows, idx.get(u["name"]), caps)
        ranked = sorted((r for r in rows if r["c"] is not None), key=lambda r: r["c"], reverse=True)
        keep = lambda r: {k: r[k] for k in ("symbol", "label", "pct", "w", "c")}   # noqa: E731
        iq = idx.get(u["name"])
        out[u["name"]] = {"n": total, "loaded": len(rows), "adv": sum(1 for r in rows if r["pct"] > 0), "dec": sum(1 for r in rows if r["pct"] < 0),
                          "method": method, "basis": basis, "unit": unit, "index": {"symbol": u["index"], "pct": iq["pct"], "last": iq["last"]} if iq else None,
                          **summ, "gainers": [keep(r) for r in ranked if r["c"] > 0][:top], "losers": [keep(r) for r in ranked[::-1] if r["c"] < 0][:top]}
    return out


def main():
    out = {"generated": datetime.now(timezone.utc).isoformat(), "sections": {}, "curve": [], "fred": [], "jgb": [], "movers": {}, "news": [], "errors": []}

    def safe(fn, *a):
        try:
            return fn(*a), None
        except Exception as e:  # noqa: BLE001
            return None, f"{fn.__name__} {a[0] if a else ''}: {e}".replace("  ", " ")

    yr = datetime.now(timezone.utc).year
    with ThreadPoolExecutor(max_workers=8) as ex:
        yfut = {sec: [(label, ex.submit(safe, yahoo, sym)) for sym, label in items] for sec, items in YAHOO.items()}
        nom_f = ex.submit(safe, treasury, "daily_treasury_yield_curve", (yr - 1, yr))
        real_f = ex.submit(safe, treasury, "daily_treasury_real_yield_curve", (yr - 1, yr))
        effr_f = ex.submit(safe, effr)
        jgb_f = ex.submit(safe, jgb)
        oas_f = [(sid, label, ex.submit(safe, fred, sid)) for sid, label in OAS]
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

        nom, err = nom_f.result()
        if err:
            out["errors"].append("treasury nominal: " + err)
        else:
            for key, label in CURVE:
                r = nom.get(key)
                if r:
                    out["curve"].append({"id": key, "label": label, "date": r[-1][0], "now": r[-1][1],
                                         "w1": value_on_or_before(r, 7), "m1": value_on_or_before(r, 30),
                                         "y1": value_on_or_before(r, 365)})
            if nom.get("10yr") and nom.get("2yr"):
                out["fred"].append(entry("T10Y2Y", "10y-2y spread", derive(nom["10yr"], nom["2yr"], lambda a, b: a - b)))
            if nom.get("10yr") and nom.get("3mo"):
                out["fred"].append(entry("T10Y3M", "10y-3m spread", derive(nom["10yr"], nom["3mo"], lambda a, b: a - b)))
            real, err = real_f.result()
            if err:
                out["errors"].append("treasury real: " + err)
            else:
                rk = real.get("10yr")
                if rk:
                    out["fred"].append(entry("DFII10", "10y real yield", rk))
                    if nom.get("10yr"):
                        out["fred"].append(entry("T10YIE", "10y breakeven", derive(nom["10yr"], rk, lambda a, b: a - b)))
        e, err = effr_f.result()
        out["errors"].append("effr: " + err) if err else out["fred"].append(entry("DFF", "Fed funds effective", e))
        for sid, label, fu in oas_f:
            r, err = fu.result()
            if err:
                out["errors"].append(err)
            else:
                out["fred"].append(entry(sid, label, r))

        j, err = jgb_f.result()
        if err:
            out["errors"].append("jgb: " + err)
        else:
            for t in ("2Y", "5Y", "10Y", "20Y", "30Y", "40Y"):
                r = j.get(t)
                if r:
                    out["jgb"].append(entry("JGB" + t, "JGB " + t, r))
        for fu in nfut:
            r, err = fu.result()
            if err:
                out["errors"].append("news " + err)
            else:
                out["news"].extend(r)
    try:
        mv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "movers.txt")
        if os.path.exists(mv):
            out["movers"] = build_movers(mv, out["errors"])
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"movers: {e}")
    total = sum(len(v) for v in out["sections"].values())
    if total == 0 and not out["curve"]:
        print("No data fetched at all; keeping previous data.json", file=sys.stderr)
        for e in out["errors"][:10]:
            print(e, file=sys.stderr)
        sys.exit(1)
    path = sys.argv[1] if len(sys.argv) > 1 else "docs/data.json"
    with open(path, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    for e in out["errors"]:
        print("WARN", e)
    print(f"wrote {path}: {total} quotes, {len(out['curve'])} curve pts, {len(out['news'])} headlines, {len(out['errors'])} errors")


if __name__ == "__main__":
    main()
