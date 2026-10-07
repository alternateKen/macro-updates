# Macro Morning Dashboard

A web page that refreshes itself three times every weekday with:
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

## Refresh times (weekdays)
1. **Pre-market:** about 6:15am New York time (10:15 UTC in US summer time, 11:15 UTC in US winter time).
2. **After the US close:** about 4:45pm New York time (20:45 UTC in summer, 21:45 UTC in winter).
3. **After the Asian close:** 10:30 UTC every weekday (India closes last, at 10:00 UTC). That is 6:30pm Hong Kong and Singapore, 7:30pm Tokyo and Seoul, 4:00pm India.

GitHub can start a scheduled run a few minutes late. You can also press **Run workflow** on the Actions tab at any time.

## Top movers (ranked by impact on the index)
The morning snapshot ranks stocks by their **contribution to the index move** (weight in the index x day move), for the Dow 30, S&P 500,
Nasdaq-100 (members read live from Wikipedia) and China H-shares, China A-shares, Taiwan and Korea (curated large caps in `movers.txt`).
- Dow is price-weighted: contribution is in index points (price change / the Dow divisor, derived live).
- Everything else uses weights from Bloomberg files in the `weights/` folder when present (exact), otherwise Yahoo market caps (approximate;
  the card is marked "approx", and Asian lists are only a basket of large caps, not the whole index).
- How to export the Bloomberg weights: see `weights/README.txt`.
To change the Asian lists, open `movers.txt` on GitHub, click the pencil, edit and save. Bloomberg style codes work (`0700 HK`, `600519 CH`, `2330 TT`, `005930 KS`).

## Bloomberg screens (typed in by hand)
Bloomberg cannot be read automatically from GitHub, so three screens are kept as small files in the `bloomberg/` folder and shown on the page:
`wirp_us.csv` + `wirp_global.csv` (Fed funds futures and every central bank's next meeting, from WIRP), `credit.csv` (CDX / iTraxx spreads) and
`eco.csv` (US releases with Bloomberg consensus, from ECO). Each file starts with an `# asof:` date; the page shows it and turns amber when it is more
than one working day old (a week for the calendar). See `bloomberg/README.txt` for how to refresh them. Saving a file rebuilds the page.
