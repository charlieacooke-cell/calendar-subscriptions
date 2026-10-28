"""Minimal stdlib HTTP helpers. No third-party dependencies, so CI needs no install step."""

import json
import urllib.error
import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

TIMEOUT = 45


def _open(req, attempts=3):
    last = None
    for i in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read()
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            last = exc
    raise RuntimeError("request failed after %d attempts: %s" % (attempts, last))


def get_json(url, headers=None):
    req = urllib.request.Request(url, headers=dict({"User-Agent": USER_AGENT}, **(headers or {})))
    return json.loads(_open(req).decode("utf-8"))


def post_json(url, payload, headers=None):
    body = json.dumps(payload).encode("utf-8")
    base = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=body, headers=dict(base, **(headers or {})), method="POST")
    return json.loads(_open(req).decode("utf-8"))
