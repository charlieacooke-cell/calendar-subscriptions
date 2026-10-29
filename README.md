# Calendar Subscriptions

Subscribable `.ics` fixture feeds for the teams I actually follow, rebuilt
daily by GitHub Actions and served from GitHub Pages.

| Feed | Contents |
| --- | --- |
| `wallabies.ics` | Australia men's rugby union — Tests, The Rugby Championship, Nations Championship, Rugby World Cup, Pacific Nations Cup, British & Irish Lions |
| `brumbies.ics` | ACT Brumbies — Super Rugby Pacific and Super Rugby AUS |
| `cricket-australia-men.ics` | Australia men's Tests, ODIs and T20Is (one entry per Test day) |
| `cricket-australia-women.ics` | Australia women's cup knockouts (quarter-final onwards), plus Tests against England or India, home or away |
| `all.ics` | All of the above in one calendar |

## Where the data comes from

Both sources are the keyless JSON APIs the official sites use themselves, so
there is no scraping of rendered HTML and no third-party aggregator in the
middle.

**Cricket — `apiv2.cricket.com.au/web/fixtures/yearfilter`**
Returns every fixture Cricket Australia tracks worldwide, with
`isWomensMatch`, `gameType`, venue coordinates, broadcasters and ticket links.
All the selection happens in [`src/sources/cricket.py`](src/sources/cricket.py):
the men's feed keeps `gameType` in Test / ODI / T20 International with
`Australia Men` on one side, which naturally excludes BBL, Sheffield Shield and
tour matches against state sides.

**Rugby — `rugby-au-cms.graphcdn.app`, operation `FixturesAndResults`**
The GraphQL endpoint behind rugby.com.au's fixtures page. Competition and team
ids are hard-coded in [`src/sources/rugby.py`](src/sources/rugby.py) (Wallabies
`100`, Brumbies `150`). If Rugby AU ever renumbers them, `rugby.discover_filters()`
re-reads the current ids from the fixtures page's own filter props.

## Decisions worth knowing

- **Cricket events are one hour long.** A Test day or an ODI really runs seven
  hours, which swallows a week view whole. The entry exists to tell you when
  play starts. Rugby is two hours, which is the real thing. Both live in
  `DURATIONS` at the top of [`generate.py`](generate.py).
- **Each Test day is its own event** — "1st Test (Day 3)" — rather than one
  five-day block.
- **Stable UIDs, rising `SEQUENCE`.** The UID is a hash of the source fixture
  id, so a kick-off that moves updates the existing entry instead of creating a
  second one. `state/sequences.json` tracks a fingerprint per UID and bumps
  `SEQUENCE` only when something a viewer would notice changes, which is what
  makes calendar apps accept the update.
- **`TRANSP:TRANSPARENT`** on everything, so sport never makes you look busy.
- **Unconfirmed fixtures are marked.** Rugby AU parks a fixture with no
  announced kick-off at exactly midnight UTC; those get `[time TBC]` and
  `STATUS:TENTATIVE`.
- **The women's feed takes two rules**, in `_wanted_womens()`: cup knockouts
  from the quarter-finals on, and Tests against England or India, home or
  away. It is often sparse, by design. A cup knockout exists in the API as
  "TBC v TBC" until the draw is settled, so an Australia semi-final only
  appears once their place is confirmed — typically a few days out. As of
  October 2026 no women's Test is scheduled in Australia at all, so the one
  Test in the feed is the 2027 Ashes Test at Headingley, which lands at the
  Australian time it is watchable rather than its local start. Setting
  `WOMENS_TESTS_AT_HOME_ONLY = True` in `src/sources/cricket.py` narrows the
  rule back to home Tests only, which would empty the feed today.
- **"In Australia" is decided on two signals, not one.** CA writes
  `venue.state` inconsistently — `NSW` but also `nsw` and `tas` — and leaves it
  blank for at least one Sydney ground, so `_in_australia()` accepts either a
  recognised state or coordinates inside an Australian bounding box.
- **Women's fixtures have no `gameType`.** CA reports it as `None` on
  essentially every women's match, so `_is_test()` falls back to the match name
  and the scheduled number of days.
- **90 days of history** is kept so last week's result is still visible;
  anything older is dropped.
- **Stdlib only.** No `pip install` step anywhere, in CI or locally.

## Running it locally

```bash
python3 generate.py
```

Writes `docs/*.ics`, `docs/index.html` and `state/sequences.json`.

## How the publishing works

[`.github/workflows/build.yml`](.github/workflows/build.yml) runs at 19:00 UTC
daily (6am AEDT), regenerates the feeds, and commits `docs/` only when a
fixture actually changed — `DTSTAMP` moves on every run and would otherwise
produce a commit a day of pure noise. GitHub Pages serves `docs/` from `main`,
so `git log -p docs/` is a readable history of every time a fixture moved.
