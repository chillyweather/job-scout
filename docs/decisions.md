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

## 8. Europe is a second profile, not a mode (2026-11-17)

Dima wants a low-cost look at European roles, not a second main track.
A separate config with its own state keeps the Israel report unchanged and lets the two run on different schedules (daily and weekly).
The Europe profile reads both watchlists, because several Israeli companies hire in Europe too.

Locations are judged one at a time, so a role listed in both New York and London passes, and bare "Remote" does not, since on these boards it usually means the US.

## 9. Work permission is a tag with its evidence, not a verdict (2026-11-17)

Without an EU passport, whether a posting allows hiring him is the deciding question, and most postings never say.
Code reads the description for blockers, offers and contract hiring, and attaches the sentence it matched.
Only an explicit blocker removes a posting; everything else stays, tagged.

The first version treated any blocker as decisive. On the first real board checked (n8n), every posting said "We can sponsor visas to Germany; for any other country, you need to have existing right to work", and all of them were removed.
That sentence is an offer, so a blocker next to an explicit sponsorship offer is now `conditional` and stays in the report.

## 10. Standing rules from the tracker live in code (2026-11-20)

Three of Dima's rules are mechanical enough to check before the agent sees a posting:

- **Blocked companies** (`blocked_companies`): never report them. Unframe, after its September rejection.
- **High-level Hebrew** (`hebrew`): rule adopted 16 September 2026, skip openings that declare native or high-level Hebrew. Dropped postings are listed once under `excluded_by_rule` with the matching sentence, because a regex can misread a requirement and a silent drop would hide that. "Fluent Hebrew", "Hebrew is a plus" and Hebrew-language postings are tagged, not dropped: he applied to a Hebrew posting (Madanes #123).
- **One role per company**: a posting whose employer has an application record in the tracker carries `employer_in_tracker`. A flag, not a drop: a closed earlier application can make a better-matching role worth it, and that is a judgement. Only tracker record lines count (`| 117 | ...` rows and `### 21.` headings), so short names such as Via or Rise do not match unrelated text.

Fit level ("realistic mid-level only") stays with the agent; titles do not say it reliably.
