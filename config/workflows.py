"""Translation workflow registry.

A *workflow* wraps a translator and may invoke it multiple times (for
back-translation, self-correction, agreement between two models, etc.).
The default ``NONE`` workflow is a one-shot pass-through.

This is the single place where concrete :class:`Workflow` implementations
are exposed to the UI.  Phase 2 will append multi-step workflows here
without any change to the views, forms, or templates.
"""
from __future__ import annotations

from translator.translation.base import Workflow
from translator.translation.stub import NoneWorkflow

# Order is preserved in the workflow dropdown; the first entry is the
# default selection (``NONE``).
WORKFLOWS: list[Workflow] = [
    NoneWorkflow(),
    # Phase 2: add multi-step workflow instances here.
]
