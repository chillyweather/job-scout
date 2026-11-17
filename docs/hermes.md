# Running job-scout from the Hermes agent

job-scout is a tool the daily sweep calls first.
It has no schedule of its own and makes no model calls.

## One-time setup on the server

1. Clone and install (see the README). Keep the repository folder: `state/job-scout.sqlite` lives there and must persist between runs.
2. Create `config.local.json` with the server paths of the application tracker and the leads inbox:

   ```json
   {"known_files": ["/path/to/🟢 Track A - Application Tracker.md", "/path/to/Vacancy Leads Inbox.md"]}
   ```

   If the vault is not on the server, leave `known_files` empty. job-scout then reports roles you already hold, and the dedupe step below has to catch them.
3. Run `job-scout check`. Every board should print `ok`. Fix or disable the ones that do not.
4. Run `job-scout poll --dry-run --format markdown` to see the size of the first report. If it is too long to assess, run `job-scout poll --baseline` once.

## Daily sweep: what Hermes does

Add this as the first step of the existing sweep prompt:

> Run `job-scout poll` in the job-scout folder and read its JSON.
>
> 1. If `boards.failed` is not empty, mention each failed board in the run summary. Three or more consecutive failures means the slug probably changed: say so.
> 2. For each item in `postings`, judge fit against the CV and the direction notes, exactly as for leads found by search. Apply the leads inbox rules: tiers `realistic`, `plausible stretch`, `lead to verify`; skip dream roles, pure title matches, and roles with several hard gaps.
> 3. Before adding a lead, deduplicate against the inbox and the tracker as usual. job-scout already dropped exact matches, not near duplicates.
> 4. Write each kept lead to the inbox in its usual format, and add the line `- **Found by:** board poller` (or `web search` for leads found the usual way).
> 5. A posting with `change: "updated"` or `"reopened"` that is already in the inbox: update that entry's `Last checked` and note what changed. Do not create a second entry.
> 6. Then run the usual web search for sources job-scout does not cover: LinkedIn-only roles, staffing agencies, AllJobs leads that resolve to an employer page, custom career pages, and Comeet boards.
>
> Never change the application tracker.

## Weekly: the Europe glance

Europe is a side track, so it runs once a week, separately from the daily sweep:

> Run `job-scout --config config.europe.json poll` in the job-scout folder and read its JSON.
> Every posting has a `work_permit` tag and the sentence it came from.
> Postings tagged `permit_required` were already removed.
>
> 1. Put `sponsors`, `conditional` and `remote_contract` postings first. For `conditional`, check that the role's country is one the posting sponsors.
> 2. Judge fit as for Israel, and add one line on the permit situation in plain words.
> 3. Write a short weekly summary, not inbox entries: Europe leads go into the inbox only when Dima picks one.
> 4. Report failed boards as in the daily sweep.

The first Europe run reports every matching open role. Run it with `--dry-run --format markdown` first to see the size, and `--baseline` if it is too long.

## Weekly: growing the watchlist

Once a week, Hermes looks for companies hiring for the target role shapes whose boards are on Greenhouse, Lever or Ashby, and proposes additions in the run summary with company, vendor, slug and which list they belong to: `watchlist.json` for Israel, `watchlist.europe.json` for European and remote-first companies.
Dima confirms each before it goes into `watchlist.json`.
Search proposes boards; it never creates leads directly.

## The two-week trial

The `Found by` line is what the stop rule needs.
After two weeks, count realistic leads by source and compare the board's `published_at` with the date the same role was found by search.
Keep the poller if it supplied at least two realistic leads search did not, or found leads a median of two or more days earlier.
