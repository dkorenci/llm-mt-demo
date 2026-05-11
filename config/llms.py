"""Hugging Face inference-endpoint LLM catalogue.

This module is purely declarative: it lists the LLMs that are available
to the translator and the multi-step workflows.  The factory in
:mod:`translator.translation.llm_factory` reads these specs and builds
the corresponding LangChain ``ChatHuggingFace`` wrappers.

Add or remove entries here to change what appears in the Model dropdown
and what the workflows can use as an override LLM; no other code needs
to change.

Defaults reflect the reference factory:
``temperature=None`` together with ``do_sample=False`` requests greedy
decoding (no sampling), which is the deterministic baseline appropriate
for a translation demo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LLMSpec:
    """Parameters for one Hugging Face inference-endpoint LLM.

    Attributes:
        id: Stable registry key; used as the form value of the Model
            dropdown and as the cache key in the LLM factory.
        display_name: Human-readable label shown in the dropdown.
        repo_id: Hugging Face model repository ID (e.g.
            ``"google/gemma-3-12b-it"``).
        provider: Inference provider routed through the HF Hub
            (e.g. ``"novita"``, ``"featherless-ai"``).
        temperature: Sampling temperature.  ``None`` together with
            ``do_sample=False`` selects greedy decoding.
        max_new_tokens: Maximum number of generated tokens per call.
        do_sample: Whether to sample.  ``False`` = greedy.
        top_p: Nucleus sampling cutoff (only used when sampling).
        top_k: Top-k cutoff (only used when sampling).
        repetition_penalty: Repetition penalty (``None`` = provider default).
        model_kwargs: Extra provider-specific kwargs forwarded as-is.
    """

    id: str
    display_name: str
    repo_id: str
    provider: str
    temperature: float | None = None
    max_new_tokens: int = 4096
    do_sample: bool = False
    top_p: float | None = None
    top_k: int | None = None
    repetition_penalty: float | None = None
    model_kwargs: dict[str, Any] = field(default_factory=dict)


# Order is preserved in the Model dropdown; the first entry is the
# default selection.
LLMS: list[LLMSpec] = [
    LLMSpec(
        id="gemma3-12b",
        display_name="Gemma 3 12B Instruct",
        repo_id="google/gemma-3-12b-it",
        provider="featherless-ai",
    ),
    LLMSpec(
        id="gemma3-27b",
        display_name="Gemma 3 27B Instruct",
        repo_id="google/gemma-3-27b-it",
        provider="featherless-ai",
    ),
]


# Index by id for O(1) lookup; raises KeyError on unknown id (which the
# form/view layer is responsible for catching).
_BY_ID: dict[str, LLMSpec] = {spec.id: spec for spec in LLMS}


def list_llms() -> list[tuple[str, str]]:
    """Return Django-style ``[(id, display_name), ...]`` choices."""
    return [(spec.id, spec.display_name) for spec in LLMS]


def get_spec(llm_id: str) -> LLMSpec:
    """Look up an :class:`LLMSpec` by its registry id."""
    return _BY_ID[llm_id]


def default_llm_id() -> str:
    """ID of the LLM pre-selected in the Model dropdown."""
    return LLMS[0].id
