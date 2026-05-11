"""Translation + Correction workflow, expressed as a LangGraph graph.

Port of the procedural ``TranslationCorrectionWorkflow`` from
``ma_prototypes/translation_workflows/translation_correction_workflow.py``,
re-expressed as a three-node LangGraph state machine so the data flow
(initial translation, correction-agent raw response, parsed
``<solution>`` content, "solution found" flag, instruction text) is
explicit and inspectable.

Graph::

    translate -> correct -> parse -> END

* **translate** delegates to the supplied basic translator, so the
  workflow composes with any LLM in the factory without per-LLM code.
* **correct** sends the original text, the initial translation, and the
  translator's own instruction string to an auxiliary LLM, using the
  exact correction prompt from the reference implementation.  The aux
  LLM defaults to the translator's own LLM (``translator.llm``), giving
  a true *self*-correction.  A different factory LLM can be selected
  per workflow instance via the ``override_llm_id`` constructor arg.
* **parse** extracts the content of the ``<solution>...</solution>`` tags
  from the correction response.  If the tags are missing the workflow
  falls back to the initial translation, exactly as the reference does,
  and logs a warning.

Display name and registry id are constructor arguments so the menu label
is owned by :mod:`config.workflows`, not by this module.
"""
from __future__ import annotations

import logging
import re
from typing import TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ..base import Translator, TranslationRequest, TranslationResult, Workflow
from ..llm_factory import create_llm
from ..retry import invoke_chain

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt (verbatim from the reference workflow)
# ---------------------------------------------------------------------------

# Substitutions: prompt, original_text, translation, reasoning_words.
# ``prompt`` here is the *translation* instruction text, repeated to the
# corrector so it knows the constraints the initial translation was
# produced under.
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


# Matches the *last* <solution>...</solution> block, in case the model
# echoes the tag name earlier in its reasoning.  ``re.DOTALL`` so the
# content may span multiple lines; the search is non-greedy so adjacent
# tag pairs don't bleed into each other.
_SOLUTION_RE: re.Pattern[str] = re.compile(
    r"<solution>\s*(.*?)\s*</solution>", re.DOTALL
)


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------

class CorrectionState(TypedDict):
    """Data threaded through the graph nodes.

    All intermediate artefacts of the reference workflow are kept here so
    they remain available for inspection / logging after the run.
    """

    request: TranslationRequest
    instruction: str
    initial_translation: str
    correction_raw: str
    final_translation: str
    solution_found: bool


# ---------------------------------------------------------------------------
# Workflow class
# ---------------------------------------------------------------------------

class CorrectionWorkflow(Workflow):
    """Translate, then self-correct (or correct with a configured aux LLM).

    The ``id`` and ``display_name`` class attributes are placeholders; the
    constructor accepts overrides so :mod:`config.workflows` is the only
    file that names workflows.
    """

    id: str = "self-correction"
    display_name: str = "Self correction"

    def __init__(
        self,
        override_llm_id: str | None = None,
        reasoning_words: int = 300,
        id: str | None = None,
        display_name: str | None = None,
    ) -> None:
        """Configure a workflow instance.

        Args:
            override_llm_id: If set, the correction step uses this
                factory LLM instead of ``translator.llm``.  Lets a
                registration in :mod:`config.workflows` pair a small
                translator with a larger corrector (or vice versa)
                without code changes.
            reasoning_words: Target length, in words, of the reasoning
                section the corrector is asked to produce.  Substituted
                into :data:`CORRECTION_PROMPT`.
            id: Override the registry id (form value).
            display_name: Override the dropdown label.
        """
        if id is not None:
            self.id = id
        if display_name is not None:
            self.display_name = display_name
        self._override_llm_id: str | None = override_llm_id
        self._reasoning_words: int = reasoning_words

    # ------------------------------------------------------------------
    # Workflow interface
    # ------------------------------------------------------------------

    def run(
        self,
        request: TranslationRequest,
        translator: Translator,
    ) -> TranslationResult:
        graph = self._build_graph(translator)
        out: CorrectionState = graph.invoke(  # type: ignore[assignment]
            {
                "request": request,
                "instruction": self._instruction_for(translator, request),
                "initial_translation": "",
                "correction_raw": "",
                "final_translation": "",
                "solution_found": False,
            }
        )
        if not out["solution_found"]:
            logger.warning(
                "Correction workflow: no <solution> tags in corrector response; "
                "falling back to the initial translation."
            )
        return TranslationResult(text=out["final_translation"])

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _aux_llm(self, translator: Translator) -> BaseChatModel:
        """Return the LLM that runs the correction step.

        Defaults to the basic translator's own LLM (a self-correction).
        Falls back to a factory LLM if an override was configured.
        """
        if self._override_llm_id is not None:
            return create_llm(self._override_llm_id)
        return translator.llm  # type: ignore[attr-defined]

    def _instruction_for(
        self, translator: Translator, request: TranslationRequest
    ) -> str:
        """Read the translator's own instruction string if it exposes one.

        Concrete basic translators expose ``.instruction(request)`` so
        their prompt text remains the single source of truth.  If a
        future translator does not (e.g. a remote-API wrapper), we fall
        back to a generic phrasing so the workflow still runs.
        """
        getter = getattr(translator, "instruction", None)
        if callable(getter):
            return getter(request)
        return (
            f"Translate the text from {request.source_lang} to "
            f"{request.target_lang}."
        )

    def _build_graph(self, translator: Translator) -> CompiledStateGraph:
        """Build and compile the three-node graph for one run.

        Built per-run rather than once at construction time so each call
        captures the specific ``translator`` instance the view selected.
        Compilation is cheap relative to the LLM calls.
        """
        aux: BaseChatModel = self._aux_llm(translator)
        reasoning_words = self._reasoning_words

        def translate_node(state: CorrectionState) -> dict:
            """Step 1: produce the initial translation via the basic translator."""
            result = translator.translate(state["request"])
            return {"initial_translation": result.text}

        def correct_node(state: CorrectionState) -> dict:
            """Step 2: ask the aux LLM to review and possibly rewrite."""
            prompt = ChatPromptTemplate.from_messages(
                [("human", CORRECTION_PROMPT)]
            )
            chain = prompt | aux
            response = invoke_chain(
                chain,
                {
                    "prompt": state["instruction"],
                    "original_text": state["request"].text,
                    "translation": state["initial_translation"],
                    "reasoning_words": reasoning_words,
                },
            )
            return {"correction_raw": response.content}

        def parse_node(state: CorrectionState) -> dict:
            """Step 3: extract <solution>...</solution>, or fall back to step 1."""
            # ``findall`` so we keep the *last* solution block if the
            # corrector emitted more than one (e.g. once in its reasoning
            # and again at the end).
            matches = _SOLUTION_RE.findall(state["correction_raw"])
            if matches:
                return {
                    "final_translation": matches[-1].strip(),
                    "solution_found": True,
                }
            return {
                "final_translation": state["initial_translation"],
                "solution_found": False,
            }

        graph: StateGraph = StateGraph(CorrectionState)
        graph.add_node("translate", translate_node)
        graph.add_node("correct", correct_node)
        graph.add_node("parse", parse_node)
        graph.set_entry_point("translate")
        graph.add_edge("translate", "correct")
        graph.add_edge("correct", "parse")
        graph.add_edge("parse", END)
        return graph.compile()
