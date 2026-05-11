"""Abstract interface for URL fetchers + extractors.

The translator app talks to *one* fetcher implementation through the
:class:`Fetcher` abstraction.  Swapping the backend means changing a
single line in :mod:`translator.fetcher.__init__` (or adding a
``config/fetcher.py`` analogous to ``config/models.py``).

Concrete fetchers are responsible for *both* steps:

1. Downloading the page in a way that looks like a real browser, and
2. Extracting the main article text (and a title, if available).

The two steps are kept inside the fetcher so each backend can pair the
HTTP layer with the extractor that handles its quirks (some extractors
prefer bytes, some text, some require the original URL for relative
links, etc.).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class FetchError(Exception):
    """Raised when fetching or extracting a URL fails.

    The message is safe to surface to the end user.
    """


@dataclass(frozen=True)
class FetchResult:
    """Successful outcome of fetching and extracting a URL.

    Attributes:
        text: Main article body, plain text.  May be empty if the page
            contained no extractable content.
        title: Page or article title, if the extractor returned one.
    """

    text: str
    title: str


class Fetcher(ABC):
    """Abstract base class for URL fetcher + extractor implementations."""

    id: str = ""
    display_name: str = ""

    @abstractmethod
    def fetch_and_extract(self, url: str) -> FetchResult:
        """Fetch ``url`` and return its extracted article text.

        Raises:
            FetchError: on any network, HTTP, or extraction failure.
        """
        raise NotImplementedError
