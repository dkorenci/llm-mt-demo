"""Phase-1 stub implementations of :class:`Translator` and :class:`Workflow`.

These are placeholders so the full UI pipeline (form → workflow →
translator → rendered target text) can be exercised end-to-end without
any LLM calls.  Phase 2 will leave these in place (the ``NONE`` workflow
is genuinely useful) but add real translators alongside ``EchoTranslator``.
"""
from __future__ import annotations

from .base import Translator, TranslationRequest, TranslationResult, Workflow


class EchoTranslator(Translator):
    """Trivial translator that echoes the input with a directional tag.

    Used in Phase 1 so the UI can be developed and demonstrated before
    any LLM integration is in place.
    """

    id: str = "stub-echo"
    display_name: str = "Echo (stub)"

    def translate(self, request: TranslationRequest) -> TranslationResult:
        if not request.text:
            return TranslationResult(text="")
        tag = f"[{request.source_lang}→{request.target_lang}] "
        return TranslationResult(text=tag + request.text)


class NoneWorkflow(Workflow):
    """The default workflow: a single, direct translator invocation.

    Always available regardless of which extra workflows are configured.
    """

    id: str = "none"
    display_name: str = "NONE"

    def run(
        self, request: TranslationRequest, translator: Translator
    ) -> TranslationResult:
        return translator.translate(request)
