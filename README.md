# Macro Morning Dashboard

A web page that refreshes itself every weekday (about 6:15am New York time, and again after the US close) with:
US index futures and indices, sector heatmap, the Treasury yield curve (vs 1 week / 1 month / 1 year ago),
spreads, real yields, JGB yields, energy, metals, agriculture, FX, crypto, global indices, headlines,
a US economic calendar, an auto-generated morning snapshot, and a "Copy brief for Claude" button.

Data: Yahoo Finance (prices), US Treasury and NY Fed (yields, Fed funds), Japan Ministry of Finance (JGBs),
FRED (credit spreads, best effort), public RSS feeds (headlines), TradingView widget (calendar). All free, no keys.

The stock baskets live in a separate repository and page:
[agentic-watchlist](https://github.com/alternateKen/agentic-watchlist) (link at the top of the dashboard).

## One-time switch-on
1. GitHub repo, Settings, Pages, Source: choose **GitHub Actions**.
2. Actions tab, "Update macro dashboard", **Run workflow** (this is also the "refresh now" button).
3. Open the link shown on the run. Bookmark it.

Files: `scripts/fetch_data.py` (collects data), `docs/index.html` (the page), `.github/workflows/update.yml` (the schedule).
To add a ticker, edit the `YAHOO` list at the top of `fetch_data.py`.
