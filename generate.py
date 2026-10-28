#!/usr/bin/env python3
"""Build the .ics subscription feeds into docs/.

Run with no arguments. Writes docs/*.ics, docs/index.html and
state/sequences.json. Nothing outside the standard library is needed.
"""

import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import ics
from src.sources import cricket, rugby

ROOT = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(ROOT, "docs")
STATE = os.path.join(ROOT, "state", "sequences.json")

# How long each event blocks out. Cricket is deliberately an hour: a real Test
# day or ODI would swallow the whole working day in a week view, and the point
# of the entry is to tell you when play starts.
DURATIONS = {
    "cricket": 60,
    "rugby": 120,
}

# Keep a little history so a feed still shows last week's result, but not so
# much that a season's worth of Test days piles up in the file.
HISTORY_DAYS = 90

# A UID's SEQUENCE must only ever go up, so entries are kept well past the
# fixture itself before being dropped.
STATE_RETENTION_DAYS = 400


def load_state():
    try:
        with open(STATE) as handle:
            return json.load(handle)
    except (IOError, ValueError):
        return {}


def prune_state(sequences, today):
    cutoff = (today - dt.timedelta(days=STATE_RETENTION_DAYS)).isoformat()
    for uid in [u for u, r in sequences.items() if r.get("seen", "9999") < cutoff]:
        del sequences[uid]
    return sequences


def recent(matches, today):
    """Drop fixtures that finished long enough ago to be clutter."""
    cutoff = dt.datetime.combine(
        today - dt.timedelta(days=HISTORY_DAYS), dt.time(0, 0), dt.timezone.utc)
    return [m for m in matches if m.start >= cutoff]


def save_state(sequences):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as handle:
        json.dump(sequences, handle, indent=1, sort_keys=True)
        handle.write("\n")


def build():
    today = dt.date.today()
    years = [today.year, today.year + 1, today.year + 2]

    print("fetching cricket fixtures for %s ..." % years)
    cricket_fixtures = cricket.fetch(years, include_completed_years=[today.year])
    print("  %d fixtures" % len(cricket_fixtures))

    print("fetching rugby fixtures ...")
    wallabies = recent(rugby.wallabies(DURATIONS["rugby"]), today)
    brumbies = recent(rugby.brumbies(DURATIONS["rugby"]), today)

    feeds = [
        ("wallabies.ics", "Wallabies",
         "Australia men's rugby union - Tests, Rugby Championship, Nations Championship and Rugby World Cup.",
         wallabies),
        ("brumbies.ics", "ACT Brumbies",
         "ACT Brumbies - Super Rugby Pacific.",
         brumbies),
        ("cricket-australia-men.ics", "Australia Men's Cricket",
         "Australia men's Tests, ODIs and T20Is. Each Test day is a separate entry.",
         recent(cricket.mens_internationals(cricket_fixtures, DURATIONS["cricket"]), today)),
        ("cricket-australia-women.ics", "Australia Women's Cricket",
         "Australia women's cup knockouts, plus home Tests against England or India.",
         recent(cricket.womens_selected(cricket_fixtures, DURATIONS["cricket"]), today)),
    ]

    everything = []
    for _, _, _, matches in feeds:
        everything.extend(matches)
    feeds.append((
        "all.ics", "Charlie's Sport",
        "Wallabies, Brumbies, Australia men's cricket and Australia women's cricket knockouts.",
        everything,
    ))

    sequences = load_state()
    os.makedirs(DOCS, exist_ok=True)
    summary = []

    for filename, name, description, matches in feeds:
        body = ics.render(matches, name, description, sequences=sequences)
        with open(os.path.join(DOCS, filename), "w", newline="") as handle:
            handle.write(body)
        upcoming = [m for m in matches
                    if m.start >= dt.datetime.now(dt.timezone.utc)]
        nxt = min(upcoming, key=lambda m: m.start) if upcoming else None
        summary.append((filename, name, description, len(matches), nxt))
        print("  %-32s %3d events" % (filename, len(matches)))

    save_state(prune_state(sequences, today))
    write_index(summary)
    return summary


def write_index(summary):
    rows = []
    for filename, name, description, count, nxt in summary:
        when = (nxt.start.strftime("%a %d %b %Y, %H:%M UTC") + " — " + nxt.summary
                if nxt else "nothing scheduled yet")
        rows.append(
            '<li><a class="feed" href="{f}">{n}</a>'
            '<p class="desc">{d}</p>'
            '<p class="meta">{c} events · next: {w}</p></li>'.format(
                f=filename, n=_html(name), d=_html(description), c=count, w=_html(when)))

    built = dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y %H:%M UTC")
    page = INDEX_TEMPLATE.replace("{{ROWS}}", "\n".join(rows)).replace("{{BUILT}}", built)
    with open(os.path.join(DOCS, "index.html"), "w") as handle:
        handle.write(page)


def _html(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


INDEX_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sport Calendars</title>
<style>
  :root {
    --bg: #fbfaf8; --card: #ffffff; --ink: #1b1a18; --muted: #6b6762;
    --line: #e7e3dd; --accent: #1f6f4a;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #141413; --card: #1d1c1a; --ink: #f0eee9; --muted: #9b958c;
      --line: #2e2c29; --accent: #6cc295;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 48px 16px 72px; background: var(--bg); color: var(--ink);
    font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  }
  .wrap { max-width: 640px; margin: 0 auto; }
  h1 { font-size: 1.6rem; margin: 0 0 6px; letter-spacing: -0.015em; }
  .sub { color: var(--muted); margin: 0 0 32px; }
  ul { list-style: none; margin: 0; padding: 0; }
  li {
    background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: 18px 20px; margin-bottom: 14px;
  }
  a.feed {
    color: var(--accent); font-weight: 650; font-size: 1.05rem;
    text-decoration: none; overflow-wrap: anywhere;
  }
  a.feed:hover { text-decoration: underline; }
  .desc { margin: 6px 0 0; }
  .meta { margin: 8px 0 0; color: var(--muted); font-size: 0.875rem; }
  .how { margin-top: 36px; border-top: 1px solid var(--line); padding-top: 24px; }
  .how h2 { font-size: 1rem; margin: 0 0 10px; }
  .how p, .how li.plain { color: var(--muted); font-size: 0.9rem; }
  .how ol { padding-left: 20px; color: var(--muted); font-size: 0.9rem; }
  code {
    background: var(--bg); border: 1px solid var(--line); border-radius: 5px;
    padding: 1px 5px; font-size: 0.85em;
  }
  footer { margin-top: 32px; color: var(--muted); font-size: 0.8rem; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Sport Calendars</h1>
  <p class="sub">Subscribable fixture feeds, rebuilt daily from official sources.</p>
  <ul>
{{ROWS}}
  </ul>
  <div class="how">
    <h2>How to subscribe</h2>
    <ol>
      <li>Copy a feed's link address (right-click &rarr; Copy Link).</li>
      <li><strong>Apple Calendar:</strong> File &rarr; New Calendar Subscription, paste, set
          auto-refresh to every day.</li>
      <li><strong>Google Calendar:</strong> Other calendars &rarr; + &rarr; From URL, paste.</li>
      <li><strong>Outlook:</strong> Add calendar &rarr; Subscribe from web, paste.</li>
    </ol>
    <p>Swap <code>https://</code> for <code>webcal://</code> to have your calendar app
       pick the link up directly.</p>
  </div>
  <footer>Last built {{BUILT}}. Fixtures from cricket.com.au and rugby.com.au.</footer>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    build()
