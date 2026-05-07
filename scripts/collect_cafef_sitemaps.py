from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests
from tqdm import tqdm
import trafilatura


SITEMAP_INDEX = "https://cafef.vn/sitemap.xml"
ARTICLE_URL_RE = re.compile(r"-\d+\.chn$")
STOCK_SLUG_RE = re.compile(
    r"(chung-khoan|co-phieu|vn-index|hnx|upcom|vn30|hose|co-tuc|dhcd|dhdcd|"
    r"trai-phieu|niem-yet|thanh-khoan|khoi-ngoai|ban-rong|mua-rong|"
    r"loi-nhuan|doanh-thu|ty-dong|ti-dong)",
    flags=re.IGNORECASE,
)


def stable_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def fetch_text(url: str) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (academic NLP dataset; contact: local project)"},
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def xml_locs(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text.encode("utf-8"))
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [element.text or "" for element in root.findall(".//sm:loc", ns)]
    if not locs:
        locs = [element.text or "" for element in root.findall(".//loc")]
    return [loc for loc in locs if loc]


def sitemap_urls(index_url: str, max_sitemaps: int) -> list[str]:
    locs = xml_locs(fetch_text(index_url))
    candidates = [
        loc
        for loc in locs
        if "/sitemaps/sitemaps-" in loc or loc.endswith("latest-news-sitemap.xml")
    ]
    return candidates[:max_sitemaps]


def collect_article_urls(index_url: str, max_sitemaps: int, max_urls: int, slug_filter: bool) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for sitemap_url in tqdm(sitemap_urls(index_url, max_sitemaps), desc="Reading sitemaps"):
        try:
            locs = xml_locs(fetch_text(sitemap_url))
        except Exception as exc:
            print(f"[WARN] Failed sitemap {sitemap_url}: {exc}")
            continue
        for loc in locs:
            path = urlparse(loc).path
            if not ARTICLE_URL_RE.search(path):
                continue
            if slug_filter and not STOCK_SLUG_RE.search(path):
                continue
            if loc in seen:
                continue
            seen.add(loc)
            urls.append(loc)
            if len(urls) >= max_urls:
                return urls
    return urls


def fetch_article(url: str, min_chars: int) -> dict | None:
    html = trafilatura.fetch_url(url)
    if not html:
        return None
    extracted = trafilatura.extract(
        html,
        output_format="json",
        include_comments=False,
        include_tables=True,
        favor_precision=True,
        url=url,
    )
    if not extracted:
        return None
    payload = json.loads(extracted)
    text = (payload.get("text") or "").strip()
    if len(text) < min_chars:
        return None
    title = (payload.get("title") or "").strip()
    if not title:
        title = text.splitlines()[0].strip()
    return {
        "id": stable_id(url),
        "url": url,
        "source": "CafeF - Sitemap",
        "title": title,
        "author": payload.get("author") or "",
        "published_at": payload.get("date") or "",
        "text": text,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def urls_from_jsonl(path: Path) -> set[str]:
    urls: set[str] = set()
    if not path.exists():
        return urls
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = row.get("url")
            if url:
                urls.add(str(url))
    return urls


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-url", default=SITEMAP_INDEX)
    parser.add_argument("--max-sitemaps", type=int, default=12)
    parser.add_argument("--max-urls", type=int, default=500)
    parser.add_argument("--max-articles", type=int, default=200)
    parser.add_argument("--min-chars", type=int, default=700)
    parser.add_argument("--no-slug-filter", action="store_true")
    parser.add_argument("--exclude-jsonl", action="append", default=[])
    parser.add_argument("--delay", type=float, default=0.05)
    parser.add_argument("--output", default="data/raw/cafef_sitemap_stock.jsonl")
    args = parser.parse_args()

    article_urls = collect_article_urls(
        args.index_url,
        max_sitemaps=args.max_sitemaps,
        max_urls=args.max_urls,
        slug_filter=not args.no_slug_filter,
    )
    excluded_urls: set[str] = set()
    for path in args.exclude_jsonl:
        excluded_urls.update(urls_from_jsonl(Path(path)))
    if excluded_urls:
        before = len(article_urls)
        article_urls = [url for url in article_urls if url not in excluded_urls]
        print(f"Skipped {before - len(article_urls)} excluded URLs before download")

    rows: list[dict] = []
    for url in tqdm(article_urls, desc="Downloading articles"):
        article = fetch_article(url, min_chars=args.min_chars)
        if article:
            rows.append(article)
        if len(rows) >= args.max_articles:
            break
        if args.delay:
            time.sleep(args.delay)

    write_jsonl(Path(args.output), rows)
    print(f"Found {len(article_urls)} candidate URLs")
    print(f"Saved {len(rows)} articles to {args.output}")


if __name__ == "__main__":
    main()
