"""Basic single-LLM translator.

Wraps one factory LLM with a translation prompt.  Concrete dropdown
entries in the Model selector resolve to one of these via the registry;
adding a new entry to :mod:`config.llms` is the only thing required to
make a new LLM appear in the UI.

The instance carries two public contracts that wrapping workflows rely
on:

* ``.llm`` -- the underlying LangChain chat model, used by default by
  multi-step workflows that need to issue auxiliary calls.
* ``.instruction(req)`` -- the natural-language instruction string used
  in the translation prompt (without the source text).  Workflows that
  embed the original instruction in a downstream prompt (the
  ``CorrectionWorkflow`` does this verbatim) read it from here, so the
  prompt text in :mod:`basic` stays the single source of truth.
"""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

from config.languages import by_code
from config.llms import get_spec

from .base import Translator, TranslationRequest, TranslationResult
from .llm_factory import create_llm
from .retry import invoke_chain


# Prompt template.  ``{instruction}`` is filled from
# :meth:`BasicLLMTranslator.instruction`, and ``{text}`` from the
# request.  Keeping the instruction as a separate substitution lets
# wrapping workflows reuse the exact same phrasing in their own prompts.
TRANSLATION_PROMPT: str = (
    "{instruction}\n"
    "\n"
    "<text>\n"
    "{text}\n"
    "</text>"
)


def _language_name(code: str) -> str:
    """Return the human-readable English name of an ISO language code.

    Falls back to the code itself if the code is not in the catalogue
    (defensive: the form validates languages, so this should not happen
    in practice, but we never want the prompt template to crash).
    """
    try:
        return by_code(code).name
    except KeyError:
        return code


def _strip(text: str) -> str:
    """Trim whitespace from an LLM response.

    Kept deliberately small: we ask the model in the prompt not to add
    preamble, quotes or fence markers, so trusting the model is fine for
    a demo.  Adding more aggressive cleanup here would mask prompt
    issues rather than fix them.
    """
    return text.strip()


class BasicLLMTranslator(Translator):
    """One factory LLM + the translation prompt; implements :class:`Translator`.

    Constructed by the registry on demand for a given ``llm_id``; the
    registry caches instances so each LLM has at most one wrapper for
    the lifetime of the process.
    """

    def __init__(self, llm_id: str) -> None:
        spec = get_spec(llm_id)
        self.id: str = spec.id
        self.display_name: str = spec.display_name
        # Public attribute on purpose: this is the documented hook by
        # which multi-step workflows reach the underlying LLM.
        self.llm: BaseChatModel = create_llm(llm_id)

    def instruction(self, request: TranslationRequest) -> str:
        """Return the natural-language translation instruction used in the prompt.

        The string does *not* include the source text; it is the bare
        instruction (``"Translate the text from English to Croatian..."``)
        that wrapping workflows may quote when explaining to a
        downstream LLM what the basic translator was asked to do.
        """
        return (
            f"Translate the text from {_language_name(request.source_lang)} "
            f"to {_language_name(request.target_lang)}. Reply with only the "
            f"translation, no preamble, no commentary, no quotes around the "
            f"translation, no language tags."
        )

    def translate(self, request: TranslationRequest) -> TranslationResult:
        """Translate ``request.text`` via one LLM call.

        Empty input short-circuits to an empty result (a single empty
        chat-completion call to the provider is wasteful and sometimes
        outright errors).
        """
        if not request.text.strip():
            return TranslationResult(text="")

        prompt = ChatPromptTemplate.from_messages([("human", TRANSLATION_PROMPT)])
        chain = prompt | self.llm
        response = invoke_chain(
            chain,
            {
                "instruction": self.instruction(request),
                "text": request.text,
            },
        )
        return TranslationResult(text=_strip(response.content))
