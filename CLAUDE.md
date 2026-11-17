# job-scout

Polls company job boards (Greenhouse, Lever, Ashby) and reports postings new since the last run. Read README.md, then docs/decisions.md.

- Python 3.10+, standard library only. Do not add dependencies without a recorded decision in docs/decisions.md.
- Tests are offline: `python3 -m unittest discover -s tests -t .`. Never call the network in a test; add fixtures instead.
- No model calls in this package. Fit judgement belongs to the agent that runs it (docs/hermes.md).
- A board failure must stay visible in the report and must not close that board's postings.
