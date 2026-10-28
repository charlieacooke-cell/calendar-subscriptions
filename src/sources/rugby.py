"""Rugby Australia fixtures.

Source: the Apollo/GraphQL endpoint behind rugby.com.au's fixtures page
(https://rugby-au-cms.graphcdn.app, operation FixturesAndResults). No key.

Competition and team ids are published in the fixtures page's own filter
props, so discover_filters() below can re-read them if Rugby AU renumbers.
"""

import datetime as dt
import json
import re

from .. import http
from ..model import Match

GRAPHQL = "https://rugby-au-cms.graphcdn.app"
FIXTURES_PAGE = "https://www.rugby.com.au/fixtures-results"

QUERY = (
    "query FixturesAndResults($comps:[CompInput],$teams:[String],$type:String,"
    "$skip:Int,$limit:Int){getFixtureItems(comps:$comps,teams:$teams,type:$type,"
    "skip:$skip,limit:$limit){id compId compName dateTime group isLive isBye "
    "round roundType roundLabel season status venue sourceType matchLabel "
    "homeTeam{id name} awayTeam{id name}}}"
)

# Rugby AU's filter ids, read from the fixtures page on 2026-10-29.
WALLABIES = "100"
BRUMBIES = "150"

WALLABIES_COMPS = [
    ("3", "International"),
    ("114", "Nations Championship"),
    ("214", "The Rugby Championship"),
    ("210", "Rugby World Cup"),
    ("219", "Pacific Nations Cup"),
    ("221", "British & Irish Lions"),
]
BRUMBIES_COMPS = [
    ("205", "Super Rugby Pacific"),
    ("103", "Super Rugby AUS"),
]


def discover_filters():
    """Re-read competition and team ids from the fixtures page's SSR props.

    Not used by the build - it is the tool for when ids stop matching.
    """
    import urllib.request
    req = urllib.request.Request(FIXTURES_PAGE, headers={"User-Agent": http.USER_AGENT})
    with urllib.request.urlopen(req, timeout=http.TIMEOUT) as r:
        html = r.read().decode("utf-8", "replace")
    blob = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    data = json.loads(blob.group(1))
    document = data["props"]["pageProps"]["pageData"]["content"]["document"]
    return document[0]["props"]["competitions"]


def fetch(team_id, comps, limit=200):
    """Upcoming fixtures for one team across the given competition ids.

    The endpoint's `type` argument is lower-case "fixtures"; omitting it gives
    the same upcoming list, which is what a subscription wants.
    """
    payload = {
        "operationName": "FixturesAndResults",
        "query": QUERY,
        "variables": {
            "comps": [{"id": comp_id, "sourceType": "1"} for comp_id, _ in comps],
            "teams": [team_id],
            "type": "fixtures",
            "skip": 0,
            "limit": limit,
        },
    }
    body = http.post_json(GRAPHQL, payload, headers={"Origin": "https://www.rugby.com.au"})
    if body.get("errors"):
        raise RuntimeError("rugby graphql errors: %s" % json.dumps(body["errors"])[:400])
    return (body.get("data") or {}).get("getFixtureItems") or []


def _parse(stamp):
    # Rugby AU returns "2026-11-08T15:10:00+0000".
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            parsed = dt.datetime.strptime(stamp, fmt)
        except ValueError:
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    raise ValueError("unparseable rugby dateTime: %r" % stamp)


def to_matches(fixtures, categories, duration_minutes=120):
    out = []
    for fixture in fixtures:
        if fixture.get("isBye"):
            continue
        home = (fixture.get("homeTeam") or {}).get("name") or "TBC"
        away = (fixture.get("awayTeam") or {}).get("name") or "TBC"
        venue = fixture.get("venue") or ""
        competition = fixture.get("compName") or ""
        round_label = fixture.get("roundLabel") or fixture.get("round") or ""

        # Rugby AU parks a fixture whose kick-off is not settled at exactly
        # midnight UTC. No real kick-off lands there - 00:00 UTC is 11am in
        # Sydney and 1am in Europe - so treat it as a date-only placeholder.
        start = _parse(fixture["dateTime"])
        time_tbc = start.astimezone(dt.timezone.utc).time() == dt.time(0, 0)
        tentative = (not venue) or time_tbc or "TBC" in (home + away)

        summary = "%s v %s" % (home, away)
        if competition and competition != "International":
            summary += " — " + competition
        if tentative:
            summary += " [time TBC]" if time_tbc and venue else " [TBC]"

        description = [competition]
        if round_label:
            description.append(str(round_label))
        if fixture.get("matchLabel"):
            description.append(fixture["matchLabel"])
        if time_tbc:
            description.append(
                "Kick-off time not yet announced - the time shown is a placeholder.")
        elif tentative:
            description.append("Date or venue not yet confirmed.")
        description += ["", "Source: rugby.com.au"]

        out.append(Match(
            uid_seed="rugby:%s" % fixture["id"],
            summary=summary,
            start=start,
            duration_minutes=duration_minutes,
            location=venue,
            description="\n".join(p for p in description if p is not None),
            url=FIXTURES_PAGE,
            categories=categories,
            tentative=tentative,
        ))
    return out


def wallabies(duration_minutes=120):
    return to_matches(fetch(WALLABIES, WALLABIES_COMPS),
                      ["Rugby", "Wallabies"], duration_minutes)


def brumbies(duration_minutes=120):
    return to_matches(fetch(BRUMBIES, BRUMBIES_COMPS),
                      ["Rugby", "Brumbies"], duration_minutes)
