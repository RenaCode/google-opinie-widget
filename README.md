# Google Reviews Widget — self-hosted, official API

A standalone widget that shows your Google Business Profile reviews on your own
website, without a paid review plugin or vendor branding. Data comes from the
official **Google Places API (New)**, called through a tiny proxy that keeps the
API key on your server.

> The on-page labels are Polish by default (built for a Polish business).
> Change the strings in `TXT` in `widget/opinie.js` for another language — but
> leave the words **Google Maps** untouched (see *Terms compliance*).

## How it works

```
visitor's browser                     your cluster                       Google
widget (opinie.js) --GET /v1/reviews--> proxy (holds API key) --Place Details (New)--> Places API
                   <---- JSON, no-store ----                  <------------ live data ----
```

- **The key never reaches the browser.** It lives in a Kubernetes Secret and is
  sent to Google in a header from the proxy only.
- **Nothing is cached or stored.** Every page view that scrolls to the widget
  makes one live API call; responses carry `Cache-Control: no-store`. This is
  what the Google Maps Platform terms require for Places content.
- **Cost is bounded, not unlimited.** The proxy answers only the websites listed
  in `allowedOrigins`, caps calls per minute and per day, and the widget fetches
  only when its section is about to scroll into view. Put a hard quota on the
  API in Google Cloud as well (below) — the in-process counters reset on restart.
- **It never breaks the site.** Any failure (quota, network, Google error) leaves
  the fallback HTML that sits inside the widget container.
- **Up to 5 reviews.** The Places API returns at most five reviews per place,
  chosen by Google by relevance. That is all any API-based widget can show.

## 1. Google Cloud: key and quota

1. Enable **Places API (New)** in a Google Cloud project with billing.
2. Create an API key and restrict it:
   - *API restrictions*: Places API (New) only,
   - *Application restrictions*: IP addresses → the public egress IP of your server.
3. **Quotas** → Places API (New) → set a *requests per day* limit (e.g. 300).
   This is the hard ceiling on the bill.
4. Find your Place ID (`ChIJ...`) with Google's
   [Place ID Finder](https://developers.google.com/maps/documentation/places/web-service/place-id).

Pricing: a Place Details call that includes `reviews` is billed as
*Place Details Enterprise + Atmosphere* — 1,000 calls per month free, then
billed per 1,000 calls. Check the current
[price list](https://developers.google.com/maps/billing-and-pricing/pricing).

## 2. Run the proxy (Helm)

```bash
kubectl create secret generic google-opinie \
  --from-literal=GOOGLE_PLACES_API_KEY='...' \
  --from-literal=PLACE_ID='ChIJ...'

helm upgrade --install google-opinie charts/google-opinie \
  --set ingress.host=reviews.example.com \
  --set 'config.allowedOrigins={https://example.com,https://www.example.com}'
```

The chart runs stock `python:3.12-slim` with the proxy code mounted from a
ConfigMap (stdlib only, no image to build), behind Traefik with a cert-manager
certificate. See `charts/google-opinie/values.yaml` for all settings.

Check it:

```bash
curl -s https://reviews.example.com/healthz
curl -s -H 'Origin: https://example.com' https://reviews.example.com/v1/reviews
```

## 3. Put the widget on your site

Upload `widget/opinie.js` to your site (e.g. as `/opinie.js`) and add:

```html
<div id="google-opinie" data-src="https://reviews.example.com/v1/reviews">
  <!-- optional: fallback content, shown if the data fails to load -->
</div>
<script src="/opinie.js" defer></script>
```

| attribute | default | meaning |
|---|---|---|
| `data-src` | — | proxy URL (required) |
| `data-stars` | `1` | show only reviews rated >= this many stars (see below) |
| `data-max` | `5` | maximum number of reviews to display |
| `data-btn-class` | `btn btn-primary` | CSS class for the "see all" button |

The widget inherits the site's colors from CSS variables (`--accent`, `--text`,
`--surface`, ...). If the site sends a Content-Security-Policy, allow the proxy
in `connect-src` and `https://*.googleusercontent.com` in `img-src` (reviewer
avatars).

Local preview without the API: open `examples/embed-example.html` through any
static server (it reads the fake `examples/sample-response.json`).

## Terms compliance

What the code does to follow the
[Places API policies](https://developers.google.com/maps/documentation/places/web-service/policies)
and the [Google Maps Platform Service Specific Terms](https://cloud.google.com/maps-platform/terms/maps-service-terms):

- **No caching or storage** of Places content — live call per view, `no-store`.
  Only the Place ID is kept (explicitly allowed).
- **"Google Maps" attribution** shown in the widget's container, unmodified and
  untranslated.
- **Author attribution** for every review: name linked to the author's profile,
  avatar (initials if the photo can't load).
- **Link to each review on Google Maps** (`googleMapsUri`) and a **"report"**
  link (`flagContentUri`).
- **Notice of ordering and filtering**: the widget states that Google chose the
  reviews by relevance, and says so when a star filter is active.
- Used without a map, which the terms allow for Places data; it must not be
  shown on a non-Google map.

Your responsibilities as the site operator:

- **Don't cherry-pick.** EU consumer law (Omnibus Directive; in Poland
  *ustawa o przeciwdziałaniu nieuczciwym praktykom rynkowym*) treats presenting
  reviews selectively in a misleading way as an unfair practice. That is why
  `data-stars` defaults to `1` (show everything Google returns). If you raise it,
  the widget discloses the filter — decide whether that is fair for your case.
- **Privacy policy.** Reviewers' names and avatars are personal data, and the
  avatars load from Google's servers (the visitor's IP reaches Google). Mention
  Google Maps reviews in your privacy policy.
- **Billing and the key** are yours: keep the quota from step 1 in place.

## License

MIT — see [LICENSE](LICENSE). The license covers this code only; review content
belongs to its authors and Google and is used under the Google Maps Platform
terms. This project is not affiliated with or endorsed by Google. Google and
Google Maps are trademarks of Google LLC.
