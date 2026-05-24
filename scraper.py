#!/usr/bin/env python3
"""
Story scraper: paginated chapter/page site → EPUB

Usage:
    python scraper.py https://www.lit.com/s/my-only-talent-ch-1
    python scraper.py https://www.lit.com/s/my-only-talent-ch-1 "Author Name"

Requirements:
    pip install requests beautifulsoup4 ebooklib
"""

from __future__ import annotations

import re
import sys
import time
import requests
from bs4 import BeautifulSoup
from ebooklib import epub

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REQUEST_DELAY = 0.75        # seconds between requests — be polite
REQUEST_TIMEOUT = 15        # seconds before giving up on a request
MAX_PAGES_PER_CHAPTER = 50  # safety ceiling — prevents runaway loops

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------
# IMPORTANT: Inspect the target site's HTML and update this list.
# Right-click → Inspect the story text block, find a unique CSS selector,
# and put it first in this list. The scraper tries each in order.

CONTENT_SELECTORS = [
    "div[itemprop='articleBody']", # semantic — works on Literotica and many others
    ".aa_ht",
    ".story-text",
    "#story",
    "div.b-story-body",
    ".panel.article",
    "article",
]

TITLE_SELECTORS = [
    "h1.headline",
    "h1",
    ".title",
    "title",
]

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def get_page(url: str, session: requests.Session) -> requests.Response | None:
    """Fetch a URL. Returns None on 404; raises on other errors."""
    try:
        response = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"  ⚠  Request failed for {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def extract_content(soup: BeautifulSoup) -> str:
    """Try each selector in order; return inner HTML of first match."""
    for selector in CONTENT_SELECTORS:
        el = soup.select_one(selector)
        if el:
            # Strip any nav / button elements embedded inside the content block
            for tag in el.select("a[href], button, .b-pager, .clearfix"):
                tag.decompose()
            return str(el)
    # Fallback: grab all <p> tags (better than nothing)
    paras = soup.find_all("p")
    if paras:
        return "\n".join(str(p) for p in paras)
    print("  ⚠  Could not find content block — check CONTENT_SELECTORS above.")
    return "<p>[Content not found — update CONTENT_SELECTORS]</p>"


def extract_title(soup: BeautifulSoup, fallback: str = "") -> str:
    for selector in TITLE_SELECTORS:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(strip=True)
            if text:
                return text
    return fallback


# ---------------------------------------------------------------------------
# Series detection
# ---------------------------------------------------------------------------

def _chapter_sort_key(url: str) -> int:
    """
    Extract chapter number for sorting series URLs.
    Prefers the number after '-ch-' (e.g. 'story-ch-03-1' → 3)
    over a bare trailing number (e.g. 'story-3' → 3).
    """
    m = re.search(r"-ch-(\d+)", url)
    if m:
        return int(m.group(1))
    m = re.search(r"-(\d+)/?$", url.rstrip("/"))
    return int(m.group(1)) if m else 0


def _scrape_series_page(series_url: str, origin: str, session: requests.Session) -> list[str] | None:
    """Fetch a series index page and return all chapter URLs found on it."""
    resp = get_page(series_url, session)
    if resp is None:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    seen: set[str] = set()
    urls: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/s/"):
            href = origin + href
        if (
            "/s/" in href
            and "comments" not in href
            and "dialog" not in href
            and href not in seen
        ):
            seen.add(href)
            urls.append(href)
    return urls or None


def get_series_urls(story_url: str, session: requests.Session) -> list[str] | None:
    """
    If the story belongs to a Literotica series, return all chapter URLs
    sorted by chapter number. Returns None if no series link is found.
    Accepts either a chapter URL or a /series/se/XXXXXX URL directly.
    """
    origin = re.match(r"https?://[^/]+", story_url).group(0)

    # Direct series URL — skip the story-page lookup
    if re.search(r"/series/se/\d+", story_url):
        series_href = story_url
    else:
        resp = get_page(story_url, session)
        if resp is None:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        series_href = None
        for a in soup.find_all("a", href=True):
            if re.search(r"/series/se/\d+", a["href"]):
                series_href = a["href"]
                break
        if not series_href:
            return None
        if not series_href.startswith("http"):
            series_href = origin + series_href

    print(f"    Series : {series_href}")
    time.sleep(REQUEST_DELAY)
    urls = _scrape_series_page(series_href, origin, session)
    if not urls:
        return None

    return sorted(urls, key=_chapter_sort_key)


# ---------------------------------------------------------------------------
# Scraping logic
# ---------------------------------------------------------------------------

def scrape_chapter_from_url(
    chapter_url: str,
    chapter_num: int,
    session: requests.Session,
) -> tuple[str, str] | None:
    """
    Scrape all pages of one chapter given its full URL.
    Returns (chapter_title, combined_html) or None if the chapter 404s.
    """
    response = get_page(chapter_url, session)
    if response is None:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    chapter_title = extract_title(soup, fallback=f"Chapter {chapter_num}")
    content_blocks = [extract_content(soup)]
    print(f"    Page 1 ✓")

    for page_num in range(2, MAX_PAGES_PER_CHAPTER + 1):
        time.sleep(REQUEST_DELAY)
        page_url = f"{chapter_url}?page={page_num}"
        resp = get_page(page_url, session)
        if resp is None:
            break
        page_soup = BeautifulSoup(resp.text, "html.parser")
        content_blocks.append(extract_content(page_soup))
        print(f"    Page {page_num} ✓")

    combined = "\n<hr/>\n".join(content_blocks)
    return chapter_title, combined


def scrape_chapter(
    base_url: str,
    chapter_num: int,
    session: requests.Session,
    ch_width: int = 1,
) -> tuple[str, str] | None:
    """
    Scrape one chapter by constructing its URL from base + chapter number.
    Returns (chapter_title, combined_html) or None if the chapter 404s.
    ch_width controls zero-padding: 2 → "ch-01", 1 → "ch-1".
    """
    chapter_url = f"{base_url}-ch-{str(chapter_num).zfill(ch_width)}"
    return scrape_chapter_from_url(chapter_url, chapter_num, session)


# ---------------------------------------------------------------------------
# EPUB builder
# ---------------------------------------------------------------------------

def build_epub(story_title: str, author: str, chapters: list[tuple[str, str]]) -> epub.EpubBook:
    book = epub.EpubBook()
    book.set_identifier(re.sub(r"\W+", "-", story_title.lower()))
    book.set_title(story_title)
    book.set_language("en")
    book.add_author(author)

    # Minimal CSS for readable typography on Kindle
    style = epub.EpubItem(
        uid="style",
        file_name="style.css",
        media_type="text/css",
        content="""
            body { font-family: Georgia, serif; line-height: 1.6; margin: 5%; }
            h1 { font-size: 1.4em; margin-bottom: 1em; }
            p { margin: 0 0 0.8em 0; text-indent: 1.5em; }
            hr { border: none; border-top: 1px solid #ccc; margin: 1.5em 0; }
        """,
    )
    book.add_item(style)

    epub_chapters = []
    for i, (ch_title, content) in enumerate(chapters, 1):
        c = epub.EpubHtml(
            title=ch_title,
            file_name=f"chapter_{i:03d}.xhtml",
            lang="en",
        )
        # ebooklib's parse_html_string requires bytes when an XML declaration is present
        c.content = (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<!DOCTYPE html>'
            f'<html xmlns="http://www.w3.org/1999/xhtml">'
            f'<head><title>{ch_title}</title>'
            f'<link rel="stylesheet" type="text/css" href="style.css"/>'
            f'</head><body>'
            f'<h1>{ch_title}</h1>'
            f'{content}'
            f'</body></html>'
        ).encode('utf-8')
        c.add_item(style)
        book.add_item(c)
        epub_chapters.append(c)

    book.toc = [(epub.Section(story_title), epub_chapters)]
    book.spine = ["nav"] + epub_chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    return book


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

def parse_start_url(url: str) -> tuple[str, str, int, int]:
    """
    Returns (base_url_without_ch, story_slug, start_chapter, ch_width).
    ch_width is the zero-pad width of the chapter number in the URL.
    E.g. 'https://www.lit.com/s/my-story-ch-01'
      → ('https://www.lit.com/s/my-story', 'my-story', 1, 2)
    """
    match = re.match(r"^(https?://[^/]+/s/(.+?))-ch-(\d+)/?$", url.rstrip("/"))
    if not match:
        raise ValueError(
            "Could not parse URL.\n"
            "Expected: https://www.site.com/s/story-name-ch-1"
        )
    base = match.group(1)
    slug = match.group(2)
    raw_ch = match.group(3)
    start_ch = int(raw_ch)
    ch_width = len(raw_ch)  # e.g. "01" → 2, "1" → 1
    return base, slug, start_ch, ch_width


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    start_url = sys.argv[1].strip()
    author = sys.argv[2] if len(sys.argv) > 2 else "Unknown Author"

    is_series_url = bool(re.search(r"/series/se/\d+", start_url))

    if is_series_url:
        base_url = story_slug = None
        start_chapter = 1
        ch_width = 1
        story_title = "Unknown Story"
    else:
        try:
            base_url, story_slug, start_chapter, ch_width = parse_start_url(start_url)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
        story_title = story_slug.replace("-", " ").title()

    print(f"\n📖  {story_title}")
    if not is_series_url:
        print(f"    Base URL : {base_url}")
    print(f"    Starting : Chapter {start_chapter}\n")

    session = requests.Session()
    chapters: list[tuple[str, str]] = []

    print(f"  Checking for series…")
    series_urls = get_series_urls(start_url, session)

    if series_urls:
        print(f"  → Series found: {len(series_urls)} chapter(s)\n")
        # When entering via a series URL, derive slug and title from first chapter URL
        if is_series_url:
            first = series_urls[0]
            slug_match = re.search(r"/s/([^/?#]+)", first)
            if slug_match:
                raw_slug = slug_match.group(1)
                # Strip trailing version suffix and chapter suffix for the slug
                story_slug = re.sub(r"-ch-\d+.*$", "", raw_slug) or re.sub(r"-\d+$", "", raw_slug)
                story_title = story_slug.replace("-", " ").title()
                print(f"    Title    : {story_title}")
                print(f"    Slug     : {story_slug}\n")

        # Filter to only chapters at or after start_chapter
        start_key = _chapter_sort_key(start_url) if not is_series_url else 0
        series_urls = [u for u in series_urls if _chapter_sort_key(u) >= start_key]

        for i, chapter_url in enumerate(series_urls, start_chapter):
            print(f"  Chapter {i}…")
            time.sleep(REQUEST_DELAY)
            result = scrape_chapter_from_url(chapter_url, i, session)
            if result is None:
                print(f"  ⚠  Skipping chapter {i} (fetch failed).")
                continue
            ch_title, ch_content = result
            if i == start_chapter and ch_title != f"Chapter {i}":
                story_title = ch_title
            chapters.append((f"Chapter {i}", ch_content))
    else:
        print(f"  → No series found, using sequential URL pattern\n")
        ch = start_chapter
        while True:
            print(f"  Chapter {ch}…")
            time.sleep(REQUEST_DELAY)
            result = scrape_chapter(base_url, ch, session, ch_width)
            if result is None:
                print(f"  → Chapter {ch} returned 404 — end of story.\n")
                break
            ch_title, ch_content = result
            if ch == start_chapter and ch_title != f"Chapter {ch}":
                story_title = ch_title
            chapters.append((f"Chapter {ch}", ch_content))
            ch += 1

    if not chapters:
        print("No content scraped — check selectors and URL.")
        sys.exit(1)

    print(f"\n✅  Scraped {len(chapters)} chapter(s).")
    print(f"📦  Building EPUB…")

    book = build_epub(story_title, author, chapters)
    epub_path = f"{story_slug}.epub"
    epub.write_epub(epub_path, book)
    print(f"✅  Saved: {epub_path}")


if __name__ == "__main__":
    main()
