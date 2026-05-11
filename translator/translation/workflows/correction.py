"""Translation + Correction workflow, built as a LangGraph state machine.

The workflow performs a two-pass translation: an initial translation,
then a review-and-correct step driven by an auxiliary LLM that is
shown the original text, the initial translation, and the
instructions under which the initial translation was produced.  The
corrector is asked to reason briefly about possible improvements and
to end its response with the final translation enclosed in
``<solution>...</solution>`` tags, which the workflow then extracts.

The graph composes with the basic translator at the *graph* level:
the basic translator's compiled graph is slotted in as the first node
of this workflow's graph, and overlapping state keys
(``request``, ``instruction``, ``translation``) are auto-mapped between
the parent and the subgraph.

Graph::

    translate -> correct -> parse -> END

* **translate** is the basic translator's own compiled graph (added
  as a subgraph node).  It writes ``translation`` into the shared
  state.
* **correct** sends the original text, the initial translation, and
  the translator's own instruction string to an auxiliary LLM.  The
  aux LLM defaults to the LLM that drives the basic translator
  (giving a true *self*-correction); a different factory LLM can be
  selected per workflow registration via ``override_llm_id``.
* **parse** extracts the content of the ``<solution>...</solution>``
  tags from the correction response.  If the tags are missing the
  workflow keeps the initial translation as a safe fallback; the
  entry's ``extract_result`` logs the fallback.
"""
from __future__ import annotations

import functools
import logging
import re
from typing import Any, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ..base import TranslationRequest, TranslationResult
from ..basic import make_instruction
from ..llm_factory import create_llm
from ..retry import invoke_chain

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

# Substitutions:
#   ``prompt``           -- the *translation* instruction text, repeated
#                           to the corrector so it knows the constraints
#                           the initial translation was produced under.
#   ``original_text``    -- the source text being translated.
#   ``translation``      -- the initial translation written by the
#                           basic-translator subgraph.
#   ``reasoning_words``  -- target length of the corrector's reasoning
#                           section, in words.  Acts as a soft cap.
#
# The corrector is asked to end its response with the final answer
# enclosed in ``<solution>...</solution>`` tags; the parse node uses
# that to recover the corrected translation.
CORRECTION_PROMPT: str = (
    "Your job is to review a translation, and correct it if necessary.\n"
    "You will be given an original text, translation instructions, and "
    "the translation created according to these instructions.\n"
    "Respect the instructions!\n"
    "\n"
    "These are the instructions according to which the translation was "
    "produced:\n"
    "\"{prompt}\"\n"
    "\n"
    "Original text:\n"
    "{original_text}\n"
    "\n"
    "Translation:\n"
    "{translation}\n"
    "\n"
    "First, analyze the instructions, the original text, and the "
    "translation.\n"
    "Then reason about the improved solution (if any), and produce the "
    "solution.\n"
    "Try to keep the reasoning succinct, close to {reasoning_words} "
    "words!\n"
    "End with your final solution, enclosed within the <solution> "
    "</solution> tags.\n"
)


# Matches every ``<solution>...</solution>`` block.  Non-greedy so
# adjacent pairs don't bleed; ``re.DOTALL`` so the content may span
# multiple lines.  The parse node picks the *last* match -- the model
# sometimes echoes the tag name in its reasoning before the final
# answer.
_SOLUTION_RE: re.Pattern[str] = re.compile(
    r"<solution>\s*(.*?)\s*</solution>", re.DOTALL
)


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------

class CorrectionState(TypedDict):
    """Data threaded through the correction graph.

    The first three fields are shared with :class:`BasicState`, so the
    basic translator's subgraph (which reads ``request`` /
    ``instruction`` and writes ``translation``) composes here without a
    rename step.  The remaining fields are exclusive to this workflow.
    """

    request: TranslationRequest
    instruction: str
    translation: str                # initial translation (written by the subgraph)
    correction_raw: str             # full raw response from the correction LLM
    final_translation: str          # parsed <solution> content, or fallback
    solution_found: bool            # whether <solution> tags were present


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def _correct_node(
    state: CorrectionState,
    llm: BaseChatModel,
    reasoning_words: int,
) -> dict[str, Any]:
    """Ask the aux LLM to review and possibly rewrite the initial translation."""
    prompt = ChatPromptTemplate.from_messages([("human", CORRECTION_PROMPT)])
    chain = prompt | llm
    response = invoke_chain(
        chain,
        {
            "prompt": state["instruction"],
            "original_text": state["request"].text,
            "translation": state["translation"],
            "reasoning_words": reasoning_words,
        },
    )
    return {"correction_raw": response.content}


def _parse_node(state: CorrectionState) -> dict[str, Any]:
    """Extract the final translation from ``<solution>...</solution>`` tags.

    Falls back to the initial translation if no tags are present.  The
    ``solution_found`` flag in the result lets the workflow entry's
    ``extract_result`` log the fallback exactly once.
    """
    matches = _SOLUTION_RE.findall(state["correction_raw"])
    if matches:
        # Last block wins -- some models echo <solution> in their
        # reasoning before the final answer.
        return {
            "final_translation": matches[-1].strip(),
            "solution_found": True,
        }
    return {
        "final_translation": state["translation"],
        "solution_found": False,
    }


# ---------------------------------------------------------------------------
# Factory + WorkflowEntry helpers
# ---------------------------------------------------------------------------

def create_correction_workflow(
    translator_graph: CompiledStateGraph,
    translator_llm: BaseChatModel,
    *,
    override_llm_id: str | None = None,
    reasoning_words: int = 300,
) -> CompiledStateGraph:
    """Compose the basic translator graph with correction + parse nodes.

    Args:
        translator_graph: The basic translator's compiled graph.  Added
            as the ``translate`` node of this workflow's graph; its
            output ``translation`` field is read by the correction node.
        translator_llm: The LLM driving the basic translator.  Used as
            the default for the correction step (=> true self-correction).
        override_llm_id: If set, the correction step uses this factory
            LLM instead of the translator's own LLM.
        reasoning_words: Target length, in words, of the reasoning
            section the corrector is asked to produce.

    Returns:
        A compiled graph over :class:`CorrectionState`.
    """
    aux_llm: BaseChatModel = (
        create_llm(override_llm_id) if override_llm_id is not None
        else translator_llm
    )

    graph: StateGraph = StateGraph(CorrectionState)
    # Graph-level composition: the basic translator's compiled graph is
    # the ``translate`` node.  LangGraph passes overlapping state keys
    # (``request``, ``instruction``, ``translation``) in both directions
    # automatically, so the subgraph's ``translation`` output flows back
    # into the parent state without any glue.
    graph.add_node("translate", translator_graph)
    graph.add_node(
        "correct",
        functools.partial(_correct_node, llm=aux_llm, reasoning_words=reasoning_words),
    )
    graph.add_node("parse", _parse_node)
    graph.set_entry_point("translate")
    graph.add_edge("translate", "correct")
    graph.add_edge("correct", "parse")
    graph.add_edge("parse", END)
    return graph.compile()


def correction_initial_state(request: TranslationRequest) -> dict[str, Any]:
    """Seed-state for the correction graph (matches :class:`CorrectionState`)."""
    return {
        "request": request,
        "instruction": make_instruction(request),
        "translation": "",
        "correction_raw": "",
        "final_translation": "",
        "solution_found": False,
    }


def correction_extract_result(state: dict[str, Any]) -> TranslationResult:
    """Pull the final translation from the correction graph's output state.

    Logs a warning if the corrector did not emit a usable
    ``<solution>`` block; the result text is the fallback (the initial
    translation), so the user still gets something.
    """
    if not state.get("solution_found", False):
        logger.warning(
            "Correction workflow: no <solution> tags found in corrector "
            "response; falling back to the initial translation."
        )
    return TranslationResult(text=state.get("final_translation", ""))
