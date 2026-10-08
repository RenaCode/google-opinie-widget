# Google reviews fetcher — self-contained container. Runs the headless-browser
# scraper on a schedule and uploads reviews.json to the website over FTP(S).
# Base image ships Chromium + all browser deps for Playwright.
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir playwright==1.47.0

COPY scraper/ /app/scraper/
COPY deploy/docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Persisted across restarts so the "keep last good reviews" guard survives.
ENV REVIEWS_OUT=/data/reviews.json
VOLUME ["/data"]

ENTRYPOINT ["/app/entrypoint.sh"]
