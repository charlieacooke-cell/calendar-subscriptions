"""RFC 5545 writer.

Deliberately hand-rolled: the whole job is a few hundred lines of correct
folding and escaping, and a stdlib-only build keeps CI to a bare python step.
"""

import datetime as dt
import hashlib

UID_DOMAIN = "calendar-subscriptions.charliecooke.github.io"


def _esc(text):
    return (text.replace("\\", "\\\\")
                .replace(";", "\;")
                .replace(",", "\\,")
                .replace("\r\n", "\\n")
                .replace("\n", "\\n"))


def _fold(line):
    """Fold to 75 octets per RFC 5545, counting bytes rather than characters."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    out, start = [], 0
    limit = 75
    while start < len(raw):
        end = min(start + limit, len(raw))
        # Never split a multi-byte character.
        while end > start and end < len(raw) and (raw[end] & 0xC0) == 0x80:
            end -= 1
        out.append(raw[start:end].decode("utf-8"))
        start = end
        limit = 74          # continuation lines carry a leading space
    return "\r\n ".join(out)


def _utc(when):
    return when.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def uid_for(seed):
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:20]
    return "%s@%s" % (digest, UID_DOMAIN)


def render(matches, name, description, sequences=None, now=None):
    """Render a VCALENDAR.

    sequences maps uid -> {"hash": str, "seq": int} and is mutated in place so
    the caller can persist it. A fixture whose details change gets a higher
    SEQUENCE, which is what makes calendar apps accept the update.
    """
    sequences = sequences if sequences is not None else {}
    now = now or dt.datetime.now(dt.timezone.utc)
    stamp = _utc(now)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//charliecooke//Calendar Subscriptions//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:" + _esc(name),
        "X-WR-CALDESC:" + _esc(description),
        "X-WR-TIMEZONE:Australia/Sydney",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]

    for match in sorted(matches, key=lambda m: (m.start, m.summary)):
        uid = uid_for(match.uid_seed)
        fingerprint = hashlib.sha1(match.fingerprint().encode("utf-8")).hexdigest()
        record = sequences.get(uid)
        if record is None:
            record = sequences[uid] = {"hash": fingerprint, "seq": 0}
        elif record["hash"] != fingerprint:
            record["hash"] = fingerprint
            record["seq"] = record["seq"] + 1
        record["seen"] = now.date().isoformat()
        seq = record["seq"]

        lines += [
            "BEGIN:VEVENT",
            "UID:" + uid,
            "DTSTAMP:" + stamp,
            "DTSTART:" + _utc(match.start),
            "DTEND:" + _utc(match.end),
            "SEQUENCE:%d" % seq,
            "SUMMARY:" + _esc(match.summary),
            "STATUS:" + ("TENTATIVE" if match.tentative else "CONFIRMED"),
            # Sport should not make you look busy.
            "TRANSP:TRANSPARENT",
        ]
        if match.location:
            lines.append("LOCATION:" + _esc(match.location))
        if match.description:
            lines.append("DESCRIPTION:" + _esc(match.description))
        if match.url:
            lines.append("URL:" + match.url)
        if match.categories:
            lines.append("CATEGORIES:" + ",".join(_esc(c) for c in match.categories))
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in lines) + "\r\n"
