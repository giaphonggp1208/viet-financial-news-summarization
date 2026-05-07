from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

import feedparser
from tqdm import tqdm
import trafilatura


DEFAULT_FEEDS = [
    "https://vnexpress.net/rss/kinh-doanh.rss",
]


def stable_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def fetch_article(url: str, min_chars: int = 800) -> dict | None:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return None

    text = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
    )
    if not text or len(text) < min_chars:
        return None

    return {
        "id": stable_id(url),
        "url": url,
        "source": urlparse(url).netloc,
        "text": text.strip(),
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def iter_feed_urls(feeds: list[str], limit_per_feed: int) -> list[dict]:
    entries: list[dict] = []
    for feed_url in feeds:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:limit_per_feed]:
            link = entry.get("link")
            if not link:
                continue
            entries.append(
                {
                    "url": link,
                    "title": entry.get("title", ""),
                    "published_at": entry.get("published", ""),
                    "feed": feed_url,
                }
            )
    return entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feed", action="append", dest="feeds", default=[])
    parser.add_argument("--limit-per-feed", type=int, default=200)
    parser.add_argument("--min-chars", type=int, default=800)
    parser.add_argument("--output", default="data/raw/articles.jsonl")
    args = parser.parse_args()

    feeds = args.feeds or DEFAULT_FEEDS
    entries = iter_feed_urls(feeds, args.limit_per_feed)
    seen_urls: set[str] = set()
    rows: list[dict] = []

    for entry in tqdm(entries, desc="Downloading articles"):
        url = entry["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        article = fetch_article(url, min_chars=args.min_chars)
        if not article:
            continue
        article.update(
            {
                "title": entry.get("title", ""),
                "published_at": entry.get("published_at", ""),
                "feed": entry.get("feed", ""),
            }
        )
        rows.append(article)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Saved {len(rows)} articles to {out_path}")


if __name__ == "__main__":
    main()

