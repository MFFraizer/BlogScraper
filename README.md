# BlogScraper

Scrapes paginated story chapters from lit.com-style sites and assembles them into a readable EPUB. Optionally converts to AZW3 for Kindle via Calibre.

---

## Requirements

- Python 3.10+
- [Calibre](https://calibre-ebook.com/) (only needed for AZW3/Kindle conversion)

Install Python dependencies:

```bash
pip install -r requirements.txt
```

---

## Usage

```bash
python scraper.py <chapter-1-url> [author]
```

**Examples:**

```bash
# Scrape from chapter 1, no author
python scraper.py https://www.lit.com/s/my-only-talent-ch-1

# Scrape with author name (appears in EPUB metadata)
python scraper.py https://www.lit.com/s/my-only-talent-ch-1 "Jane Author"

# Start mid-story at chapter 12
python scraper.py https://www.lit.com/s/my-only-talent-ch-12 "Jane Author"
```

The URL must match the pattern `https://hostname/s/story-slug-ch-N`. The scraper walks forward from chapter N until it hits a 404.

---

## Output

An EPUB file is written to the current directory:

```
my-only-talent.epub
```

### Convert to AZW3 (Kindle)

Requires [Calibre](https://calibre-ebook.com/) to be installed:

```bash
ebook-convert my-only-talent.epub my-only-talent.azw3
```

Then transfer the `.azw3` file to your Kindle via USB or Send to Kindle.

---

## Configuration

Open `scraper.py` and edit the constants at the top:

| Constant | Default | Purpose |
|---|---|---|
| `REQUEST_DELAY` | `0.75` | Seconds between requests |
| `REQUEST_TIMEOUT` | `15` | Seconds before a request times out |
| `MAX_PAGES_PER_CHAPTER` | `50` | Safety ceiling on pages per chapter |
| `CONTENT_SELECTORS` | See below | CSS selectors for story text |

### Adapting to a new site

The scraper tries each selector in `CONTENT_SELECTORS` in order and uses the first match. If the output looks wrong (missing text or nav garbage included), inspect the target site's HTML, find the CSS selector for the story text block, and add it first in the list:

```python
CONTENT_SELECTORS = [
    ".your-new-selector",   # add your site-specific selector first
    ".aa_ht",
    # ... existing selectors
]
```

---

## Notes

- **Polite scraping:** 0.75-second delay between every request by default.
- **End detection:** The scraper stops automatically when a chapter URL returns 404.
- **Multi-page chapters:** Pages within a chapter (`?page=2`, `?page=3`, etc.) are fetched and joined with a horizontal rule.
- **Story title:** Derived from the `<h1>` of chapter 1, falling back to the URL slug.
