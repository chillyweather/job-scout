# Decisions

Short records of choices that would otherwise look arbitrary. Newest last.

## 1. Read job boards, do not search for jobs (2026-11-17)

A daily agent sweep already searches the web for roles.
Repeating that through a search API (Exa) would give the same sampled, partly stale results with more code.
Reading vendor job-board APIs gives what the sweep lacks: a complete list per company, an exact diff, and publish dates.
Search still has a job: proposing companies to watch.
This mirrors AutoScout's rule that only configured sources create candidates.

A one-query comparison on 2026-11-17 (Exa and Claude web search, AI solutions roles in Israel on job-board domains) returned stale roles from both, aggregator copies mostly from web search, and roles already in the tracker; neither could say what was new.

## 2. A tool for the existing agent, not a second agent (2026-11-17)

Dima did not want two daily runs. job-scout has no schedule and no model call; the Hermes sweep calls it first and does the fit judgement it already does.

## 3. Filters in code, fit in the model (2026-11-17)

Location and title rules are cheap, deterministic and testable, and they remove most of what a board lists.
The model sees only the few roles that pass and are new.

## 4. Report a role again only when it materially changes (2026-11-17)

State stores the content hash at the time a role was reported.
A role resurfaces when its title, locations or description change, or when it closes and reopens.
Taken from AutoScout's Material Change rule.

## 5. A failed board is loud (2026-11-17)

A board that fails to fetch is listed with a consecutive-failure count and does not close its roles.
Otherwise a broken slug looks exactly like a quiet company.

## 6. Comeet is deferred (2026-11-17)

Comeet hosts many Israeli boards (Lusha, Global-e, DriveNets, Buildots and others in the tracker).
Its public careers API needs a company UID and a token that are embedded in each company's careers page, so every board needs a manual lookup.
Worth adding once the trial shows the poller earns its place.

## 7. Standard library only (2026-11-17)

urllib, sqlite3 and json cover the job. No dependency means nothing to install on the server beyond the package.
