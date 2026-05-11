# `translator/fetcher/` — URL fetcher subpackage

Owns the "Load URL" pipeline: download an article URL and return its
extracted main text.  The package is a swappable abstraction plus two
concrete backends; selection happens at import time from the
``MT_FETCHER`` environment variable (set by ``run.sh --fetcher <name>``).

## Files

| File | Role |
|---|---|
| `base.py` | `Fetcher` ABC, `FetchResult` dataclass, `FetchError` exception. |
| `http.py` | Shared HTTP layer: realistic-browser headers, size cap, content-type guard, encoding fallback, brotli probe. Returns an `HttpDownload`. |
| `trafilatura_impl.py` | `TrafilaturaFetcher` (default) — uses `http.download()` then `trafilatura.bare_extraction`. |
| `newspaper_impl.py` | `NewspaperFetcher` — uses `http.download()` then `newspaper3k.Article`. |
| `__init__.py` | Registers backends, picks one based on `MT_FETCHER`, exposes `fetch_and_extract(url)` and `available_fetchers()`. |

## Backend selection

| Backend | Strengths | Weaknesses |
|---|---|---|
| `trafilatura` (default) | Actively maintained; broader recall; better on non-standard layouts; richer metadata. | More permissive — can include ad copy, related links, captions. |
| `newspaper` | Strict main-content detection; usually no ads or related-content noise; cleaner output for translation. | Unmaintained; sometimes truncates short or non-standard pages; needs the control-char defense to avoid an lxml crash. |

Switch backends via the CLI: `./run.sh --fetcher newspaper`.

## Adding a new backend

1. Add a new module under `translator/fetcher/` defining a class that
   subclasses `Fetcher` (set `id`, `display_name`, implement
   `fetch_and_extract`).  It almost certainly wants to call
   `http.download()` from this package to keep the browser-like HTTP
   fingerprint consistent.
2. Add an entry to `_FETCHERS` in `__init__.py` keyed by the class's
   `id`.

The view and the form do not need to change — they import
`fetch_and_extract` / `FetchError` from this package's top-level.

## Defensive measures already in place

In `http.py`:

- Realistic Chrome-on-Linux headers (`User-Agent`, `Sec-Ch-Ua-*`,
  `Sec-Fetch-*`, `Accept`, `Accept-Language`).
- Brotli decoding (`Accept-Encoding: ... br`) backed by the `brotli`
  package in `requirements.txt`, so the advertised compression list is
  honest.
- Response body capped at 8 MB, streamed with `iter_content` so we
  short-circuit before fully reading oversized responses.
- Content-Type guard: only `text/html`, `application/xhtml+xml`, and
  `text/plain` are accepted; PDFs, images, JSON APIs are rejected
  early.
- Encoding fallback to UTF-8 when the server omits a charset or
  claims `iso-8859-1` (requests' default, usually wrong for modern
  pages).  Both the raw bytes *and* the decoded `str` are exposed on
  the `HttpDownload` so each extractor can pick whichever shape it
  prefers — trafilatura takes the bytes so lxml can honour the
  document's own encoding declaration, while newspaper takes the
  decoded `str` (its parsing path predates and handles that input).

In `trafilatura_impl.py`:

- HTML is stripped of ASCII control characters (everything below 0x20
  except TAB / LF / CR) before extraction — this is the same class of
  bug that crashed `newspaper3k` on pages with bare NULs, and it costs
  nothing to fix preemptively because XML 1.0 forbids those bytes in
  text content anyway.
- `bare_extraction` is configured with `favor_recall=True`,
  `include_comments=False`, `include_tables=False`, and is given the
  *final* URL (post-redirects) so trafilatura can resolve metadata.
- `None` results (trafilatura's "no content found") are surfaced as an
  empty `FetchResult`, not as an exception; the view then renders
  *"couldn't extract any article text"* rather than a traceback.

## Known limitations

- **JS-rendered SPAs.**  Pages whose article body is built by client
  JavaScript have nothing in the HTML body for any of these
  extractors to find.  Fixing this requires a headless browser
  (Playwright, Chromium-based) and is out of scope for now.
- **Login-walled / paywalled pages.**  We do not authenticate.
- **Aggressive anti-bot vendors.**  The browser-like header set is
  enough for most news sites, but is not a substitute for stealth-mode
  Playwright on sites that fingerprint with TLS or JS challenges.
