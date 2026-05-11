"""The trivial pass-through workflow.

Always present in the dropdown as ``NONE`` -- a single direct call to
the selected translator.  The ``id`` and ``display_name`` are
constructor arguments so the menu label can be renamed entirely from
:mod:`config.workflows` without touching this file.
"""
from __future__ import annotations

from ..base import Translator, TranslationRequest, TranslationResult, Workflow


class NoneWorkflow(Workflow):
    """One-shot pass-through: delegate directly to the translator."""

    # Class-level defaults; the constructor lets configuration override them.
    id: str = "none"
    display_name: str = "NONE"

    def __init__(
        self,
        id: str | None = None,
        display_name: str | None = None,
    ) -> None:
        if id is not None:
            self.id = id
        if display_name is not None:
            self.display_name = display_name

    def run(
        self,
        request: TranslationRequest,
        translator: Translator,
    ) -> TranslationResult:
        return translator.translate(request)
