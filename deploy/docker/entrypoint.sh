#!/usr/bin/env bash
# Container loop: fetch reviews, upload over FTP(S), sleep, repeat.
# Config via environment (see .env.example). Secrets never baked into the image.
set -uo pipefail

: "${REVIEWS_CONFIG:=/app/config.json}"
: "${REVIEWS_OUT:=/data/reviews.json}"
: "${INTERVAL_SECONDS:=43200}"   # 12h

export REVIEWS_CONFIG REVIEWS_OUT

upload() {
  [ -n "${REVIEWS_FTP_URL:-}" ] || { echo "[docker] REVIEWS_FTP_URL unset — skipping upload"; return 0; }
  [ -s "$REVIEWS_OUT" ] || { echo "[docker] no output file — skipping upload"; return 0; }
  curl -sS --ssl-reqd --ftp-create-dirs \
       --user "${REVIEWS_FTP_USER}:${REVIEWS_FTP_PASS}" \
       -T "$REVIEWS_OUT" "$REVIEWS_FTP_URL" \
    && echo "[docker] uploaded -> $REVIEWS_FTP_URL" \
    || echo "[docker] upload FAILED (keeping going)"
}

echo "[docker] start; interval=${INTERVAL_SECONDS}s config=$REVIEWS_CONFIG out=$REVIEWS_OUT"
while true; do
  echo "[docker] === run $(date -u +%FT%TZ) ==="
  python /app/scraper/fetch_reviews.py || echo "[docker] scraper warning — keeping previous data"
  upload
  echo "[docker] sleep ${INTERVAL_SECONDS}s"
  sleep "${INTERVAL_SECONDS}"
done
