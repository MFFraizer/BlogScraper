# BlogScraper

Scrapes paginated story chapters from lit.com-style sites and assembles them into a readable EPUB.

---

## Requirements

- Python 3.10+

Install Python dependencies:

```bash
pip install -r requirements.txt
```

---

## Usage

There are two ways to run the scraper: a local web GUI (recommended — no need to remember command syntax), or the CLI directly.

### GUI (recommended)

Start the local server:

```bash
python3 app.py
```

Then open **http://127.0.0.1:5000** in your browser. Paste a chapter or series URL, optionally add an author name, and click **Start Scrape**. Console output streams live, and finished EPUBs show up in the Library list below with a Download link.

The GUI just runs `scraper.py` as a subprocess and streams its output — it doesn't change how scraping works, only how you trigger it. Only one scrape runs at a time. Stop the server with `Ctrl+C` in the terminal when you're done.

### CLI

```bash
python scraper.py <chapter-1-url-or-series-url> [author]
```

**Examples:**

```bash
# Scrape from chapter 1, no author
python scraper.py https://www.lit.com/s/my-only-talent-ch-1

# Scrape with author name (appears in EPUB metadata)
python scraper.py https://www.lit.com/s/my-only-talent-ch-1 "Jane Author"

# Start mid-story at chapter 12
python scraper.py https://www.lit.com/s/my-only-talent-ch-12 "Jane Author"

# Scrape an entire series from its series index page
python scraper.py https://www.lit.com/series/se/457284057
```

A single-chapter URL must match the pattern `https://hostname/s/story-slug-ch-N`. The scraper walks forward from chapter N until it hits a 404. A series URL (`https://hostname/series/se/<id>`) pulls every chapter listed on the series page instead.

---

## Output

An EPUB file is written to the repo root:

```
my-only-talent.epub
```

If you used the GUI, it's listed under Library with a Download link. Either way, upload the `.epub` directly to your Kindle via the Send to Kindle web uploader, the Kindle app, or USB transfer.

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
    "div[itemprop='articleBody']",
    # ... existing selectors
]
```

---

## Notes

- **Polite scraping:** 0.75-second delay between every request by default.
- **End detection:** The scraper stops automatically when a chapter URL returns 404.
- **Multi-page chapters:** Pages within a chapter (`?page=2`, `?page=3`, etc.) are fetched and joined with a horizontal rule.
- **Story title:** Derived from the `<h1>` of chapter 1, falling back to the URL slug.
