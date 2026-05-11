"""URL fetching + main-text extraction.

The translator app talks to a single :class:`Fetcher` instance via the
module-level :func:`fetch_and_extract` convenience function.  Which
backend is active is chosen at import time from the ``MT_FETCHER``
environment variable; ``run.sh --fetcher <name>`` is the canonical way
to set it.  The default is ``"trafilatura"``: it is actively maintained
and copes with more layouts than the alternative, at the cost of
occasionally including some boilerplate text.

Adding a new backend: subclass :class:`Fetcher` in a new module under
this package, then register it in :data:`_FETCHERS` below.
"""
from __future__ import annotations

import logging
import os
from typing import Final

from .base import Fetcher, FetchError, FetchResult
from .newspaper_impl import NewspaperFetcher
from .trafilatura_impl import TrafilaturaFetcher

logger = logging.getLogger(__name__)


# Registry of available backends, keyed by the short name used by the
# ``--fetcher`` CLI flag and the ``MT_FETCHER`` environment variable.
_FETCHERS: Final[dict[str, type[Fetcher]]] = {
    NewspaperFetcher.id: NewspaperFetcher,      # "newspaper"
    TrafilaturaFetcher.id: TrafilaturaFetcher,  # "trafilatura"
}

# Backend used when ``MT_FETCHER`` is unset or empty.
_DEFAULT_NAME: Final[str] = TrafilaturaFetcher.id


def _select_fetcher() -> Fetcher:
    """Instantiate the fetcher named by ``MT_FETCHER`` (or the default)."""
    name = (os.environ.get("MT_FETCHER") or _DEFAULT_NAME).strip().lower()
    if name not in _FETCHERS:
        valid = ", ".join(sorted(_FETCHERS))
        logger.warning(
            "Unknown MT_FETCHER=%r; falling back to %r. Valid choices: %s",
            name,
            _DEFAULT_NAME,
            valid,
        )
        name = _DEFAULT_NAME
    logger.info("URL fetcher backend: %s", name)
    return _FETCHERS[name]()


# Single active fetcher instance.  The selection happens at import time
# so the choice survives Django's autoreloader without needing further
# wiring.
DEFAULT_FETCHER: Fetcher = _select_fetcher()


def fetch_and_extract(url: str) -> FetchResult:
    """Convenience wrapper around :data:`DEFAULT_FETCHER`."""
    return DEFAULT_FETCHER.fetch_and_extract(url)


def available_fetchers() -> list[str]:
    """Return the list of registered backend names (for help text, tests)."""
    return sorted(_FETCHERS)


__all__ = [
    "DEFAULT_FETCHER",
    "Fetcher",
    "FetchError",
    "FetchResult",
    "available_fetchers",
    "fetch_and_extract",
]
