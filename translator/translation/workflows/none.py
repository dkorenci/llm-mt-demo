"""The trivial pass-through workflow.

The "graph" is literally the basic translator's compiled graph -- there
is nothing to add.  Kept as its own module so every workflow lives
under :mod:`translator.translation.workflows`, but the body is one
line.
"""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph


def create_none_workflow(
    translator_graph: CompiledStateGraph,
    translator_llm: BaseChatModel,  # unused; signature matches other workflow factories
) -> CompiledStateGraph:
    """Return the translator graph unchanged."""
    return translator_graph
