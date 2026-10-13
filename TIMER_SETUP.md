# On-time refreshes with a free external timer (about 15 minutes, no coding)

**Why:** GitHub's own scheduler starts scheduled runs hours late (5 to 9 hours for the morning runs, 2 to 4 hours for the evening runs), so the
pre-market refresh never arrives before the US open. A free timer service that presses the workflow's "Run workflow" button on the dot fixes this.
The GitHub schedule stays in place as a fallback, so nothing is lost if the timer ever fails.

**Cost:** nothing. GitHub access tokens are free, and [cron-job.org](https://cron-job.org) has a free plan (unlimited jobs under fair use,
as often as once a minute, can send POST requests with a body and headers). If any step asks for a card or a payment, stop: you picked the wrong
product. Any other timer service that can send an HTTP POST with headers works with the same values below.

---

## Part A: make an access token (once)
1. On GitHub click your profile picture, then **Settings**, then at the bottom left **Developer settings**, then **Personal access tokens**, then **Fine-grained tokens**, then **Generate new token**.
2. **Token name:** `cron-job.org workflow trigger`. **Expiration:** 1 year (put a reminder in your calendar to renew it).
3. **Resource owner:** `alternateKen`. **Repository access:** choose **Only select repositories** and tick **macro-updates** and **agentic-watchlist**.
4. Under **Repository permissions** find **Actions** and set it to **Read and write**. Leave everything else on "No access".
5. Press **Generate token**. Copy the token (it starts with `github_pat_`). GitHub shows it only once.
   **Never paste the token into a chat, a repository, or an email.** It can only run workflows on those two repositories; it cannot read your code.
   If it ever leaks, delete it on the same page and make a new one.

## Part B: make the timer jobs on cron-job.org
1. Sign up at cron-job.org (free) and confirm your email. Open **Cronjobs**, then **Create cronjob**.
2. Fill in the first job exactly like this:

| Field | Value |
|---|---|
| Title | `macro pre-market 10:15 UTC` |
| URL | `https://api.github.com/repos/alternateKen/macro-updates/actions/workflows/update.yml/dispatches` |
| Execution schedule | custom (see the table in step 4). **Set the time zone of the job to UTC** |
| **Advanced** tab, Request method | `POST` |
| **Advanced** tab, Request body | `{"ref":"main"}` |
| **Advanced** tab, Headers (add four) | `Authorization` = `Bearer github_pat_...your token...` |
| | `Accept` = `application/vnd.github+json` |
| | `X-GitHub-Api-Version` = `2022-11-28` |
| | `Content-Type` = `application/json` |
| Notifications | tick **notify me when the job fails** |

3. Press **Test run** (or **Create** then **Test run** from the job's page). A good result is **HTTP 204**. Then open your repository's **Actions** tab:
   a new run named "Update macro dashboard" with the event **workflow_dispatch** should appear and finish in 1 to 2 minutes.
4. Use **Duplicate** on that job for each row below (change only the Title, the schedule and, for the watchlist, the repository name in the URL).
   Days are Monday to Friday. Times are UTC.

| Job | URL repository | Time (UTC) | In New York | In Hong Kong |
|---|---|---|---|---|
| macro pre-market A | `macro-updates` | 10:15 | 6:15am in US summer time | 6:15pm |
| macro pre-market B | `macro-updates` | 11:15 | 6:15am in US winter time | 7:15pm |
| macro after Asian close | `macro-updates` | 10:30 | 6:30am summer, 5:30am winter | 6:30pm |
| macro after US close | `macro-updates` | 21:45 | 5:45pm summer, 4:45pm winter | 5:45am next day |
| macro after US close backup | `macro-updates` | 22:45 | 6:45pm summer, 5:45pm winter | 6:45am next day |
| watchlist pre-market A | `agentic-watchlist` | 10:15 | 6:15am in summer | 6:15pm |
| watchlist pre-market B | `agentic-watchlist` | 11:15 | 6:15am in winter | 7:15pm |
| watchlist market hours | `agentic-watchlist` | every 30 minutes from 13:00 to 21:30 | 9:00am to 5:30pm summer, 8:00am to 4:30pm winter | 9:00pm to 5:30am |

   For the "market hours" job choose **hours 13 to 21** and **minutes 0 and 30**.
   One of the two pre-market jobs is always an hour off from 6:15am in New York. That is on purpose (it avoids depending on a daylight-saving
   setting) and costs nothing: it is just one extra refresh.

## Part C: check it works
- Next morning the **Actions** tab should show a run at about 10:15 or 11:15 UTC (6:15am in New York) with the event **workflow_dispatch**.
  The page's "Data refreshed" time and the first lines of the "Copy brief for Claude" text will show the new time.
- cron-job.org keeps a history for each job. A failure also emails you.

## If something goes wrong
| What cron-job.org reports | Likely cause and fix |
|---|---|
| 401 or 403 | the token is wrong, expired, or lacks **Actions: Read and write** on that repository. Make a new token (Part A) and update the `Authorization` header in each job |
| 404 | the URL has a typo, or the token was not given access to that repository |
| 422 | the workflow cannot be started by hand. Both repositories' workflows already allow this, so check the URL ends in `update.yml/dispatches` |
| 204 but no new run | look at the **Actions** tab filter: it may be hidden under "All workflows" |

## Notes
- The timer and GitHub's late scheduled runs can both fire. A late run just refreshes the data again: harmless.
- Token expiry is the one thing that silently stops this. Set the calendar reminder.
