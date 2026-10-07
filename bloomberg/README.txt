BLOOMBERG SCREENS ON THE DASHBOARD  (refreshed by hand: Bloomberg cannot be read automatically from GitHub)

Four small files feed three sections of the macro page. Each starts with lines like "# asof: 2026-10-07". Change that date whenever you
refresh the numbers; the page shows it, and turns amber when the data is more than one working day old (a week for the calendar).

  wirp_us.csv       Fed funds futures path             Bloomberg WIRP <GO>, region United States, instrument Fed Funds Futures
  wirp_global.csv   next meeting, every central bank   WIRP <GO>, the "models" list on the left (US, CA, EZ, GB, SE, CH, NO, AU, NZ, JP, IN, CL)
  credit.csv        CDX / iTraxx spreads               your Markit credit indices screen (spread, 3 months)
  eco.csv           US releases with consensus         ECO <GO>, United States, All Economic Releases, Agenda view for the next 1 to 2 weeks

WHAT THE NUMBERS MEAN
  wirp: "cum" = cumulative hikes (+) or cuts (-) priced from today; "pct" = % chance of a hike (+) or cut (-) at that meeting.
  credit: "quote" is "price" for indices marked * on the screen (CDX High Yield, CDX EM). For those a FALLING price means WIDER spreads.
  eco: times are copied exactly as the terminal shows them; "# timezone: +08:00" at the top must match your terminal clock.
       (A check: CPI at 8:30am New York shows as 20:30 on a UTC+8 terminal.)

EASIEST WAY TO REFRESH (no typing)
  Paste fresh screenshots of the three screens into a Claude session on this repository and ask for the bloomberg/ files to be updated.
  A morning refresh needs WIRP and the credit screen; the calendar only needs a refresh once a week.

TO EDIT BY HAND
  On GitHub open the file, click the pencil, change the numbers (keep the first lines starting with #), and press Commit changes.
  The page rebuilds itself within a few minutes.
