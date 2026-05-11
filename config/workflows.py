"""Translation workflow registry.

A workflow is a compiled LangGraph that, given a translation request
and a basic-translator graph + its LLM, runs whatever orchestration the
workflow defines (one-shot pass-through, self-correction, …).  This
module is the single place where workflow instances are declared *and*
named -- the ``id`` (form value) and ``display_name`` (menu label) of
every entry live here, not in any workflow module.

Each registered entry is a :class:`WorkflowEntry` record with four
function fields:

* ``factory(translator_graph, translator_llm) -> CompiledStateGraph``
  -- builds the final graph for one (workflow, translator) combination.
* ``initial_state(request) -> dict`` -- seeds the graph's input state.
* ``extract_result(state) -> TranslationResult`` -- converts the
  graph's final state into the result the view writes back.

Adding a new multi-step workflow is one new module under
:mod:`translator.translation.workflows` plus one append here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from translator.translation.base import TranslationRequest, TranslationResult
from translator.translation.basic import basic_extract_result, basic_initial_state
from translator.translation.workflows.correction import (
    correction_extract_result,
    correction_initial_state,
    create_correction_workflow,
)
from translator.translation.workflows.none import create_none_workflow


GraphFactory = Callable[[CompiledStateGraph, BaseChatModel], CompiledStateGraph]
InitialStateFn = Callable[[TranslationRequest], dict[str, Any]]
ExtractResultFn = Callable[[dict[str, Any]], TranslationResult]


@dataclass(frozen=True)
class WorkflowEntry:
    """One row in the Workflow dropdown.

    Holds the user-visible identity (``id`` / ``display_name``) and the
    three callables the view glue needs to actually run a request
    through the workflow.
    """

    id: str
    display_name: str
    factory: GraphFactory
    initial_state: InitialStateFn
    extract_result: ExtractResultFn


def _correction_factory(
    override_llm_id: str | None = None,
    reasoning_words: int = 300,
) -> GraphFactory:
    """Capture per-workflow knobs in a closure with the standard factory shape."""

    def factory(
        translator_graph: CompiledStateGraph,
        translator_llm: BaseChatModel,
    ) -> CompiledStateGraph:
        return create_correction_workflow(
            translator_graph,
            translator_llm,
            override_llm_id=override_llm_id,
            reasoning_words=reasoning_words,
        )

    return factory


# Order is preserved in the Workflow dropdown; the first entry is the
# default selection.
WORKFLOWS: list[WorkflowEntry] = [
    WorkflowEntry(
        id="none",
        display_name="NONE",
        factory=create_none_workflow,
        initial_state=basic_initial_state,
        extract_result=basic_extract_result,
    ),
    WorkflowEntry(
        id="self-correction",
        display_name="Self correction",
        factory=_correction_factory(),
        initial_state=correction_initial_state,
        extract_result=correction_extract_result,
        # To register a corrector that uses a different factory LLM:
        # factory=_correction_factory(override_llm_id="gemma3-27b"),
    ),
]
