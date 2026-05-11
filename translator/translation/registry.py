"""Lookup glue between :mod:`config` and the view layer.

Two registries:

* **Translators** -- one per LLM declared in :mod:`config.llms`.
  :func:`get_translator` returns the compiled basic-translator graph
  paired with the underlying LLM, so workflow factories can use the
  LLM for their auxiliary calls (defaulting to "the same LLM" gives a
  natural self-correction).
* **Workflows** -- a dict of :class:`~config.workflows.WorkflowEntry`
  records indexed by id, declared in :mod:`config.workflows`.

Both registries are cached: each LLM produces one
``(CompiledStateGraph, BaseChatModel)`` pair for the lifetime of the
process, and the workflow entries are simply imported once.
"""
from __future__ import annotations

import functools

from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from config.llms import LLMS, default_llm_id, get_spec, list_llms
from config.workflows import WORKFLOWS as _CONFIGURED_WORKFLOWS
from config.workflows import WorkflowEntry

from .basic import create_basic_translator
from .llm_factory import create_llm


# ---------------------------------------------------------------------------
# Translators -- built on demand from the LLM catalogue
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def _build_translator(llm_id: str) -> tuple[CompiledStateGraph, BaseChatModel]:
    """Return a cached (graph, llm) pair for one LLM id."""
    llm = create_llm(llm_id)
    return create_basic_translator(llm), llm


def list_translators() -> list[tuple[str, str]]:
    """Return ``[(id, display_name), ...]`` for the Model dropdown."""
    return list_llms()


def get_translator(identifier: str) -> tuple[CompiledStateGraph, BaseChatModel]:
    """Resolve a Model dropdown selection to ``(basic-translator graph, LLM)``.

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
# Workflows -- declarative list of entries
# ---------------------------------------------------------------------------

def _build_workflow_index(
    items: list[WorkflowEntry],
) -> dict[str, WorkflowEntry]:
    """Build a ``{id: entry}`` index, raising on missing or duplicate ids."""
    index: dict[str, WorkflowEntry] = {}
    for entry in items:
        if not entry.id:
            raise ValueError(f"Configured workflow {entry!r} has no id")
        if entry.id in index:
            raise ValueError(
                f"Duplicate workflow id {entry.id!r} in configuration"
            )
        index[entry.id] = entry
    return index


WORKFLOWS: dict[str, WorkflowEntry] = _build_workflow_index(
    list(_CONFIGURED_WORKFLOWS)
)


def list_workflows() -> list[tuple[str, str]]:
    """Return ``[(id, display_name), ...]`` in the configured order."""
    return [(w.id, w.display_name) for w in _CONFIGURED_WORKFLOWS]


def get_workflow_entry(identifier: str) -> WorkflowEntry:
    """Look up a :class:`WorkflowEntry` by its registry id."""
    return WORKFLOWS[identifier]


def default_workflow_id() -> str:
    """ID of the workflow pre-selected in the dropdown (``"none"`` by convention)."""
    return next(iter(WORKFLOWS))


__all__ = [
    "LLMS",
    "WORKFLOWS",
    "WorkflowEntry",
    "default_translator_id",
    "default_workflow_id",
    "get_translator",
    "get_workflow_entry",
    "list_translators",
    "list_workflows",
]
