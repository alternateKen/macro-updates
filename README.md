# Macro Morning Dashboard

A web page that refreshes itself every weekday (about 6:30am New York, and again after the US close) with:
US index futures and indices, sector heatmap, the Treasury yield curve (vs 1 week / 1 month / 1 year ago),
spreads, real yields and credit, energy, metals, agriculture, FX, crypto, global indices, headlines,
and a US economic calendar.

Data: Yahoo Finance (prices), FRED (yields and spreads, end-of-day), public RSS feeds (headlines),
TradingView widget (calendar). All free, no keys.

## One-time switch-on
1. GitHub repo, Settings, Pages, Source: choose **GitHub Actions**.
2. Actions tab, "Update macro dashboard", **Run workflow** (this is also the "refresh now" button).
3. Open the link shown on the run. Bookmark it.

Files: `scripts/fetch_data.py` (collects data), `docs/index.html` (the page), `.github/workflows/update.yml` (the schedule).
To add a ticker, edit the `YAHOO` list at the top of `fetch_data.py`.

## Agentic Watchlist Dashboard
`watchlist.html` (link at the top of the macro page) shows your baskets from `watchlist.txt`:
basket averages, relative strength vs the S&P 500, 52-week range, 50/200-day trend, unusual volume,
latest headlines per stock, and a "Copy brief for Claude" button.
To change it: open `watchlist.txt` on GitHub, click the pencil, edit, save. It rebuilds automatically.
Share tickers only (no position sizes): the repository may be public.

The dashboards refresh every 30 minutes during US market hours (about 9:05am to 4:35pm New York time), at about 6:15am New York time, and whenever `watchlist.txt` changes. Bloomberg style codes (`2345 TT`, `6809 HK`, `6723 JP`, `300394 CH`, `NAPA NO`) are translated to Yahoo codes automatically.
