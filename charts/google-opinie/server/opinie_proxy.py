#!/usr/bin/env python3
"""
Google reviews proxy — official Places API (New), standard library only.

The browser widget cannot call the Places API itself without exposing the API
key, so this tiny server holds the key and forwards ONE request per page view:

    widget  --GET /v1/reviews-->  this proxy  --Place Details (New)-->  Google

It deliberately stores NOTHING. The Google Maps Platform terms forbid caching
or storing Places content (only place IDs may be kept), so every response is
fetched live and sent with `Cache-Control: no-store`. To keep the bill bounded
instead, the proxy:

  * answers only browsers from ALLOWED_ORIGINS (others never reach Google),
  * caps upstream calls per minute and per day (counters, not content),
  * returns 503 when a cap is hit — the widget then keeps its HTML fallback.

The in-process caps reset on restart, so they are a brake, not a guarantee.
The hard ceiling is a daily quota on the API in Google Cloud (see README).

Configuration (environment):
  GOOGLE_PLACES_API_KEY  required  server key, restricted to Places API (New)
  PLACE_ID               required  e.g. ChIJ... (Google's Place ID Finder)
  ALLOWED_ORIGINS        required  comma-separated, e.g. https://example.com
  LANGUAGE               pl        language of review texts and labels
  REGION                 PL        region code
  DAILY_LIMIT            300       max upstream calls per UTC day
  MINUTE_LIMIT           20        max upstream calls per minute
  PORT                   8080
"""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PLACES_URL = "https://places.googleapis.com/v1/places/"
# Only what the widget renders. The field mask decides the billed SKU:
# `reviews` puts the call in "Place Details Enterprise + Atmosphere".
FIELD_MASK = "displayName,rating,userRatingCount,googleMapsUri,reviews"
UPSTREAM_TIMEOUT = 8


def log(*a):
    print("[opinie]", *a, flush=True)


class Config:
    def __init__(self, env):
        self.api_key = env.get("GOOGLE_PLACES_API_KEY", "").strip()
        self.place_id = env.get("PLACE_ID", "").strip()
        self.origins = {o.strip().rstrip("/") for o in
                        env.get("ALLOWED_ORIGINS", "").split(",") if o.strip()}
        self.language = env.get("LANGUAGE", "pl").strip()
        self.region = env.get("REGION", "PL").strip()
        self.daily_limit = int(env.get("DAILY_LIMIT", "300"))
        self.minute_limit = int(env.get("MINUTE_LIMIT", "20"))
        self.port = int(env.get("PORT", "8080"))

    def missing(self):
        return [name for name, val in (("GOOGLE_PLACES_API_KEY", self.api_key),
                                       ("PLACE_ID", self.place_id),
                                       ("ALLOWED_ORIGINS", self.origins)) if not val]


class Budget:
    """Upstream call counters per minute and per UTC day. Thread-safe."""

    def __init__(self, per_minute, per_day, clock=time.time):
        self.per_minute, self.per_day, self.clock = per_minute, per_day, clock
        self.lock = threading.Lock()
        self.minute = self.day = None
        self.minute_used = self.day_used = 0

    def take(self):
        now = self.clock()
        minute, day = int(now // 60), int(now // 86400)
        with self.lock:
            if minute != self.minute:
                self.minute, self.minute_used = minute, 0
            if day != self.day:
                self.day, self.day_used = day, 0
            if self.minute_used >= self.per_minute or self.day_used >= self.per_day:
                return False
            self.minute_used += 1
            self.day_used += 1
            return True


def fetch_place(cfg, opener=urllib.request.urlopen):
    """One live Place Details (New) call. Returns the parsed JSON."""
    query = urllib.parse.urlencode({"languageCode": cfg.language,
                                    "regionCode": cfg.region})
    req = urllib.request.Request(
        PLACES_URL + urllib.parse.quote(cfg.place_id, safe="") + "?" + query,
        headers={"X-Goog-Api-Key": cfg.api_key, "X-Goog-FieldMask": FIELD_MASK})
    with opener(req, timeout=UPSTREAM_TIMEOUT) as resp:
        return json.load(resp)


def normalize(place):
    """Reduce Google's response to what the widget needs, keeping every field
    the attribution rules require (author name/photo/profile, review link,
    report link, place link)."""
    reviews = []
    for r in place.get("reviews") or []:
        author = r.get("authorAttribution") or {}
        text = (r.get("text") or {}).get("text") or (r.get("originalText") or {}).get("text") or ""
        reviews.append({
            "author": author.get("displayName") or "",
            "authorUri": author.get("uri") or "",
            "authorPhoto": author.get("photoUri") or "",
            "rating": r.get("rating") or 0,
            "text": text,
            "when": r.get("relativePublishTimeDescription") or "",
            "reviewUri": r.get("googleMapsUri") or "",
            "flagUri": r.get("flagContentUri") or "",
        })
    return {
        "name": (place.get("displayName") or {}).get("text") or "",
        "rating": place.get("rating"),
        "count": place.get("userRatingCount"),
        "url": place.get("googleMapsUri") or "",
        "reviews": reviews,
    }


def make_handler(cfg, budget, fetch=fetch_place):
    class Handler(BaseHTTPRequestHandler):
        server_version = "opinie"
        sys_version = ""

        def log_message(self, fmt, *args):
            pass  # access log off; errors are logged explicitly

        def _send(self, status, body, origin=None):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            # Places content must not be cached — not by browsers, not by proxies.
            self.send_header("Cache-Control", "no-store")
            self.send_header("Vary", "Origin")
            if origin:
                self.send_header("Access-Control-Allow-Origin", origin)
            self.end_headers()
            self.wfile.write(data)

        def _origin(self):
            origin = (self.headers.get("Origin") or "").rstrip("/")
            return origin if origin in cfg.origins else None

        def do_OPTIONS(self):
            origin = self._origin()
            if not origin:
                return self._send(403, {"error": "origin not allowed"})
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET")
            self.send_header("Access-Control-Max-Age", "86400")
            self.send_header("Vary", "Origin")
            self.end_headers()

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/healthz":
                return self._send(200, {"ok": True})
            if path != "/v1/reviews":
                return self._send(404, {"error": "not found"})
            origin = self._origin()
            if not origin:
                return self._send(403, {"error": "origin not allowed"})
            if not budget.take():
                log("budget exhausted — answering 503 without calling Google")
                return self._send(503, {"error": "busy"}, origin)
            try:
                place = fetch(cfg)
            except urllib.error.HTTPError as e:
                detail = e.read(500).decode("utf-8", "replace")
                log(f"Places API HTTP {e.code}: {detail}")
                return self._send(502, {"error": "upstream"}, origin)
            except Exception as e:  # network, timeout, bad JSON
                log(f"Places API failed: {type(e).__name__}: {e}")
                return self._send(502, {"error": "upstream"}, origin)
            return self._send(200, normalize(place), origin)

    return Handler


def main():
    cfg = Config(os.environ)
    missing = cfg.missing()
    if missing:
        log("missing configuration: " + ", ".join(missing))
        return 2
    budget = Budget(cfg.minute_limit, cfg.daily_limit)
    server = ThreadingHTTPServer(("", cfg.port), make_handler(cfg, budget))
    log(f"listening on :{cfg.port}; origins={sorted(cfg.origins)} "
        f"limits={cfg.minute_limit}/min {cfg.daily_limit}/day")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
