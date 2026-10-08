"""Tests for the reviews proxy. Stdlib only: python -m unittest discover tests"""
import http.client
import json
import os
import sys
import threading
import unittest
import urllib.error
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "charts", "google-opinie", "server"))
import opinie_proxy as p  # noqa: E402

ORIGIN = "https://example.com"

PLACE = {
    "displayName": {"text": "Example Business"},
    "rating": 4.8,
    "userRatingCount": 37,
    "googleMapsUri": "https://maps.google.com/?cid=1",
    "reviews": [{
        "rating": 5,
        "text": {"text": "Great"},
        "relativePublishTimeDescription": "a month ago",
        "authorAttribution": {"displayName": "Jan K.", "uri": "https://www.google.com/maps/contrib/1",
                              "photoUri": "https://lh3.googleusercontent.com/a"},
        "googleMapsUri": "https://www.google.com/maps/reviews/1",
        "flagContentUri": "https://www.google.com/local/review/rap/report?1",
    }],
}


def config(**over):
    env = {"GOOGLE_PLACES_API_KEY": "k", "PLACE_ID": "ChIJ1", "ALLOWED_ORIGINS": ORIGIN + "/"}
    env.update(over)
    return p.Config(env)


class ProxyCase(unittest.TestCase):
    def start(self, fetch, budget=None):
        self.calls = []

        def counting(cfg):
            self.calls.append(cfg)
            return fetch(cfg)

        handler = p.make_handler(config(), budget or p.Budget(100, 100), counting)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def get(self, path, origin=ORIGIN, method="GET"):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        conn.request(method, path, headers={"Origin": origin} if origin else {})
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp, (json.loads(body) if body else None)

    def test_allowed_origin_gets_live_data_uncached(self):
        self.start(lambda cfg: PLACE)
        resp, body = self.get("/v1/reviews")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.getheader("Access-Control-Allow-Origin"), ORIGIN)
        self.assertEqual(resp.getheader("Cache-Control"), "no-store")
        self.assertEqual(body["count"], 37)
        r = body["reviews"][0]
        # attribution fields required by Google's policies survive normalization
        self.assertEqual(r["author"], "Jan K.")
        self.assertTrue(r["authorUri"] and r["authorPhoto"] and r["reviewUri"] and r["flagUri"])
        self.assertEqual(len(self.calls), 1)

    def test_every_request_hits_google_no_cache(self):
        self.start(lambda cfg: PLACE)
        self.get("/v1/reviews")
        self.get("/v1/reviews")
        self.assertEqual(len(self.calls), 2)

    def test_foreign_or_missing_origin_never_reaches_google(self):
        self.start(lambda cfg: PLACE)
        for origin in ("https://evil.example", None, "https://example.com.evil.example"):
            resp, _ = self.get("/v1/reviews", origin=origin)
            self.assertEqual(resp.status, 403, origin)
            self.assertIsNone(resp.getheader("Access-Control-Allow-Origin"))
        self.assertEqual(self.calls, [])

    def test_preflight(self):
        self.start(lambda cfg: PLACE)
        resp, _ = self.get("/v1/reviews", method="OPTIONS")
        self.assertEqual(resp.status, 204)
        self.assertEqual(resp.getheader("Access-Control-Allow-Origin"), ORIGIN)
        resp, _ = self.get("/v1/reviews", origin="https://evil.example", method="OPTIONS")
        self.assertEqual(resp.status, 403)
        self.assertEqual(self.calls, [])

    def test_budget_exhausted_returns_503_without_calling_google(self):
        self.start(lambda cfg: PLACE, budget=p.Budget(per_minute=1, per_day=100))
        self.assertEqual(self.get("/v1/reviews")[0].status, 200)
        resp, _ = self.get("/v1/reviews")
        self.assertEqual(resp.status, 503)
        self.assertEqual(resp.getheader("Access-Control-Allow-Origin"), ORIGIN)
        self.assertEqual(len(self.calls), 1)

    def test_upstream_error_is_502(self):
        def boom(cfg):
            raise urllib.error.URLError("down")
        self.start(boom)
        self.assertEqual(self.get("/v1/reviews")[0].status, 502)

    def test_healthz_and_head_do_not_call_google(self):
        self.start(lambda cfg: PLACE)
        self.assertEqual(self.get("/healthz", origin=None)[0].status, 200)
        self.assertEqual(self.get("/v1/reviews", method="HEAD")[0].status, 501)
        self.assertEqual(self.calls, [])


class BudgetCase(unittest.TestCase):
    def test_minute_and_day_windows(self):
        now = [0.0]
        b = p.Budget(per_minute=2, per_day=3, clock=lambda: now[0])
        self.assertTrue(b.take())
        self.assertTrue(b.take())
        self.assertFalse(b.take())          # minute cap
        now[0] = 61
        self.assertTrue(b.take())
        self.assertFalse(b.take())          # day cap (3)
        now[0] = 86400 + 1
        self.assertTrue(b.take())           # new day


class FetchCase(unittest.TestCase):
    def test_request_shape(self):
        seen = {}

        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, *a):
                return b"{}"

        def opener(req, timeout):
            seen["url"], seen["headers"] = req.full_url, dict(req.header_items())
            return Resp()

        p.fetch_place(config(), opener=opener)
        self.assertTrue(seen["url"].startswith("https://places.googleapis.com/v1/places/ChIJ1?"))
        self.assertIn("languageCode=pl", seen["url"])
        self.assertNotIn("key=", seen["url"])  # key travels in a header, never in the URL
        self.assertEqual(seen["headers"]["X-goog-api-key"], "k")
        self.assertIn("reviews", seen["headers"]["X-goog-fieldmask"])

    def test_config_requires_key_place_and_origins(self):
        self.assertEqual(p.Config({}).missing(), ["GOOGLE_PLACES_API_KEY", "PLACE_ID", "ALLOWED_ORIGINS"])
        self.assertEqual(config().origins, {ORIGIN})


if __name__ == "__main__":
    unittest.main()
