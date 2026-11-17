# job-scout

job-scout reads company job boards directly and reports the roles that appeared, changed or reopened since its last run.
It is the first step of a daily job-search sweep run by an agent, not a replacement for it.

## Why it exists

An agent asked each morning to "check new matching positions" searches the web.
A search index samples: it cannot say what was posted yesterday, it returns roles that closed months ago, and it cannot tell what it missed.

Greenhouse, Lever and Ashby publish every open role of a company as public JSON, with no key.
Reading those lists gives three things a search cannot:

- **Complete per company.** Every open role on a watched board, not the ones an index happened to keep.
- **An exact diff.** New, changed, reopened and closed, from stored state rather than model judgement.
- **Same-day freshness**, with the board's own publish date.

What it does not reach: LinkedIn-only roles, staffing agencies, AllJobs, and custom career pages.
The agent's web search keeps covering those.

## How it works

```
watchlist.json ─► fetch each board ─► location + title filters ─► diff against SQLite state
                                                                 ─► drop roles already in your notes
                                                                 ─► JSON report for the agent
```

1. **Watchlist.** `watchlist.json` lists companies with their job-board vendor and slug.
2. **Fetch.** One adapter per vendor turns its response into the same posting shape. A board that fails is listed in the report with a failure count; it never looks like "nothing new", and its roles are not marked closed.
3. **Filters in code.** Location terms and title include/exclude terms in `config.json`. Word-boundary matching, so "ai" does not match "retail" and "IL" is never treated as Israel.
4. **State.** SQLite records first seen, last seen, closed, and the content hash at the time a role was reported. A role is reported again only when its title, locations or description change, or when it reopens.
5. **Your notes.** Roles whose job id appears in the tracker or the leads inbox, or whose company and exact title share a line there, are left out and counted.

No model is called. Judging fit is the agent's job, on the handful of roles that survive.

## Install

Python 3.10 or later, no dependencies.

```bash
git clone https://github.com/chillyweather/job-scout.git
cd job-scout
python3 -m pip install -e .
```

Point it at your notes in `config.local.json` (gitignored, overrides keys of `config.json`):

```bash
cp config.local.example.json config.local.json   # then edit the two paths
```

## Commands

```bash
job-scout check                          # fetch every board once, print counts; writes nothing
job-scout poll                           # the daily run: JSON report on stdout, state updated
job-scout poll --format markdown         # the same report for a person
job-scout poll --dry-run                 # compute the report, write no state
job-scout poll --baseline                # mark everything open as seen, report nothing
job-scout boards                         # list the watchlist with API URLs
```

Exit codes: `0` ok, `2` every board failed, `3` config error.

The first `poll` reports every matching open role, because nothing has been seen yet.
Run `poll --dry-run --format markdown` first to see how many that is, and `poll --baseline` if you would rather start from today.

## The report

The shape, with made-up numbers:

```json
{
  "run_at": "2026-11-18T05:00:00+00:00",
  "mode": "poll",
  "boards": {"total": 40, "ok": 39, "failed": [{"company": "...", "board": "greenhouse:slug", "error": "...", "consecutive_failures": 1}]},
  "counts": {"fetched": 2140, "outside_location": 1610, "title_filtered": 470, "known_in_notes": 12, "already_reported": 40, "new": 6, "updated": 1, "reopened": 1, "closed": 9},
  "postings": [{"key": "...", "company": "...", "title": "...", "location": "...", "url": "...", "published_at": "...", "description": "...", "change": "new", "first_poll_of_board": false}],
  "known_in_notes": [{"company": "...", "title": "...", "reason": "job id found in notes"}],
  "closed_since_last_run": [{"company": "...", "title": "...", "url": "..."}]
}
```

`first_poll_of_board: true` means the board was added recently, so "new" there means new to you, not necessarily new on the market. Check `published_at`.

## Adding companies

Add an entry to `watchlist.json` and run `job-scout check`.
The slug is the part of the board URL after the vendor host: `job-boards.greenhouse.io/<slug>`, `jobs.lever.co/<slug>`, `jobs.ashbyhq.com/<slug>`.
For boards on `jobs.eu.lever.co`, add `"region": "eu"`.

Not supported yet: Comeet, Workday, BambooHR, SmartRecruiters. Comeet matters for Israel; see `docs/decisions.md`.

## Tests

```bash
python3 -m unittest discover -s tests -t .
```

All offline, against saved board responses in `tests/fixtures`.

## Running it from the Hermes agent

See [docs/hermes.md](docs/hermes.md).
