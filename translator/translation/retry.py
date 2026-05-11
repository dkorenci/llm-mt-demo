"""Retry-with-backoff helper for transient LLM-call failures.

Cloud-hosted LLM endpoints (Hugging Face inference providers, in our
case) fail intermittently with timeouts, 5xx responses, or short-lived
provider hiccups.  Every chain invocation in this project goes through
:func:`invoke_chain`, which wraps the actual ``chain.invoke`` call in a
small retry loop so a single transient blip does not cause a user-
visible error.

The default policy is three retries with exponential backoff
(1 s -> 2 s -> 4 s), totalling at most ~7 s of waiting before giving up.
After the budget is exhausted, the last exception is re-raised so the
view layer can log it and render its generic error notice.
"""
from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)


# Inter-attempt waits, in seconds.  ``len(DEFAULT_DELAYS)`` retries are
# performed after the initial attempt, for a total of 4 attempts.
DEFAULT_DELAYS: tuple[float, ...] = (1.0, 2.0, 4.0)


F = TypeVar("F", bound=Callable[..., Any])


def retry_with_backoff(
    delays: tuple[float, ...] = DEFAULT_DELAYS,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[F], F]:
    """Decorator that retries the wrapped callable on exception.

    Args:
        delays: Sequence of inter-attempt sleep durations, in seconds.
            ``delays[i]`` is the wait *before* retry ``i + 1``.  Total
            number of attempts is ``len(delays) + 1``.
        exceptions: Exception types that trigger a retry.  Defaults to
            ``Exception`` (anything but ``BaseException``-only errors
            like ``KeyboardInterrupt``).

    Returns:
        A decorator that wraps a callable with the retry policy.

    Notes:
        Every failed attempt is logged at WARNING with the attempt index
        and the next delay; the final failure is logged with the total
        attempt count before re-raising.
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempts = len(delays) + 1
            for attempt in range(attempts):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    # Final attempt failed -- give up and propagate.
                    if attempt == attempts - 1:
                        logger.warning(
                            "LLM call failed after %d attempts: %s",
                            attempts,
                            exc,
                        )
                        raise
                    delay = delays[attempt]
                    logger.warning(
                        "LLM call failed (attempt %d/%d): %s; retrying in %.1fs",
                        attempt + 1,
                        attempts,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
            # Unreachable: the loop either returns or raises.
            raise RuntimeError("retry_with_backoff: unreachable")

        return wrapper  # type: ignore[return-value]

    return decorator


@retry_with_backoff()
def invoke_chain(chain: Any, inputs: dict[str, Any]) -> Any:
    """Run ``chain.invoke(inputs)`` under the default retry policy.

    This is the single LLM invocation point used by the basic translator
    and every workflow node, so the retry policy lives in exactly one
    place.  Tweak :data:`DEFAULT_DELAYS` (or pass custom ``delays`` to
    a fresh ``retry_with_backoff`` decorator) to change it.
    """
    return chain.invoke(inputs)
