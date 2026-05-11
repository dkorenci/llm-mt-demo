"""Basic single-LLM translator, as a graph factory.

The basic translation step is one LLM call, but it is expressed as a
one-node LangGraph so it can be composed with multi-step workflows by
direct graph composition (``parent_graph.add_node("translate",
translator_graph)``) rather than via a wrapper-method call.

Three things live here:

* :data:`TRANSLATION_PROMPT` and :func:`make_instruction` -- the
  natural-language phrasing of the translation request.  Multi-step
  workflows reuse :func:`make_instruction` directly so the corrector
  sees the *same* instructions the translator was given.
* :func:`create_basic_translator` -- factory that takes a chat LLM and
  returns a compiled one-node graph over :class:`BasicState`.
* :func:`basic_initial_state` / :func:`basic_extract_result` -- the
  seed-state and result-extraction helpers used by the NONE workflow's
  :class:`~config.workflows.WorkflowEntry`.
"""
from __future__ import annotations

import functools
from typing import Any, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from config.languages import by_code

from .base import TranslationRequest, TranslationResult
from .retry import invoke_chain


# Prompt template.  ``{instruction}`` is filled from
# :func:`make_instruction`, and ``{text}`` from the request.  Keeping
# the instruction as a separate substitution lets wrapping workflows
# reuse the exact same phrasing in their own prompts.
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
    inspecting the post-run state -- including parent workflow graphs
    that compose by absorbing this graph as a node.
    """

    request: TranslationRequest
    instruction: str
    translation: str


def _language_name(code: str) -> str:
    """Return the human-readable English name of an ISO language code.

    Falls back to the code itself if the code is not in the catalogue.
    (Defensive: the form validates languages, so this should not happen
    in practice, but we never want the prompt template to crash.)
    """
    try:
        return by_code(code).name
    except KeyError:
        return code


def _strip(text: str) -> str:
    """Trim whitespace from an LLM response.

    Kept deliberately small: we ask the model in the prompt not to add
    preamble, quotes or fence markers, so trusting the model is fine
    for a demo.  Heavier cleanup here would mask prompt issues rather
    than fix them.
    """
    return text.strip()


def make_instruction(request: TranslationRequest) -> str:
    """Return the natural-language translation instruction.

    The string does *not* include the source text; it is the bare
    instruction (``"Translate the text from English to Croatian..."``)
    that wrapping workflows quote when explaining to a downstream LLM
    what the basic translator was asked to do.
    """
    return (
        f"Translate the text from {_language_name(request.source_lang)} "
        f"to {_language_name(request.target_lang)}. Reply with only the "
        f"translation, no preamble, no commentary, no quotes around the "
        f"translation, no language tags."
    )


def _translate_node(state: BasicState, llm: BaseChatModel) -> dict[str, Any]:
    """Single graph node: run one LLM call to translate the request text.

    Returns the partial state update LangGraph expects.  Empty input
    short-circuits to an empty translation without contacting the
    provider.
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


def create_basic_translator(llm: BaseChatModel) -> CompiledStateGraph:
    """Build a compiled one-node graph: entry -> translate -> END.

    The result is a fully functional :class:`CompiledStateGraph`: it can
    be invoked directly (for one-shot translation, used by the NONE
    workflow) or absorbed as a node in a parent graph (used by
    multi-step workflows that need an initial translation step).
    """
    graph: StateGraph = StateGraph(BasicState)
    # ``functools.partial`` binds the LLM so the node signature stays
    # ``(state) -> dict`` -- the shape LangGraph expects.
    graph.add_node("translate", functools.partial(_translate_node, llm=llm))
    graph.set_entry_point("translate")
    graph.add_edge("translate", END)
    return graph.compile()


# ---------------------------------------------------------------------------
# WorkflowEntry helpers (used by the NONE workflow entry)
# ---------------------------------------------------------------------------

def basic_initial_state(request: TranslationRequest) -> dict[str, Any]:
    """Seed-state for the basic translator's graph."""
    return {
        "request": request,
        "instruction": make_instruction(request),
        "translation": "",
    }


def basic_extract_result(state: dict[str, Any]) -> TranslationResult:
    """Pull the final translation out of the basic-translator's state."""
    return TranslationResult(text=state.get("translation", ""))
