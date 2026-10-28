"""The one shape every source normalises to."""

import datetime as dt


class Match(object):
    """A single calendar-worthy event.

    uid_seed must be stable for the life of the fixture: it is what stops a
    calendar app creating a duplicate when a kick-off time moves.
    """

    def __init__(self, uid_seed, summary, start, duration_minutes,
                 location=None, description=None, url=None,
                 categories=None, tentative=False):
        self.uid_seed = uid_seed
        self.summary = summary
        self.start = start                      # aware datetime, any tz
        self.duration_minutes = duration_minutes
        self.location = location or ""
        self.description = description or ""
        self.url = url or ""
        self.categories = categories or []
        self.tentative = tentative

    @property
    def end(self):
        return self.start + dt.timedelta(minutes=self.duration_minutes)

    def fingerprint(self):
        """Everything a viewer would notice. Drives SEQUENCE bumps."""
        return "|".join([
            self.summary,
            self.start.astimezone(dt.timezone.utc).isoformat(),
            str(self.duration_minutes),
            self.location,
            self.description,
            self.url,
            "T" if self.tentative else "F",
        ])

    def __repr__(self):
        return "<Match %s %s>" % (self.start.isoformat(), self.summary)
