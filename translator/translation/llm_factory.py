"""Factory that turns an :class:`~config.llms.LLMSpec` into a LangChain LLM.

The factory is intentionally narrow: it knows about LLM parameter specs
and the Hugging Face inference endpoint wrapper, and nothing else.
Translators and workflows depend on it; it depends on nothing project-
specific beyond the LLM catalogue.

Instances are cached with :func:`functools.lru_cache` so that repeated
requests share the same ``ChatHuggingFace`` wrapper (the underlying HTTP
endpoint is stateless; reusing wrappers keeps LangChain's per-instance
caches warm).
"""
from __future__ import annotations

import functools

from langchain_core.language_models import BaseChatModel
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

from config.llms import LLMSpec, get_spec
from django.conf import settings


@functools.lru_cache(maxsize=None)
def create_llm(llm_id: str) -> BaseChatModel:
    """Return a cached chat-LLM wrapper for the spec named ``llm_id``.

    Raises:
        KeyError: if ``llm_id`` is not declared in :mod:`config.llms`.
    """
    spec: LLMSpec = get_spec(llm_id)
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
