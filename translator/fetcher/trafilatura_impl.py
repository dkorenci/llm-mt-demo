"""Trafilatura-backed fetcher implementation.

Trafilatura (https://github.com/adbar/trafilatura) is an actively
maintained, state-of-the-art article extractor.  We pair it with the
shared HTTP layer in :mod:`translator.fetcher.http` so the HTTP step
keeps its browser-like fingerprint regardless of which extractor is in
use.

Known defensive measures applied here:

* **Strip XML-incompatible control characters from the HTML before
  extraction.**  Trafilatura uses ``lxml`` internally; pages that
  contain bare NUL or other ASCII control bytes (which are invalid in
  XML 1.0 text content) can still crash a downstream serialisation
  step.  Stripping them up front is harmless — they have no semantic
  meaning in HTML text content — and it also avoided the exact failure
  mode we hit previously with newspaper3k.

* **Favor recall over precision.**  Some demo-worthy pages have
  unusually short articles; the default extractor is conservative and
  may discard them entirely.  ``favor_recall=True`` is more lenient.

* **Drop comments and tables.**  We want clean prose for translation;
  comment sections and tabular data tend to introduce noise.

* **Pass the final URL to the extractor.**  Trafilatura uses it to
  resolve relative links and improve metadata extraction.

* **Treat ``None`` extraction result as a soft failure**, not an
  exception.  Trafilatura returns ``None`` when its scoring algorithm
  judges the page has no extractable main content; the caller surfaces
  this as ``"couldn't extract any article text"`` rather than as a
  traceback.
"""
from __future__ import annotations

import logging
from typing import Final

import trafilatura  # type: ignore[import-untyped]

from .base import Fetcher, FetchError, FetchResult
from .http import download

logger = logging.getLogger(__name__)


# Bytes the XML 1.0 spec forbids inside text content (everything below
# 0x20 except TAB, LF, CR).  We strip them from the response body up
# front; they have no semantic meaning in HTML and are a known source
# of crashes deep inside lxml-based extractors (newspaper3k crashed on
# them outright, and they can still corrupt downstream serialisation).
_FORBIDDEN_CONTROL_BYTES: Final[bytes] = bytes(
    c for c in range(0x20) if c not in (0x09, 0x0A, 0x0D)
)


def _sanitize_html_bytes(html: bytes) -> bytes:
    """Return ``html`` with XML-incompatible control bytes removed."""
    # ``bytes.translate(None, delete=...)`` deletes the listed bytes
    # without translating anything else.
    return html.translate(None, _FORBIDDEN_CONTROL_BYTES)


class TrafilaturaFetcher(Fetcher):
    """Default fetcher: shared HTTP layer + trafilatura extraction. (default)

    Trafilatura is fed the raw response *bytes* rather than the decoded
    ``str``: lxml refuses Python ``str`` input that contains an
    ``<?xml encoding=...?>`` or ``<meta charset>`` declaration, and
    trafilatura silently surfaces that as an empty result with the
    log line ``parsed tree length: 1, wrong data type or not valid
    HTML``.  Passing bytes lets lxml use the declared encoding and
    parses correctly.
    """

    id: str = "trafilatura"
    display_name: str = "Trafilatura"

    def fetch_and_extract(self, url: str) -> FetchResult:
        if not url:
            raise FetchError("No URL provided.")

        try:
            download_result = download(url)
        except ValueError as exc:
            # ``download`` already logged the traceback at fetch time.
            raise FetchError(str(exc)) from exc

        html_bytes = _sanitize_html_bytes(download_result.body_bytes)
        final_url = download_result.final_url

        try:
            document = trafilatura.bare_extraction(
                html_bytes,
                url=final_url,
                include_comments=False,
                include_tables=False,
                favor_recall=True,
                with_metadata=True,
            )
        except Exception as exc:
            logger.exception(
                "trafilatura extraction crashed for %s (html length %d bytes)",
                final_url,
                len(html_bytes),
            )
            raise FetchError(f"Extraction failed: {exc}") from exc

        text, title = _unpack_document(document)
        logger.info(
            "Extracted %s -> title=%r, text_length=%d",
            final_url,
            title,
            len(text),
        )
        return FetchResult(text=text, title=title)


def _unpack_document(document: object) -> tuple[str, str]:
    """Pull ``(text, title)`` out of whatever shape trafilatura returned.

    Older releases return a ``dict``; recent releases return a
    ``Document`` (an attrs/dataclass-style object).  We accept both,
    and treat ``None`` as "no content extracted".
    """
    if document is None:
        return "", ""
    # Attribute-style (newer trafilatura).
    text = getattr(document, "text", None)
    title = getattr(document, "title", None)
    # Dict-style (older trafilatura).
    if text is None and isinstance(document, dict):
        text = document.get("text")
        title = document.get("title")
    return (text or "", title or "")
