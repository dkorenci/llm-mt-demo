"""LLM-backed translator registry.

This module is the *single* place where concrete :class:`Translator`
implementations are wired into the UI.  The rest of the application only
talks to translators through the abstract interface in
:mod:`translator.translation.base` and looks them up via
:mod:`translator.translation.registry`.

Phase 1 ships a stub translator only; Phase 2 will append real Hugging
Face / LangChain-backed entries here.
"""
from __future__ import annotations

from translator.translation.base import Translator
from translator.translation.stub import EchoTranslator

# Order is preserved in the model dropdown; the first entry is the default
# selection.
TRANSLATORS: list[Translator] = [
    EchoTranslator(),
    # Phase 2: add Hugging Face / LangChain-backed translator instances here.
]
