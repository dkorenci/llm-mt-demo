"""LLM catalogue.

The catalogue is a list of typed spec records, one per available LLM.
Each spec is a member of a *discriminated union*:

- :class:`HFSpec` -- access via the native Hugging Face inference-
  endpoint protocol.  Carries HF-native knobs (``do_sample``,
  ``top_k``, ``repetition_penalty``, ``model_kwargs``).
- :class:`OpenAISpec` -- access via the OpenAI-compatible Chat
  Completions protocol.  Used here to talk to HF's OpenAI-compatible
  router (``base_url`` = ``https://router.huggingface.co/v1``); the
  same spec type also works against ``api.openai.com`` or any other
  compatible server.

The factory in :mod:`translator.translation.llm_factory` dispatches on
the spec's runtime type to build the matching LangChain wrapper.

Add or remove entries here to change what appears in the Model
dropdown; no other code needs to change.

Defaults are chosen for reproducible translation output: each spec
type selects greedy decoding in its backend's native idiom
(:class:`HFSpec`: ``temperature=None`` + ``do_sample=False``;
:class:`OpenAISpec`: ``temperature=0.0``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class HFSpec:
    """LLM accessed via the native HF inference-endpoint protocol.

    Built by the factory into a LangChain ``ChatHuggingFace`` wrapper
    around a ``HuggingFaceEndpoint``.

    Attributes:
        id: Stable registry key; used as the form value of the Model
            dropdown and as the cache key in the LLM factory.
        display_name: Human-readable label shown in the dropdown.
        repo_id: Hugging Face model repository ID
            (e.g. ``"google/gemma-3-12b-it"``).
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


@dataclass(frozen=True)
class OpenAISpec:
    """LLM accessed via the OpenAI-compatible Chat Completions protocol.

    Built by the factory into a LangChain ``ChatOpenAI`` wrapper.  Use
    this spec type to target HF's OpenAI-compatible router or any other
    server speaking OpenAI Chat Completions.

    HF-native knobs (``top_k``, ``repetition_penalty``, etc.) that the
    OpenAI Chat Completions schema has no field for go in ``extra_body``;
    HF's router and most OpenAI-compatible servers honour them via that
    passthrough, while strict ``api.openai.com`` ignores them.

    Attributes:
        id: Stable registry key; used as the form value of the Model
            dropdown and as the cache key in the LLM factory.
        display_name: Human-readable label shown in the dropdown.
        model: Model identifier passed to the OpenAI ``model`` field.
            For HF's router, provider routing is encoded in this string
            as ``"<repo_id>:<provider>"``
            (e.g. ``"google/gemma-3-12b-it:featherless-ai"``).
        base_url: OpenAI-compatible API base URL.
        temperature: Sampling temperature.  ``0.0`` selects greedy
            decoding under the OpenAI convention.
        max_tokens: Maximum number of generated tokens per call.
        top_p: Nucleus sampling cutoff (only used when sampling).
        extra_body: Extra JSON keys merged into the request body.  HF's
            router accepts ``top_k``, ``repetition_penalty`` and similar
            non-standard fields here; strict OpenAI ignores them.
    """

    id: str
    display_name: str
    model: str
    base_url: str
    temperature: float | None = 0.0
    max_tokens: int = 4096
    top_p: float | None = None
    extra_body: dict[str, Any] = field(default_factory=dict)


LLMSpec = HFSpec | OpenAISpec


# HF's OpenAI-compatible router base URL.  Provider routing is encoded
# in the ``model`` string itself (``<repo_id>:<provider>``), so the
# same base URL covers every provider routed through HF.
HF_OPENAI_BASE_URL: str = "https://router.huggingface.co/v1"


# Order is preserved in the Model dropdown; the first entry is the
# default selection.
LLMS: list[LLMSpec] = [
    OpenAISpec(
        id="gemma3-12b",
        display_name="Gemma 3 12B Instruct",
        model="google/gemma-3-12b-it:featherless-ai",
        base_url=HF_OPENAI_BASE_URL,
    ),
    OpenAISpec(
        id="gemma3-27b",
        display_name="Gemma 3 27B Instruct",
        model="google/gemma-3-27b-it:featherless-ai",
        base_url=HF_OPENAI_BASE_URL,
    ),
]


# Index by id for O(1) lookup; raises KeyError on unknown id (which the
# form/view layer is responsible for catching).
_BY_ID: dict[str, LLMSpec] = {spec.id: spec for spec in LLMS}


def list_llms() -> list[tuple[str, str]]:
    """Return Django-style ``[(id, display_name), ...]`` choices."""
    return [(spec.id, spec.display_name) for spec in LLMS]


def get_spec(llm_id: str) -> LLMSpec:
    """Look up a spec by its registry id."""
    return _BY_ID[llm_id]


def default_llm_id() -> str:
    """ID of the LLM pre-selected in the Model dropdown."""
    return LLMS[0].id
