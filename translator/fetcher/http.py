"""Shared HTTP layer for fetcher backends.

Downloads a URL with a header set that mimics a current Chrome on Linux,
then returns the decoded body as ``str`` along with the server's
``Content-Type``.  Concrete fetchers consume the body and run their own
extractor over it.

Defensive measures implemented here:

* **Realistic browser headers** — ``User-Agent`` plus the
  ``Sec-Ch-Ua-*`` / ``Sec-Fetch-*`` families that current Chrome sends.
* **Brotli decoding** — ``Accept-Encoding`` advertises ``br`` (a real
  Chrome would); the ``brotli`` package is listed in
  ``requirements.txt`` so :mod:`requests` can decode it.
* **Bounded response size** — the body is streamed and capped at
  :data:`_MAX_BYTES` to prevent a malicious or misconfigured server from
  ballooning memory.
* **Content-Type guard** — non-HTML responses (PDFs, images, JSON
  APIs, …) are rejected up front, since article extractors cannot do
  anything useful with them.
* **Encoding fallback** — for HTML responses where the server omits a
  charset, ``response.encoding`` is set from ``apparent_encoding``
  before reading ``response.text``.
"""
from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass
from typing import Final

import requests

logger = logging.getLogger(__name__)


def _supports_brotli() -> bool:
    """Return ``True`` if ``urllib3`` can decode ``content-encoding: br``.

    ``urllib3`` uses one of the optional ``brotli``/``brotlicffi``
    packages.  If neither is importable we must *not* advertise ``br``
    in ``Accept-Encoding`` — otherwise compliant servers (e.g. those
    behind Cloudflare) will brotli-compress the response and we'll
    silently hand the compressed bytes to the extractor.
    """
    return (
        importlib.util.find_spec("brotli") is not None
        or importlib.util.find_spec("brotlicffi") is not None
    )


_HAS_BROTLI: Final[bool] = _supports_brotli()

# Encodings we promise to honour in the Accept-Encoding request header.
# urllib3 always supports gzip and deflate; brotli is optional.
_ACCEPT_ENCODING: Final[str] = (
    "gzip, deflate, br" if _HAS_BROTLI else "gzip, deflate"
)

if not _HAS_BROTLI:
    logger.warning(
        "brotli package not installed: requests will not advertise 'br' in "
        "Accept-Encoding.  Install it with 'pip install brotli' for the "
        "browser-fingerprint match used by the fetcher."
    )


# A reasonably current Chrome-on-Linux header set.  Servers that gate
# content on ``User-Agent`` (and the ``Sec-Ch-Ua-*`` / ``Sec-Fetch-*``
# family) are usually content with this combination.
_BROWSER_HEADERS: Final[dict[str, str]] = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9,hr;q=0.8",
    "Accept-Encoding": _ACCEPT_ENCODING,
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Linux"',
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    "Upgrade-Insecure-Requests": "1",
    "DNT": "1",
    "Cache-Control": "max-age=0",
}

# Network timeout (in seconds) applied to the entire request.
_REQUEST_TIMEOUT: Final[float] = 15.0

# Hard cap on the number of decoded body bytes we'll consume.  Real
# articles are well under 5 MB; anything bigger is almost certainly not
# what we want to feed an extractor.
_MAX_BYTES: Final[int] = 8 * 1024 * 1024

# Content types we are willing to extract from.
_ACCEPTED_MIME_PREFIXES: Final[tuple[str, ...]] = (
    "text/html",
    "application/xhtml+xml",
    "text/plain",  # rare, but some "article" endpoints serve plain text
)


@dataclass(frozen=True)
class HttpDownload:
    """The raw material handed to a backend extractor.

    Both ``body_bytes`` and ``body`` are exposed because different
    extractors prefer different inputs:

    * Extractors built on ``lxml`` (e.g. trafilatura, readability) work
      best when handed *bytes* — that lets lxml read the document's
      own encoding declaration.  Decoded ``str`` input with an
      ``<?xml encoding=...?>`` or ``<meta charset>`` declaration is
      rejected by lxml and silently swallowed by trafilatura as
      "parsed tree length: 1".
    * Simpler text-based extractors prefer ``str``.

    Attributes:
        body_bytes: Raw response body, with transport-level encoding
            (gzip/brotli/deflate) already decoded by ``requests``.
        body: ``body_bytes`` decoded to ``str`` using the server's
            declared charset (UTF-8 fallback).
        content_type: Server-declared content type (full header value;
            callers should look at the prefix).
        final_url: URL after following redirects.
    """

    body_bytes: bytes
    body: str
    content_type: str
    final_url: str


def _new_session() -> requests.Session:
    """Build a ``requests.Session`` pre-loaded with browser-like defaults."""
    session = requests.Session()
    session.headers.update(_BROWSER_HEADERS)
    return session


def _is_accepted(content_type: str) -> bool:
    """Return ``True`` if a content type looks extractable as text."""
    lowered = (content_type or "").lower().split(";", 1)[0].strip()
    return any(lowered.startswith(p) for p in _ACCEPTED_MIME_PREFIXES)


def download(url: str) -> HttpDownload:
    """Fetch ``url`` like a real browser and return its decoded body.

    Raises:
        ValueError: on network failure, HTTP error, oversize response,
            or rejected content type.  Callers in the fetcher layer
            wrap this into :class:`FetchError`.
    """
    try:
        session = _new_session()
        # ``stream=True`` lets us enforce the size cap before all bytes
        # are pulled from the wire.
        response = session.get(
            url,
            timeout=_REQUEST_TIMEOUT,
            allow_redirects=True,
            stream=True,
        )
    except requests.RequestException as exc:
        logger.exception("HTTP request failed for %s", url)
        raise ValueError(f"Request failed: {exc}") from exc

    try:
        if not response.ok:
            logger.warning(
                "Non-OK response for %s: HTTP %s (final url: %s)",
                url,
                response.status_code,
                response.url,
            )
            raise ValueError(
                f"Server returned HTTP {response.status_code} for {url}"
            )

        content_type = response.headers.get("Content-Type", "")
        if not _is_accepted(content_type):
            logger.warning(
                "Refusing to extract from non-HTML %s (Content-Type=%r)",
                url,
                content_type,
            )
            raise ValueError(
                f"Unsupported Content-Type {content_type!r} for {url}"
            )

        # NOTE: urllib3 v2 transparently decodes ``Content-Encoding``
        # (gzip / brotli / deflate) when the matching package is
        # importable, but unlike v1 it *does not strip* the
        # ``Content-Encoding`` response header after decoding.  We
        # therefore cannot use the presence of that header as a
        # "did decoding fail?" signal here — the startup probe of
        # ``_HAS_BROTLI`` is the only reliable check, and we run it
        # at import time so the Accept-Encoding request header stays
        # honest.

        # Pull the body with a size cap.  ``response.iter_content`` reads
        # in chunks; we stop as soon as we exceed the limit.
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > _MAX_BYTES:
                logger.warning(
                    "Response from %s exceeds size cap (>%d bytes)",
                    url,
                    _MAX_BYTES,
                )
                raise ValueError(
                    f"Response too large (>{_MAX_BYTES} bytes) from {url}"
                )
            chunks.append(chunk)
        raw = b"".join(chunks)

        # Decode to str for backends that want text.  Use the
        # server-declared charset; if it's missing or the requests
        # default of ISO-8859-1 (almost always wrong for modern pages),
        # fall back to UTF-8.  Decoding errors are replaced rather than
        # raised — extractors care about structure, not byte fidelity.
        encoding = response.encoding
        if not encoding or encoding.lower() == "iso-8859-1":
            encoding = "utf-8"
        body = raw.decode(encoding, errors="replace")

        logger.info(
            "Fetched %s -> HTTP %s, %d bytes, content-type=%r",
            url,
            response.status_code,
            total,
            content_type,
        )
        return HttpDownload(
            body_bytes=raw,
            body=body,
            content_type=content_type,
            final_url=response.url,
        )
    finally:
        response.close()
