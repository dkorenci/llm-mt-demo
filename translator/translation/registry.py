"""Lookup tables that bridge :mod:`config` and the view layer.

The translator side is built from the LLM catalogue in :mod:`config.llms`:
each LLM declared there becomes one entry in the Model dropdown, and the
view resolves a selected entry to a cached :class:`BasicLLMTranslator`
wrapping the corresponding factory LLM.

The workflow side is unchanged in shape: workflows are declared as
instances in :mod:`config.workflows` and indexed here by their ``id``.
"""
from __future__ import annotations

import functools

from config.llms import LLMS, default_llm_id, get_spec, list_llms
from config.workflows import WORKFLOWS as _CONFIGURED_WORKFLOWS

from .base import Translator, Workflow
from .basic import BasicLLMTranslator


# ---------------------------------------------------------------------------
# Translators -- built on demand from the LLM catalogue
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def _build_translator(llm_id: str) -> Translator:
    """Return a cached :class:`BasicLLMTranslator` for one LLM id."""
    return BasicLLMTranslator(llm_id)


def list_translators() -> list[tuple[str, str]]:
    """Return ``[(id, display_name), ...]`` for the Model dropdown."""
    return list_llms()


def get_translator(identifier: str) -> Translator:
    """Resolve a Model dropdown selection to a translator instance.

    Raises:
        KeyError: if ``identifier`` does not match any LLM in
            :mod:`config.llms`.  The view catches this and renders the
            generic error notice.
    """
    # Validate via the LLM catalogue first so unknown ids raise a
    # ``KeyError`` *before* we cache anything.
    get_spec(identifier)
    return _build_translator(identifier)


def default_translator_id() -> str:
    """ID of the LLM pre-selected in the Model dropdown."""
    return default_llm_id()


# ---------------------------------------------------------------------------
# Workflows -- declarative list of pre-built instances
# ---------------------------------------------------------------------------

def _build_workflow_index(items: list[Workflow]) -> dict[str, Workflow]:
    """Build a ``{id: instance}`` index, raising on missing or duplicate ids."""
    index: dict[str, Workflow] = {}
    for item in items:
        identifier = getattr(item, "id", "") or ""
        if not identifier:
            raise ValueError(f"Configured workflow {item!r} has no id")
        if identifier in index:
            raise ValueError(
                f"Duplicate workflow id {identifier!r} in configuration"
            )
        index[identifier] = item
    return index


WORKFLOWS: dict[str, Workflow] = _build_workflow_index(
    list(_CONFIGURED_WORKFLOWS)
)


def list_workflows() -> list[tuple[str, str]]:
    """Return ``[(id, display_name), ...]`` in the configured order."""
    return [(w.id, w.display_name) for w in _CONFIGURED_WORKFLOWS]


def get_workflow(identifier: str) -> Workflow:
    """Look up a workflow instance by its registry id."""
    return WORKFLOWS[identifier]


def default_workflow_id() -> str:
    """ID of the workflow pre-selected in the dropdown (``"none"`` by convention)."""
    return next(iter(WORKFLOWS))


# Re-export for downstream callers that want the raw catalogue order.
__all__ = [
    "LLMS",
    "WORKFLOWS",
    "default_translator_id",
    "default_workflow_id",
    "get_translator",
    "get_workflow",
    "list_translators",
    "list_workflows",
]
