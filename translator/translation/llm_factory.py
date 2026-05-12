"""Factory that turns an LLM spec into a LangChain chat-LLM wrapper.

Dispatches on the spec's runtime type so each access protocol stays in
its own builder, with no cross-talk:

* :class:`~config.llms.HFSpec` -> ``ChatHuggingFace`` over the native
  Hugging Face inference-endpoint protocol.
* :class:`~config.llms.OpenAISpec` -> ``ChatOpenAI`` over the
  OpenAI-compatible Chat Completions protocol (used here to talk to
  HF's OpenAI-compatible router; the same builder also works against
  ``api.openai.com`` or any other compatible server).

Instances are cached with :func:`functools.lru_cache` so repeated
requests share the same wrapper (the underlying HTTP endpoint is
stateless; reusing wrappers keeps LangChain's per-instance caches warm).
"""
from __future__ import annotations

import functools

from langchain_core.language_models import BaseChatModel
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_openai import ChatOpenAI

from config.llms import HFSpec, LLMSpec, OpenAISpec, get_spec
from django.conf import settings


def _create_hf_llm(spec: HFSpec) -> BaseChatModel:
    """Build a ``ChatHuggingFace`` wrapper from an :class:`HFSpec`."""
    endpoint = HuggingFaceEndpoint(
        repo_id=spec.repo_id,
        huggingfacehub_api_token=settings.HF_INFERENCE_ENDPOINT_TOKEN,
        provider=spec.provider,
        # All Gemma 3-it variants are chat models; "conversational" is the
        # task type that routes through the HF Hub's chat-completions API.
        task="conversational",
        max_new_tokens=spec.max_new_tokens,
        temperature=spec.temperature,
        do_sample=spec.do_sample,
        top_p=spec.top_p,
        top_k=spec.top_k,
        repetition_penalty=spec.repetition_penalty,
        model_kwargs=spec.model_kwargs,
    )
    return ChatHuggingFace(llm=endpoint)


def _create_openai_llm(spec: OpenAISpec) -> BaseChatModel:
    """Build a ``ChatOpenAI`` wrapper from an :class:`OpenAISpec`.

    The API key is read from ``settings.HF_INFERENCE_ENDPOINT_TOKEN`` --
    the same token works against HF's OpenAI-compatible router.  A
    future spec pointing at a non-HF OpenAI-compatible host can reuse
    this token or motivate adding a separate setting.
    """
    return ChatOpenAI(
        model=spec.model,
        base_url=spec.base_url,
        api_key=settings.HF_INFERENCE_ENDPOINT_TOKEN,
        temperature=spec.temperature,
        max_tokens=spec.max_tokens,
        top_p=spec.top_p,
        # ``extra_body`` is the escape hatch for non-standard params
        # (``top_k``, ``repetition_penalty``, ...).  HF's router and most
        # OpenAI-compatible servers honour them this way; strict
        # ``api.openai.com`` silently drops unknown keys.
        extra_body=spec.extra_body or None,
    )


@functools.lru_cache(maxsize=None)
def create_llm(llm_id: str) -> BaseChatModel:
    """Return a cached chat-LLM wrapper for the spec named ``llm_id``.

    Dispatches on the spec's runtime type.  Add a new branch here when
    a new spec subtype is introduced; the rest of the codebase only
    sees ``BaseChatModel``.

    Raises:
        KeyError: if ``llm_id`` is not declared in :mod:`config.llms`.
        TypeError: if the spec has an unrecognised subtype (programmer
            error -- a spec class was added without a matching factory
            branch).
    """
    spec: LLMSpec = get_spec(llm_id)
    if isinstance(spec, HFSpec):
        return _create_hf_llm(spec)
    if isinstance(spec, OpenAISpec):
        return _create_openai_llm(spec)
    raise TypeError(f"Unknown LLM spec type: {type(spec).__name__}")
