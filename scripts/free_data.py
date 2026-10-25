#!/usr/bin/env python3
"""Free stand-ins for the Bloomberg screens on the macro dashboard. Standard library only.

Writes the files the dashboard already reads, in the same format, into the folder given on the command line:
  wirp_us.csv      Fed pricing: CME fed funds futures (ZQ, via Yahoo) + NY Fed effective rate, meeting by meeting (WIRP method)
  wirp_global.csv  next-meeting odds: US only (no free source for the other central banks)
  credit.csv       credit spreads: ICE BofA option-adjusted spreads from the FRED API (needs a free key, see below)
  eco.csv          US data calendar: Forex Factory weekly feed (consensus, prior); actuals for key releases from FRED

Each part is independent: if one source fails, its previous file is kept and the others still update.
The FRED key comes from the FRED_API_KEY environment variable only (a GitHub repository secret in the workflow),
so it can never be committed. FOMC dates: fomc_dates.csv next to this script.
Usage: python scripts/free_data.py bloomberg
"""
import calendar, csv, http.cookiejar, io, json, os, sys, time, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "application/json,text/csv,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}
MONTH_CODES = "FGHJKMNQUVXZ"

# credit.csv rows: (group, label, FRED series). Labels are what the page shows; the snapshot line uses the first four.
CREDIT = [
    ("Americas", "US IG corporate", "BAMLC0A0CM"),
    ("Americas", "US High Yield", "BAMLH0A0HYM2"),
    ("EMEA", "Euro High Yield", "BAMLHE00EHYIOAS"),
    ("Emerging Markets", "EM corporate", "BAMLEMCBPIOAS"),
    ("Americas", "US BBB corporate", "BAMLC0A4CBBB"),
    ("Americas", "US CCC & lower", "BAMLH0A3HYC"),
    ("Asia", "Asia EM corporate", "BAMLEMRACRPIASIAOAS"),
]

# Forex Factory title -> the name the page knows (its "Key releases" filter matches these names)
ECO_NAMES = {
    "CPI m/m": "CPI MoM", "Core CPI m/m": "Core CPI MoM", "CPI y/y": "CPI YoY", "Core CPI y/y": "Core CPI YoY",
    "Unemployment Claims": "Initial Jobless Claims", "Non-Farm Employment Change": "Change in Nonfarm Payrolls",
    "Prelim UoM Consumer Sentiment": "U. of Mich. Sentiment", "Revised UoM Consumer Sentiment": "U. of Mich. Sentiment",
    "Prelim UoM Inflation Expectations": "U. of Mich. 1 Yr Inflation", "Revised UoM Inflation Expectations": "U. of Mich. 1 Yr Inflation",
    "Core PCE Price Index m/m": "Core PCE Price Index MoM", "Advance GDP q/q": "GDP Annualized QoQ",
    "Federal Funds Rate": "FOMC Rate Decision (Upper Bound)", "CB Consumer Confidence": "Conf. Board Consumer Confidence",
    "Retail Sales m/m": "Retail Sales Advance MoM", "PPI m/m": "PPI Final Demand MoM",
}
# Actuals from FRED for key releases: event name -> (series, how to turn levels into the headline number)
ECO_ACTUALS = {
    "CPI MoM": ("CPIAUCSL", "mom"), "Core CPI MoM": ("CPILFESL", "mom"),
    "CPI YoY": ("CPIAUCNS", "yoy"), "Core CPI YoY": ("CPILFENS", "yoy"),
    "Change in Nonfarm Payrolls": ("PAYEMS", "diffK"), "Unemployment Rate": ("UNRATE", "pct"),
    "Initial Jobless Claims": ("ICSA", "K"), "Core PCE Price Index MoM": ("PCEPILFE", "mom"),
    "Retail Sales Advance MoM": ("RSAFS", "mom"), "PPI Final Demand MoM": ("PPIFIS", "mom"),
}


def get(url, timeout=20, tries=2):
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1 + i)
    raise last


def write_csv(path, meta, header, rows):
    buf = io.StringIO()
    for k, v in meta:
        buf.write(f"# {k}: {v}\n")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(buf.getvalue())


def read_meta_csv(path):
    meta, body = {}, []
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            if line.startswith("#"):
                k, _, v = line[1:].partition(":")
                meta[k.strip().lower()] = v.strip()
            elif line.strip():
                body.append(line)
    return meta, list(csv.DictReader(io.StringIO("".join(body))))


# ---------------- Fed pricing ----------------
def fomc_dates():
    _, rows = read_meta_csv(os.path.join(HERE, "fomc_dates.csv"))
    return sorted({date.fromisoformat(r["meeting"].strip()) for r in rows if r.get("meeting", "").strip()})


def yahoo_quotes(symbols):
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.addheaders = list(UA.items())
    try:
        op.open("https://fc.yahoo.com", timeout=10).read()   # answers 404 but sets the cookie the crumb needs
    except Exception:  # noqa: BLE001
        pass
    crumb = op.open("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=10).read().decode().strip()
    url = ("https://query1.finance.yahoo.com/v7/finance/quote?symbols=" + urllib.parse.quote(",".join(symbols))
           + "&crumb=" + urllib.parse.quote(crumb))
    return json.loads(op.open(url, timeout=20).read())["quoteResponse"]["result"]


def fed_pricing(out_dir, extra_meetings=()):
    effr = json.loads(get("https://markets.newyorkfed.org/api/rates/unsecured/effr/last/1.json"))["refRates"][0]
    r0, target = float(effr["percentRate"]), float(effr["targetRateTo"])
    today = date.today()
    meetings = sorted({m for m in list(fomc_dates()) + list(extra_meetings) if m >= today})
    months = []
    y, m = today.year, today.month
    for _ in range(18):
        months.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    syms = {f"ZQ{MONTH_CODES[m - 1]}{y % 100:02d}.CBT": (y, m) for y, m in months}
    quotes = yahoo_quotes(list(syms))
    times = [q.get("regularMarketTime") or 0 for q in quotes if q.get("regularMarketPrice")]
    newest = max(times) if times else 0
    avg = {}   # (year, month) -> futures-implied average fed funds rate for that month
    for q in quotes:
        p, t = q.get("regularMarketPrice"), q.get("regularMarketTime") or 0
        if p and q.get("symbol") in syms and newest - t <= 5 * 86400:   # skip contracts that have not traded for days
            avg[syms[q["symbol"]]] = 100 - p
    if len(avg) < 3:
        raise RuntimeError(f"only {len(avg)} fed funds futures prices from Yahoo")
    asof = datetime.fromtimestamp(newest, timezone.utc).date().isoformat()

    meeting_months = {(d.year, d.month) for d in meetings}
    rows, pre = [], r0
    for d in meetings:
        n = calendar.monthrange(d.year, d.month)[1]
        nxt = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
        # The new rate takes effect the day after the decision. Late-month meetings leave too few days in the month to
        # read the new rate reliably, so use the next month's contract when no meeting falls in it (CME FedWatch / WIRP).
        if d.day / n > 0.6:
            if nxt in meeting_months or nxt not in avg:
                break   # a handful of days would multiply the price noise, so stop rather than show a shaky number
            post = avg[nxt]
        elif (d.year, d.month) in avg:
            post = (avg[(d.year, d.month)] * n - pre * d.day) / (n - d.day)
        else:
            break
        chg = post - pre
        rows.append([d.isoformat(), f"{(post - r0) / 0.25:.3f}", f"{chg / 0.25 * 100:.1f}", f"{post - r0:.3f}", f"{post:.3f}"])
        pre = post
    if not rows:
        raise RuntimeError("no meeting could be priced")
    write_csv(os.path.join(out_dir, "wirp_us.csv"),
              [("source", "CME fed funds futures (ZQ) via Yahoo Finance + NY Fed effective rate, meeting-by-meeting implied rates (WIRP method), free data"),
               ("asof", asof), ("target", f"{target:.2f}"), ("effective", f"{r0:.2f}"),
               ("note", "cum = cumulative hikes (+) or cuts (-) priced from today; pct = % chance of a hike (+) or cut (-) at that meeting")],
              ["meeting", "cum", "pct", "imp_change", "implied_rate"], rows)
    write_csv(os.path.join(out_dir, "wirp_global.csv"),
              [("source", "CME fed funds futures via Yahoo (US only: no free source for other central banks' odds)"), ("asof", asof),
               ("note", "pct = % chance of a hike (+) or cut (-) at the next meeting")],
              ["region", "model", "meeting", "pct"], [["North America", "US - Fut", rows[0][0], rows[0][2]]])
    return f"Fed pricing: {len(rows)} meetings from {len(avg)} contracts, next {rows[0][0]} {float(rows[0][2]):+.0f}%"


# ---------------- FRED ----------------
def fred_key():
    return os.environ.get("FRED_API_KEY", "").strip()


def fred_obs(key, series, **params):
    q = {"series_id": series, "api_key": key, "file_type": "json", **params}
    d = json.loads(get("https://api.stlouisfed.org/fred/series/observations?" + urllib.parse.urlencode(q), timeout=20))
    return [(o["date"], float(o["value"])) for o in d.get("observations", []) if o.get("value") not in (".", "", None)]


def credit(out_dir, key):
    start = (date.today() - timedelta(days=130)).isoformat()
    rows, bad, asof = [], [], None
    for group, label, sid in CREDIT:
        try:
            obs = fred_obs(key, sid, observation_start=start)
        except Exception as e:  # noqa: BLE001
            bad.append(f"{sid} ({e})")
            continue
        pts = [v * 100 for _, v in obs]   # FRED publishes percent; the page shows basis points
        if len(pts) < 2:
            bad.append(f"{sid} (no data)")
            continue
        q = pts[-63:]   # about 3 months of trading days
        lvl, av = pts[-1], sum(q) / len(q)
        asof = max(asof or obs[-1][0], obs[-1][0])
        rows.append([group, label, f"{lvl:.2f}", f"{lvl - pts[-2]:.2f}", "", "", f"{min(q):.1f}", f"{max(q):.1f}",
                     f"{av:.1f}", f"{lvl - av:.1f}", f"{lvl - q[0]:.1f}", "spread"])
    if not rows:
        raise RuntimeError("no credit series: " + "; ".join(bad))
    order = ["Americas", "EMEA", "Asia", "Emerging Markets"]
    rows.sort(key=lambda r: order.index(r[0]))   # the page starts a new group heading whenever the group changes
    write_csv(os.path.join(out_dir, "credit.csv"),
              [("source", "ICE BofA option-adjusted spreads via the FRED API (stand-ins for CDX / iTraxx), free data"), ("asof", asof),
               ("note", "level = spread in bp; low/high/avg over about 3 months of trading days; basis and roll do not apply")],
              ["group", "index", "level", "chg", "basis", "roll", "low", "high", "avg", "vs_avg", "chg_3m", "quote"], rows)
    return f"Credit: {len(rows)} of {len(CREDIT)} spreads, as of {asof}" + (f"; failed: {', '.join(bad)}" if bad else "")


# ---------------- economic calendar ----------------
def fmt_like(x, kind):
    if kind in ("mom", "yoy", "pct"):
        return f"{x:.1f}%"
    return f"{x:.0f}K"


def headline(obs, kind):
    v = [x for _, x in obs]
    if kind == "mom" and len(v) >= 2:
        return (v[-1] / v[-2] - 1) * 100
    if kind == "yoy" and len(v) >= 13:
        return (v[-1] / v[-13] - 1) * 100
    if kind == "diffK" and len(v) >= 2:
        return v[-1] - v[-2]          # PAYEMS is already in thousands
    if kind == "K" and v:
        return v[-1] / 1000
    if kind == "pct" and v:
        return v[-1]
    return None


def actual_from_fred(key, event, release_day):
    """The new print on release_day: FRED's data as known on that day, if it has a newer observation than the day before."""
    sid, kind = ECO_ACTUALS[event]
    start = (release_day - timedelta(days=500)).isoformat()
    now = fred_obs(key, sid, observation_start=start, realtime_start=release_day.isoformat(), realtime_end=release_day.isoformat())
    before = fred_obs(key, sid, observation_start=start, realtime_start=(release_day - timedelta(days=1)).isoformat(),
                      realtime_end=(release_day - timedelta(days=1)).isoformat())
    if not now or (before and now[-1][0] <= before[-1][0]):
        return ""
    x = headline(now, kind)
    return "" if x is None else fmt_like(x, kind)


def eco(out_dir, key):
    feed = json.loads(get("https://nfs.faireconomy.media/ff_calendar_thisweek.json"))
    now = datetime.now(timezone.utc)
    events, fomc = {}, set()
    path = os.path.join(out_dir, "eco.csv")
    if os.path.exists(path):   # keep last week's releases (and their actuals) for 7 days
        meta, rows = read_meta_csv(path)
        if meta.get("timezone", "+00:00") == "+00:00":
            for r in rows:
                try:
                    t = datetime.strptime(r["datetime"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                except (KeyError, ValueError):
                    continue
                if t >= now - timedelta(days=7):
                    events[(r["datetime"], r["event"])] = r
    for e in feed:
        if e.get("country") != "USD" or e.get("impact") == "Holiday":
            continue
        try:
            t = datetime.fromisoformat(e["date"]).astimezone(timezone.utc)
        except (KeyError, ValueError):
            continue
        name = ECO_NAMES.get(e["title"], e["title"])
        if name == "FOMC Rate Decision (Upper Bound)":
            fomc.add(datetime.fromisoformat(e["date"]).date())
        k = (t.strftime("%Y-%m-%d %H:%M"), name)
        old = events.get(k, {})
        events[k] = {"datetime": k[0], "event": name, "period": "", "survey": e.get("forecast", "") or "",
                     "actual": old.get("actual", ""), "prior": e.get("previous", "") or "", "revised": ""}
    filled = 0
    if key:
        for (ts, name), r in events.items():
            t = datetime.strptime(ts, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            if name in ECO_ACTUALS and not r["actual"] and now - timedelta(days=7) <= t <= now - timedelta(minutes=30):
                try:
                    r["actual"] = actual_from_fred(key, name, (t - timedelta(hours=5)).date())   # release date in New York
                    filled += bool(r["actual"])
                except Exception:  # noqa: BLE001
                    pass
    rows = [[r["datetime"], r["event"], r["period"], r["survey"], r["actual"], r["prior"], r["revised"]]
            for _, r in sorted(events.items())]
    write_csv(path, [("source", "Forex Factory weekly calendar (consensus, prior); actuals for key releases from FRED, free data"),
                     ("asof", now.date().isoformat()), ("timezone", "+00:00"),
                     ("note", "times are UTC; survey = Forex Factory forecast; the feed covers the current week only")],
              ["datetime", "event", "period", "survey", "actual", "prior", "revised"], rows)
    return f"Calendar: {len(rows)} US events ({filled} actuals filled from FRED)", fomc


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "bloomberg")
    os.makedirs(out_dir, exist_ok=True)
    key, fails, fomc = fred_key(), 0, set()
    try:
        msg, fomc = eco(out_dir, key)
        print(msg)
    except Exception as e:  # noqa: BLE001
        fails += 1
        print(f"WARN calendar failed, previous file kept: {e}")
    for name, fn in (("Fed pricing", lambda: fed_pricing(out_dir, fomc)),
                     ("credit", lambda: credit(out_dir, key) if key else "Credit: skipped, no FRED_API_KEY set (previous credit.csv kept)")):
        try:
            print(fn())
        except Exception as e:  # noqa: BLE001
            fails += 1
            print(f"WARN {name} failed, previous file kept: {e}")
    return 1 if fails == 3 else 0


if __name__ == "__main__":
    sys.exit(main())
