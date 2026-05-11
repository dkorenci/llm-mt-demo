"""Lookup tables that bridge :mod:`config` and the view layer.

The view reads available translators and workflows from this module and
resolves the user's selection back to a concrete instance.  Concrete
classes themselves are declared in :mod:`config.models` and
:mod:`config.workflows`; this module merely indexes them.

Importing this module triggers the import of the config modules, which
in turn instantiate the concrete classes once at process start.
"""
from __future__ import annotations

from config.models import TRANSLATORS as _CONFIGURED_TRANSLATORS
from config.workflows import WORKFLOWS as _CONFIGURED_WORKFLOWS

from .base import Translator, Workflow


def _build_index(items: list, kind: str) -> dict[str, object]:
    """Build a ``{id: instance}`` index, raising on missing or duplicate ids."""
    index: dict[str, object] = {}
    for item in items:
        identifier = getattr(item, "id", "") or ""
        if not identifier:
            raise ValueError(f"Configured {kind} {item!r} has no id")
        if identifier in index:
            raise ValueError(
                f"Duplicate {kind} id {identifier!r} in configuration"
            )
        index[identifier] = item
    return index


# Public indexes ---------------------------------------------------------------------

TRANSLATORS: dict[str, Translator] = _build_index(  # type: ignore[assignment]
    list(_CONFIGURED_TRANSLATORS), "translator"
)
WORKFLOWS: dict[str, Workflow] = _build_index(  # type: ignore[assignment]
    list(_CONFIGURED_WORKFLOWS), "workflow"
)


def list_translators() -> list[tuple[str, str]]:
    """Return ``[(id, display_name), ...]`` in the configured order."""
    return [(t.id, t.display_name) for t in _CONFIGURED_TRANSLATORS]


def list_workflows() -> list[tuple[str, str]]:
    """Return ``[(id, display_name), ...]`` in the configured order."""
    return [(w.id, w.display_name) for w in _CONFIGURED_WORKFLOWS]


def get_translator(identifier: str) -> Translator:
    """Look up a translator instance by its registry id."""
    return TRANSLATORS[identifier]


def get_workflow(identifier: str) -> Workflow:
    """Look up a workflow instance by its registry id."""
    return WORKFLOWS[identifier]


def default_translator_id() -> str:
    """ID of the translator pre-selected in the model dropdown."""
    return next(iter(TRANSLATORS))


def default_workflow_id() -> str:
    """ID of the workflow pre-selected in the workflow dropdown (``"none"``)."""
    return next(iter(WORKFLOWS))
