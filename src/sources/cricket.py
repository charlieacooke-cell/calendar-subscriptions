"""Cricket Australia fixtures.

Source: https://apiv2.cricket.com.au/web/fixtures/yearfilter
The site's own Preact front end calls this; no key, no auth. It returns every
fixture CA tracks worldwide (internationals, BBL/WBBL, Shield, overseas
bilaterals), so all the selection work happens here.
"""

import datetime as dt
import re

from .. import http
from ..model import Match

API = "https://apiv2.cricket.com.au/web/fixtures/yearfilter"
FIXTURES_PAGE = "https://www.cricket.com.au/matches"

MENS_TEAM = "Australia Men"
WOMENS_TEAM = "Australia Women"

# gameType values CA uses for the three international formats. Everything else
# it reports ("First Class Domestic", "T20 Domestic", "Non Accredited Test",
# and a bare None on most women's fixtures) is out of scope for the men's feed.
INTERNATIONAL_FORMATS = {"Test", "ODI", "T20 International"}

# A bilateral series never names a match this way, so matching the match name
# is enough on its own to mean "tournament knockout".
KNOCKOUT = re.compile(r"^\s*(quarter[\s-]*final|semi[\s-]*final|final|the final)\b", re.I)

# Australia women's Tests are rare, and the ones worth a calendar entry are the
# multi-format Ashes and India series - home or away, since there are so few of
# them. Set WOMENS_TESTS_AT_HOME_ONLY back to True to keep only home Tests.
WOMENS_TEST_OPPONENTS = {"England Women", "India Women"}
WOMENS_TESTS_AT_HOME_ONLY = False

# Deciding "is this in Australia?" off venue.state alone is not safe: CA writes
# it inconsistently ("NSW" but also "nsw", "tas") and leaves it blank for at
# least one Sydney ground. Every venue does carry coordinates, so check both.
AUS_STATES = {"NSW", "VIC", "QLD", "SA", "WA", "TAS", "ACT", "NT"}
AUS_LAT = (-44.0, -10.0)
AUS_LON = (112.0, 154.0)


def _fetch_year(year, completed):
    url = ("%s?year=%d&isCompleted=%s&limit=500&jsconfig=eccn:true&format=json"
           % (API, year, "true" if completed else "false"))
    return http.get_json(url).get("fixtures") or []


def fetch(years, include_completed_years=()):
    """Return the raw fixture dicts for the given years, de-duplicated by id."""
    by_id = {}
    for year in years:
        for fixture in _fetch_year(year, completed=False):
            by_id[fixture["id"]] = fixture
    for year in include_completed_years:
        for fixture in _fetch_year(year, completed=True):
            by_id.setdefault(fixture["id"], fixture)
    return list(by_id.values())


def _teams(fixture):
    return ((fixture.get("homeTeam") or {}).get("name") or "",
            (fixture.get("awayTeam") or {}).get("name") or "")


def _parse(stamp):
    # CA returns "2026-10-27T08:30:00Z".
    return dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def _in_australia(fixture):
    venue = fixture.get("venue") or {}
    if (venue.get("state") or "").strip().upper() in AUS_STATES:
        return True
    try:
        lat = float(venue.get("latitude"))
        lon = float(venue.get("longitude"))
    except (TypeError, ValueError):
        return False
    return AUS_LAT[0] <= lat <= AUS_LAT[1] and AUS_LON[0] <= lon <= AUS_LON[1]


def _is_test(fixture):
    """True for Tests, including women's fixtures where gameType is absent.

    CA reports gameType as None on essentially every women's match, so fall
    back to the two signals that are populated: the match name and the
    scheduled number of days.
    """
    if fixture.get("gameType") == "Test":
        return True
    if "test" in (fixture.get("name") or "").lower():
        return True
    return (fixture.get("numberOfDays") or 1) > 1


def _opponent_of(fixture, team):
    home, away = _teams(fixture)
    return away if home == team else home


def _venue_text(fixture):
    venue = fixture.get("venue") or {}
    parts = [p for p in (venue.get("name"), venue.get("location")) if p]
    return ", ".join(parts)


def _describe(fixture, extra=None):
    lines = []
    competition = (fixture.get("competition") or {}).get("name")
    if competition:
        lines.append(competition)
    if fixture.get("name"):
        lines.append(fixture["name"])
    if extra:
        lines.append(extra)
    channels = [c.get("channelName") for c in (fixture.get("channels") or []) if c.get("channelName")]
    if channels:
        lines.append("Watch: " + ", ".join(sorted(set(channels))))
    if fixture.get("ticketUrl"):
        lines.append("Tickets: " + fixture["ticketUrl"])
    lines.append("")
    lines.append("Source: cricket.com.au")
    return "\n".join(lines)


def _short(team):
    """'Australia Men' -> 'Australia'. The feed name already says which side."""
    for suffix in (" Men", " Women"):
        if team.endswith(suffix):
            return team[: -len(suffix)]
    return team


def _match_for_day(fixture, day, total_days, duration_minutes, categories):
    home, away = _teams(fixture)
    label = fixture.get("name") or "Match"
    title = "%s v %s" % (_short(home), _short(away))

    start = _parse(fixture["startDateTime"])
    uid_seed = "cricket:%s" % fixture["id"]
    if total_days > 1:
        start = start + dt.timedelta(days=day - 1)
        summary = "%s — %s (Day %d)" % (title, label, day)
        uid_seed += ":day%d" % day
        extra = "Day %d of %d" % (day, total_days)
    else:
        summary = "%s — %s" % (title, label)
        extra = None

    tentative = "TBC" in (home + away) or not _venue_text(fixture)
    return Match(
        uid_seed=uid_seed,
        summary=summary + (" [TBC]" if tentative else ""),
        start=start,
        duration_minutes=duration_minutes,
        location=_venue_text(fixture),
        description=_describe(fixture, extra),
        url=FIXTURES_PAGE,
        categories=categories,
        tentative=tentative,
    )


def mens_internationals(fixtures, duration_minutes=60):
    """Australia men's Tests, ODIs and T20Is. Tests become one event per day."""
    out = []
    for fixture in fixtures:
        if fixture.get("isWomensMatch"):
            continue
        if MENS_TEAM not in _teams(fixture):
            continue
        if fixture.get("gameType") not in INTERNATIONAL_FORMATS:
            continue
        days = fixture.get("numberOfDays") or 1
        if fixture.get("gameType") != "Test":
            days = 1
        for day in range(1, days + 1):
            out.append(_match_for_day(fixture, day, days, duration_minutes,
                                      ["Cricket", "Australia Men"]))
    return out


def _wanted_womens(fixture):
    """Two rules, either of which puts an Australia women's fixture in the feed.

    Cup knockouts, quarter-final onwards. Note these exist in the API as
    "TBC v TBC" until the draw is settled, so an Australia match only appears
    once their place is confirmed - typically a few days out.

    Plus Tests against England or India, home or away. Overseas ones land in
    the calendar at the Australian time they are watchable, so a 10am start at
    Headingley shows up as a 7pm event in Sydney.
    """
    if KNOCKOUT.match(fixture.get("name") or ""):
        return True
    if _is_test(fixture) and _opponent_of(fixture, WOMENS_TEAM) in WOMENS_TEST_OPPONENTS:
        return (not WOMENS_TESTS_AT_HOME_ONLY) or _in_australia(fixture)
    return False


def womens_selected(fixtures, duration_minutes=60):
    out = []
    for fixture in fixtures:
        if WOMENS_TEAM not in _teams(fixture):
            continue
        if not _wanted_womens(fixture):
            continue
        days = fixture.get("numberOfDays") or 1
        for day in range(1, days + 1):
            out.append(_match_for_day(fixture, day, days, duration_minutes,
                                      ["Cricket", "Australia Women"]))
    return out
