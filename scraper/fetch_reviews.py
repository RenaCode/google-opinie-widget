#!/usr/bin/env python3
"""
Fetch Google reviews with NO API KEY by driving a real browser
(Playwright/Chromium). It opens the business' public Google Maps profile, enters
the "Reviews" tab, scrolls the list and reads the reviews straight from the
rendered page — the same way a normal visitor sees them.

Designed DEFENSIVELY: if Google changes its layout or anything goes wrong, the
script does NOT overwrite the previous file with empty data. The old reviews stay
and the site keeps showing them. So there is nothing to "maintain" — worst case
the reviews stop refreshing, but nothing breaks.

Runs in the background in a Docker container (see deploy/docker/).
"""
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Paths can be overridden by env vars so a VPS can keep its REAL config (CID,
# business name) private, outside this public repo, and write the JSON wherever
# it is served from. Defaults point to the repo's generic example files.
CONFIG_PATH = os.environ.get("REVIEWS_CONFIG", os.path.join(ROOT, "config.json"))
OUT_PATH = os.environ.get("REVIEWS_OUT", os.path.join(ROOT, "data", "reviews.json"))

# Pre-set cookie consent so we skip the consent.google.com redirect.
CONSENT_COOKIE = {
    "name": "SOCS",
    "value": "CAISNQgDEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjQwMTA5LjA2X3AwGAEgACgD",
    "domain": ".google.com",
    "path": "/",
}

# Button labels per language (Google's own UI text). Add your locale if needed.
CONSENT_LABELS = ("Zaakceptuj wszystko", "Accept all", "Odrzuć wszystko", "Reject all")
REVIEWS_TAB = ('button[aria-label^="Opinie"]', 'button[aria-label*="opinii"]',
               'button[aria-label^="Reviews"]', 'button[aria-label*="reviews"]',
               'button[jsaction*="reviewChart"]',
               'button:has-text("Opinie")', 'button:has-text("Reviews")')
MORE_BTN = ('button:has-text("Więcej")', 'button:has-text("More")',
            'button[aria-label="Zobacz więcej"]', 'button[aria-label="See more"]')


def log(*a):
    print("[reviews]", *a, flush=True)


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_existing():
    try:
        with open(OUT_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_json(obj):
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def digits(s):
    return re.sub(r"[^\d]", "", s or "")


def _open_reviews(page):
    """Try hard to open the reviews list. Returns the number of review cards."""
    selectors = (
        'button[role="tab"][aria-label*="Opinie"]',
        'button[role="tab"]:has-text("Opinie")',
        'button[aria-label^="Opinie"]',
        'button[jsaction*="reviewChart"]',
        'button:has-text("Opinie")',
        'button[role="tab"][aria-label*="Reviews"]',
        'button:has-text("Reviews")',
    )
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.count():
                el.click(timeout=4000)
                page.wait_for_timeout(500)
                try:
                    page.wait_for_selector("div.jftiEf", timeout=6000)
                except Exception:
                    pass
                if page.locator("div.jftiEf").count():
                    return page.locator("div.jftiEf").count()
        except Exception:
            continue
    return page.locator("div.jftiEf").count()


def _extract(page, max_reviews):
    """Scroll the open reviews list and read the cards."""
    feed = None
    for sel in ('div[role="feed"]', 'div.m6QErb[aria-label]', "div.m6QErb"):
        loc = page.locator(sel)
        if loc.count():
            feed = loc.last
            break

    last = 0
    for _ in range(30):
        n = page.locator("div.jftiEf").count()
        if n >= max_reviews:
            break
        if feed is not None:
            try:
                feed.evaluate("el => el.scrollBy(0, el.scrollHeight)")
            except Exception:
                page.mouse.wheel(0, 4000)
        else:
            page.mouse.wheel(0, 4000)
        page.wait_for_timeout(1200)
        if n == last:
            page.wait_for_timeout(1000)
            if page.locator("div.jftiEf").count() == n:
                break
        last = n

    # expand truncated reviews ("More")
    try:
        buttons = []
        for sel in MORE_BTN:
            buttons += page.locator(sel).all()
        for b in buttons[:max_reviews]:
            try:
                b.click(timeout=800)
            except Exception:
                pass
    except Exception:
        pass

    out = []
    cards = page.locator("div.jftiEf")
    total = min(cards.count(), max_reviews)
    for i in range(total):
        c = cards.nth(i)
        try:
            author = c.locator("div.d4r55").first.inner_text(timeout=1500).strip()
        except Exception:
            author = ""
        stars = 0
        try:
            al = c.locator('span.kvMYJc, span[role="img"]').first.get_attribute("aria-label") or ""
            m = re.search(r"([1-5])", al)
            if m:
                stars = int(m.group(1))
        except Exception:
            pass
        text = ""
        for tsel in ("span.wiI7pd", "div.MyEned span", "span.review-full-text"):
            try:
                loc = c.locator(tsel).first
                if loc.count():
                    text = loc.inner_text(timeout=1000).strip()
                    if text:
                        break
            except Exception:
                continue
        when = ""
        try:
            when = c.locator("span.rsqaWe").first.inner_text(timeout=800).strip()
        except Exception:
            pass
        if text and stars:
            out.append({"author": author or "Klient Google",
                        "rating": stars, "text": text, "when": when})
    return out


def scrape(cid, lang, country, max_reviews, attempts=5):
    """Return (rating, count, [reviews]) or raise.

    Google intermittently serves a reviews-less "limited view" to automated
    browsers. We retry with a fresh context until the full panel (with a reviews
    list) shows up, then read it. If every attempt only yields the limited view,
    we return whatever aggregate rating we could read and no reviews — the caller
    then keeps the previous good data.
    """
    from playwright.sync_api import sync_playwright

    url = f"https://www.google.com/maps?cid={cid}&hl={lang}&gl={country}"
    rating = count = None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled",
                  "--lang=" + lang],
        )
        try:
            for attempt in range(1, attempts + 1):
                ctx = browser.new_context(
                    locale=f"{lang}-{country.upper()}",
                    timezone_id="Europe/Warsaw",
                    user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/125.0.0.0 Safari/537.36"),
                    viewport={"width": 1360, "height": 1800},
                )
                ctx.add_cookies([CONSENT_COOKIE])
                page = ctx.new_page()
                page.set_default_timeout(30000)
                try:
                    page.goto(url, wait_until="domcontentloaded")

                    # dismiss a consent banner if one still shows up
                    try:
                        for label in CONSENT_LABELS:
                            btn = page.get_by_role("button", name=label)
                            if btn.count():
                                btn.first.click(timeout=3000)
                                page.wait_for_timeout(1500)
                                break
                    except Exception:
                        pass

                    # aggregate rating + review count (place panel)
                    try:
                        page.wait_for_selector("div.F7nice, div.fontDisplayLarge", timeout=20000)
                        blob = page.locator("div.F7nice").first.inner_text(timeout=5000)
                        m = re.search(r"([0-9][.,][0-9])", blob)
                        if m:
                            rating = m.group(1).replace(",", ".")
                        m = re.search(r"([0-9][0-9\s .]{1,9})\s*(?:opin|review)", blob, re.I)
                        if m:
                            count = digits(m.group(1))
                    except Exception as e:
                        log(f"attempt {attempt}: aggregate not read ({e})")

                    page.wait_for_timeout(1500)
                    limited = False
                    try:
                        body = page.locator("body").inner_text(timeout=3000)
                        limited = ("ograniczonego widoku" in body
                                   or "limited view" in body.lower())
                    except Exception:
                        pass

                    n = _open_reviews(page)
                    if n:
                        reviews = _extract(page, max_reviews)
                        if reviews:
                            log(f"attempt {attempt}: full view, {len(reviews)} reviews")
                            return rating, count, reviews
                    log(f"attempt {attempt}: no reviews "
                        f"({'limited view' if limited else 'full view but 0 cards'}) — retrying")
                finally:
                    ctx.close()
                time.sleep(2)
        finally:
            browser.close()

    return rating, count, []



def main():
    cfg = load_config()
    cid = str(cfg["cid"]).strip()
    lang = cfg.get("lang", "pl")
    country = cfg.get("country", "pl")
    max_reviews = int(cfg.get("max_reviews", 40))
    existing = load_existing()

    rating = count = None
    reviews = []
    try:
        rating, count, reviews = scrape(cid, lang, country, max_reviews)
        log(f"rating={rating} count={count} fetched_reviews={len(reviews)}")
    except Exception as e:
        log(f"scraping failed: {type(e).__name__}: {e}")

    # DEFENSE: no reviews -> do not overwrite the old file with empty data.
    if not reviews:
        if existing:
            changed = False
            if rating:
                existing["rating"] = rating; changed = True
            if count:
                existing["count"] = count; changed = True
            if changed:
                existing["updated"] = int(time.time())
                write_json(existing)
                log("Updated aggregate rating only; reviews unchanged.")
            else:
                log("No new data — file unchanged (site shows last good reviews).")
            return 0
        log("No reviews and no previous file — not writing empty data.")
        return 1

    payload = {
        "name": cfg.get("name", ""),
        "cid": cid,
        "url": f"https://www.google.com/maps?cid={cid}",
        "rating": rating or (existing or {}).get("rating") or "",
        "count": count or (existing or {}).get("count") or str(len(reviews)),
        "updated": int(time.time()),
        "reviews": reviews,
    }
    write_json(payload)
    log(f"Wrote {len(reviews)} reviews to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
