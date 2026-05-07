from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlparse

from tqdm import tqdm
import trafilatura


DEFAULT_CATEGORY_URL = "https://cafef.vn/thi-truong-chung-khoan.chn"
DEFAULT_PAGE_URL_TEMPLATE = "https://cafef.vn/thi-truong-chung-khoan/trang-{page}.chn"
ARTICLE_URL_RE = re.compile(r"-\d+\.chn(?:$|[?#])")


class CafeFLinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[dict[str, str]] = []
        self._current_href = ""
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href") or ""
        if not href:
            return
        absolute = urljoin(self.base_url, href)
        parsed = urlparse(absolute)
        if parsed.netloc.lower().endswith("cafef.vn") and ARTICLE_URL_RE.search(parsed.path):
            self._current_href = absolute.split("#", 1)[0]
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._current_text.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._current_href:
            return
        title = " ".join(part for part in self._current_text if part).strip()
        self.links.append({"url": self._current_href, "title": title})
        self._current_href = ""
        self._current_text = []


def stable_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def fetch_html(url: str) -> str:
    html = trafilatura.fetch_url(url)
    return html or ""


def extract_article_links(category_url: str) -> list[dict[str, str]]:
    html = fetch_html(category_url)
    parser = CafeFLinkParser(category_url)
    parser.feed(html)

    seen: set[str] = set()
    links: list[dict[str, str]] = []
    for link in parser.links:
        url = link["url"]
        if url in seen:
            continue
        seen.add(url)
        links.append(link)
    return links


def fetch_article(url: str, title_hint: str = "", min_chars: int = 700) -> dict | None:
    html = fetch_html(url)
    if not html:
        return None

    extracted_json = trafilatura.extract(
        html,
        output_format="json",
        include_comments=False,
        include_tables=True,
        favor_precision=True,
        url=url,
    )
    if not extracted_json:
        return None

    payload = json.loads(extracted_json)
    text = (payload.get("text") or "").strip()
    if len(text) < min_chars:
        return None
    title = (payload.get("title") or title_hint or "").strip()
    if not title:
        title = text.splitlines()[0].strip()

    return {
        "id": stable_id(url),
        "url": url,
        "source": "CafeF - Thị trường chứng khoán",
        "title": title,
        "author": payload.get("author") or "",
        "published_at": payload.get("date") or "",
        "text": text,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def build_category_urls(
    category_url: str,
    page_url_template: str,
    pages: int,
) -> list[str]:
    urls = [category_url]
    for page in range(2, pages + 1):
        urls.append(page_url_template.format(page=page))
    return urls


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category-url", default=DEFAULT_CATEGORY_URL)
    parser.add_argument("--page-url-template", default=DEFAULT_PAGE_URL_TEMPLATE)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--max-articles", type=int, default=200)
    parser.add_argument("--min-chars", type=int, default=700)
    parser.add_argument("--output", default="data/raw/cafef_chung_khoan.jsonl")
    args = parser.parse_args()

    category_urls = build_category_urls(args.category_url, args.page_url_template, args.pages)
    link_rows: list[dict[str, str]] = []
    seen_links: set[str] = set()
    for category_url in tqdm(category_urls, desc="Reading CafeF category pages"):
        for link in extract_article_links(category_url):
            if link["url"] in seen_links:
                continue
            seen_links.add(link["url"])
            link_rows.append(link)
            if len(link_rows) >= args.max_articles:
                break
        if len(link_rows) >= args.max_articles:
            break

    rows: list[dict] = []
    for link in tqdm(link_rows, desc="Downloading CafeF articles"):
        article = fetch_article(link["url"], title_hint=link.get("title", ""), min_chars=args.min_chars)
        if article:
            rows.append(article)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Found {len(link_rows)} article URLs")
    print(f"Saved {len(rows)} CafeF articles to {out_path}")


if __name__ == "__main__":
    main()
