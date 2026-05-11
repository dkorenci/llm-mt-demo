"""Translation workflow registry.

A *workflow* wraps a basic translator and may invoke additional LLM
calls (for self-correction, back-translation, multi-model agreement,
etc.).  The default ``NONE`` workflow is a one-shot pass-through.

This is the single place where concrete :class:`Workflow` instances are
exposed to the UI -- and the only place that *names* them.  The ``id``
(form value) and ``display_name`` (menu label) of every entry are passed
to its constructor so renaming a menu item never requires touching the
workflow class itself.
"""
from __future__ import annotations

from translator.translation.base import Workflow
from translator.translation.workflows.correction import CorrectionWorkflow
from translator.translation.workflows.none import NoneWorkflow


# Order is preserved in the workflow dropdown; the first entry is the
# default selection.
WORKFLOWS: list[Workflow] = [
    NoneWorkflow(id="none", display_name="NONE"),
    CorrectionWorkflow(
        id="self-correction",
        display_name="Self correction",
        # Default: corrector LLM = translator's LLM (true self-correction).
        # Set ``override_llm_id="gemma3-27b"`` to use a different
        # factory LLM for the correction step.
    ),
]
