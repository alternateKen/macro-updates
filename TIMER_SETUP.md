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
| Title | `macro pre-market` |
| URL | `https://api.github.com/repos/alternateKen/macro-updates/actions/workflows/update.yml/dispatches` |
| Execution schedule | Custom, and the job's time zone: see step 4 |
| **Advanced** tab, Request method | `POST` |
| **Advanced** tab, Request body | `{"ref":"main"}` |
| **Advanced** tab, Headers (add four) | `Authorization` = `Bearer github_pat_...your token...` |
| | `Accept` = `application/vnd.github+json` |
| | `X-GitHub-Api-Version` = `2022-11-28` |
| | `Content-Type` = `application/json` |
| Notifications | tick **notify me when the job fails** |

3. Press **Test run** (or **Create** then **Test run** from the job's page). A good result is **HTTP 204**. Then open your repository's **Actions** tab:
   a new run named "Update macro dashboard" with the event **workflow_dispatch** should appear and finish in 1 to 2 minutes.
4. **Choose the job's time zone first, then the schedule.** Each job has its own time zone (the "Next executions" box says which, for example
   "In this job's individual timezone (Asia/Kuala_Lumpur)"). The easiest, daylight-saving-proof setup is to give each job the time zone of the
   market it follows, so you type the clock time you actually want:
   - US jobs: set the job's time zone to **America/New_York** (it then handles summer and winter time by itself).
   - The Asian-close job: leave it on **Asia/Kuala_Lumpur** (same as Hong Kong and Singapore, UTC+8, no daylight saving).
   Change the time zone **before** filling in the schedule, because the picked hours are read in that zone. Always confirm with the
   **Next executions** box on the right: it must show the clock times and weekdays in the table below.
5. Use **Duplicate** on that job for each row below and change only the Title, the time zone, the schedule and, for the watchlist, the repository name in the URL.

| Job | URL repository | Job time zone | Weekdays | Hours | Minutes | Crontab to expect |
|---|---|---|---|---|---|---|
| macro pre-market | `macro-updates` | America/New_York | Mon to Fri | 6 | 15 | `15 6 * * 1-5` |
| macro after Asian close | `macro-updates` | Asia/Kuala_Lumpur | Mon to Fri | 18 | 30 | `30 18 * * 1-5` |
| macro after US close | `macro-updates` | America/New_York | Mon to Fri | 16 | 45 | `45 16 * * 1-5` |
| macro after US close backup | `macro-updates` | America/New_York | Mon to Fri | 18 | 15 | `15 18 * * 1-5` |
| watchlist pre-market | `agentic-watchlist` | America/New_York | Mon to Fri | 6 | 15 | `15 6 * * 1-5` |
| watchlist market hours | `agentic-watchlist` | America/New_York | Mon to Fri | 9, 10, 11, 12, 13, 14, 15, 16 | 0 and 30 | `0,30 9-16 * * 1-5` |

   **How to fill the Custom schedule box** (the five lists under "Custom"):
   - **Days of month:** leave every day selected. **Months:** leave every month selected.
   - **Days of week:** select **Monday to Friday only**. Click Monday, hold Shift and click Friday. If Saturday or Sunday stay highlighted,
     click them once to switch them off.
   - **Hours** and **Minutes:** click the first value, then hold **Ctrl** (Windows) or **Cmd** (Mac) and click each further value.
     For a single value, click only that one. First clear any highlighted values you do not want.
   - Check the **Crontab expression** box under the lists against the last column above. If it shows a different time, the lists are wrong.
   - The lists can look out of date after switching from "Every 15 minutes" to Custom, so do not trust their grey highlighting: trust the
     crontab expression and the Next executions box.

   **If you would rather use UTC** (set the job's time zone to UTC): pre-market `15 10 * * 1-5` **and** `15 11 * * 1-5` (one is 6:15am in New York in summer, the
   other in winter), Asian close `30 10 * * 1-5`, after US close `45 21 * * 1-5` plus backup `45 22 * * 1-5`, watchlist market hours `0,30 13-21 * * 1-5`.
   Do not mix: the same time typed under a different time zone runs at a different moment, and times on the other side of midnight shift the weekday
   (for example 21:45 UTC is 05:45 the next morning in Kuala Lumpur, so Monday to Friday there would run Tuesday to Saturday).

## Part C: check it works
- Next morning the **Actions** tab should show a run at about 6:15am New York time (10:15 or 11:15 UTC) with the event **workflow_dispatch**.
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
