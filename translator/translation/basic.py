"""Basic single-LLM translator, expressed as a LangGraph state machine.

The basic translation step is structurally a single LLM call, but it is
implemented here as a one-node LangGraph so every translation flow in
this project -- one-shot or multi-step -- uses the same primitives
(``TypedDict`` state, node functions, ``StateGraph`` construction,
``compile()``, ``invoke()``).  This makes the basic translator and the
multi-step workflows in :mod:`translator.translation.workflows` look
structurally identical, matches the reference style in
``cdt_mcqa_filtering_agent.py``, and keeps the door open for future
features (streaming intermediate state, graph visualisation) without
special-casing one-shot translation.

Two public contracts the workflow layer relies on are preserved:

* ``.llm`` -- the underlying LangChain chat model, used by default by
  multi-step workflows that need to issue auxiliary calls.
* ``.instruction(req)`` -- the natural-language instruction string used
  in the translation prompt (without the source text).  Workflows that
  embed the original instruction in a downstream prompt (the
  ``CorrectionWorkflow`` does this verbatim) read it from here so the
  prompt text in :mod:`basic` stays the single source of truth.
"""
from __future__ import annotations

import functools
from typing import TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

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


class BasicState(TypedDict):
    """State threaded through the one-node basic-translation graph.

    Carrying all three fields explicitly means every artefact of the
    translation step (the request, the instruction string actually sent
    to the LLM, and the resulting translation) is visible to anything
    inspecting the post-run state -- including multi-step workflows
    that want to compose at the graph level.
    """

    request: TranslationRequest
    instruction: str
    translation: str


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


def _translate_node(state: BasicState, llm: BaseChatModel) -> dict:
    """Single graph node: run one LLM call to translate the request text.

    Returns the partial state update LangGraph expects (a dict of the
    keys this node writes).  Empty input short-circuits to an empty
    translation without contacting the provider.
    """
    request = state["request"]
    if not request.text.strip():
        return {"translation": ""}
    prompt = ChatPromptTemplate.from_messages([("human", TRANSLATION_PROMPT)])
    chain = prompt | llm
    response = invoke_chain(
        chain,
        {
            "instruction": state["instruction"],
            "text": request.text,
        },
    )
    return {"translation": _strip(response.content)}


class BasicLLMTranslator(Translator):
    """One factory LLM + the translation prompt, executed as a 1-node graph.

    Constructed by the registry on demand for a given ``llm_id``; the
    registry caches instances so each LLM has at most one wrapper -- and
    therefore at most one compiled graph -- for the lifetime of the
    process.
    """

    def __init__(self, llm_id: str) -> None:
        spec = get_spec(llm_id)
        self.id: str = spec.id
        self.display_name: str = spec.display_name
        # Public attribute on purpose: the documented hook by which
        # multi-step workflows reach the underlying LLM.
        self.llm: BaseChatModel = create_llm(llm_id)
        # Compile once per translator instance; the graph is reused on
        # every translate() call.  Compilation is cheap relative to the
        # LLM call (microseconds vs seconds) and only happens once
        # because the registry caches the translator itself.
        self._graph: CompiledStateGraph = self._build_graph()

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
        """Run the compiled graph for one translation request.

        The initial state seeds ``instruction`` from
        :meth:`instruction` so the graph carries the same string the
        node will eventually substitute into the prompt -- and that
        wrapping workflows can read from the final state if they
        compose at the graph level.
        """
        out: BasicState = self._graph.invoke(  # type: ignore[assignment]
            {
                "request": request,
                "instruction": self.instruction(request),
                "translation": "",
            }
        )
        return TranslationResult(text=out["translation"])

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build_graph(self) -> CompiledStateGraph:
        """Build the trivial one-node graph: entry -> translate -> END."""
        graph: StateGraph = StateGraph(BasicState)
        # ``functools.partial`` binds the LLM so the node signature stays
        # ``(state) -> dict`` -- the shape LangGraph expects.
        graph.add_node("translate", functools.partial(_translate_node, llm=self.llm))
        graph.set_entry_point("translate")
        graph.add_edge("translate", END)
        return graph.compile()
