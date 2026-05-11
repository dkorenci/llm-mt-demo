"""Newspaper3k-backed fetcher implementation.

``newspaper3k`` is older and unmaintained, but its main-text extractor
is more aggressive at discarding boilerplate (ads, related-content
strips, promo blurbs) than trafilatura's recall-favoring mode, which
makes it a better default for clean translation input.

Known defensive measures applied here:

* **Strip XML-incompatible control characters from the HTML before
  extraction.**  newspaper3k crashes with
  ``ValueError: All strings must be XML compatible: Unicode or ASCII,
  no NULL bytes or control characters`` when its ``remove_scripts_styles``
  cleaner concatenates a ``node.tail`` that contains bare control bytes
  onto a ``parent.text``.  XML 1.0 forbids those bytes in text content
  anyway, so stripping them is safe.

* **Pass decoded ``str`` to newspaper.**  newspaper3k's downloader
  stores its input directly on the ``Article`` and feeds it to
  ``lxml.html.fromstring``.  The HTML parser (unlike the XML one) is
  happy to receive a Python ``str`` with an encoding declaration, so
  ``str`` is the simpler and historically-tested input shape here.
"""
from __future__ import annotations

import logging
from typing import Final

from newspaper import Article  # type: ignore[import-untyped]

from .base import Fetcher, FetchError, FetchResult
from .http import download

logger = logging.getLogger(__name__)


# ASCII control characters that XML 1.0 forbids inside text content
# (everything below 0x20 except TAB, LF, CR).  See module docstring.
_HTML_CONTROL_CHARS_TABLE: Final[dict[int, None]] = {
    code: None for code in range(0x20) if code not in (0x09, 0x0A, 0x0D)
}


def _sanitize_html(html: str) -> str:
    """Return ``html`` with XML-incompatible control characters removed."""
    return html.translate(_HTML_CONTROL_CHARS_TABLE)


class NewspaperFetcher(Fetcher):
    """Alternative fetcher: shared HTTP layer + ``newspaper3k`` extraction.

    Newspaper's content selection is stricter than trafilatura's, which
    typically yields a cleaner article body for translation, at the
    cost of occasionally truncating short pieces or non-standard layouts.
    """

    id: str = "newspaper"
    display_name: str = "Newspaper3k"

    def fetch_and_extract(self, url: str) -> FetchResult:
        if not url:
            raise FetchError("No URL provided.")

        try:
            download_result = download(url)
        except ValueError as exc:
            # ``download`` already logged the traceback at fetch time.
            raise FetchError(str(exc)) from exc

        html = _sanitize_html(download_result.body)
        final_url = download_result.final_url

        article = Article(final_url)
        try:
            article.download(input_html=html)
        except Exception as exc:
            logger.exception(
                "newspaper.download() failed for %s (html length %d)",
                final_url,
                len(html),
            )
            raise FetchError(
                f"Extraction failed during download(): {exc}"
            ) from exc

        try:
            article.parse()
        except Exception as exc:
            logger.exception(
                "newspaper.parse() failed for %s (html length %d)",
                final_url,
                len(html),
            )
            raise FetchError(f"Extraction failed: {exc}") from exc

        text = article.text or ""
        title = article.title or ""
        logger.info(
            "Extracted %s -> title=%r, text_length=%d",
            final_url,
            title,
            len(text),
        )
        return FetchResult(text=text, title=title)
