# Google Reviews Widget — self-hosted, free, no API key

A standalone widget that shows your Google Business Profile reviews on your own
website. Written from scratch as a **free alternative to paid review plugins**
(Elfsight, Trustindex, etc.) — no API key, no vendor branding, no subscription.

> The on-page labels are Polish by default (built for a Polish business).
> Change the strings in `widget/opinie.js` for another language.

## How it works

```
Docker container (on your server, every 12h)
        |
        |  headless browser (Playwright/Chromium) reads the public Maps profile
        v
   reviews.json  --FTP-->  your website  <--same-origin fetch--  widget on the page
```

- **No API key.** Reviews are read from the public Google Maps profile by driving
  a real headless browser — the same page any visitor sees. Google blocks keyless
  access to its review *API* endpoints (HTTP 403), so the widget renders the page.
- **One container, nothing loose on the host.** The fetcher runs as a single
  always-on Docker container. It scrapes, then uploads `reviews.json` to your
  site over FTP(S).
- **On your site** there is only a lightweight `<div>`, one `<script>`, and the
  uploaded `reviews.json` — all served from your own domain (same origin, no CORS,
  no third-party CDN, no runtime dependency on GitHub).
- **It never breaks the site.** If Google changes its layout and scraping stops
  working, the scraper **does not overwrite** the cached data — the site keeps
  showing the last good reviews. Worst case they stop refreshing; the site is fine.

## 1. Put the widget on your site

Upload `widget/opinie.js` to your site (e.g. as `/opinie.js`) and add this where
you want the reviews:

```html
<div id="google-opinie" data-stars="5" data-max="6" data-src="/reviews.json">
  <!-- optional: fallback content, shown if the data fails to load -->
</div>
<script src="/opinie.js" defer></script>
```

Container attributes:

| attribute | default | meaning |
|---|---|---|
| `data-stars` | `5` | show only reviews rated >= this many stars |
| `data-max` | `6` | maximum number of reviews to display |
| `data-src` | `reviews.json` | where to fetch the data from (same origin) |
| `data-btn-class` | `btn btn-primary` | CSS class for the "see all" button |

The widget inherits the site's colors from CSS variables (`--accent`, `--text`,
`--surface`, ...), so it blends into any design automatically.

## 2. Run the fetcher (Docker)

On your server:

```bash
cd deploy/docker
cp config.example.json config.json   # edit: real CID + business name
cp .env.example .env                  # edit: FTP target + credentials
docker compose up -d --build
```

- `config.json` and `.env` stay **on your server only** — they are gitignored and
  never pushed to this public repo.
- The container runs the fetch + upload immediately, then every
  `INTERVAL_SECONDS` (default 12h). Check logs with `docker compose logs -f`.

### How to find the CID

Open the business profile in Google Maps -> in the URL find `...?cid=NUMBER`.
Paste that number into `config.json`.

## Configuration reference

`deploy/docker/config.json` (private, on the server):

```json
{
  "cid": "PUT_YOUR_GOOGLE_CID_HERE",
  "name": "Your Business Name",
  "lang": "pl",
  "country": "pl",
  "max_reviews": 40,
  "min_stars_default": 5
}
```

`deploy/docker/.env` (private, on the server): `INTERVAL_SECONDS`,
`REVIEWS_FTP_URL`, `REVIEWS_FTP_USER`, `REVIEWS_FTP_PASS` — see `.env.example`.

## Legal / technical note

Data comes from the publicly visible Google profile (what any Maps visitor sees).
Real, public reviews are quoted with their author's name. The officially supported
source is the Google Places API — but it requires a key and can be billed. This
widget deliberately takes the "no key" route, accepting that the scraper may need
an occasional fix if Google changes its page. The only file that would ever need a
tweak is `scraper/fetch_reviews.py`.
