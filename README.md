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
