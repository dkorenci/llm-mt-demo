"""Shared dataclasses for the translation pipeline.

The view layer constructs a :class:`TranslationRequest` from form
input, hands it to the registry's run-glue, and receives a
:class:`TranslationResult` back.  Both are :func:`dataclasses.dataclass`
records so they are trivially passable through LangGraph state and
trivially extensible (adding a field is non-breaking thanks to
``dataclass``-style construction at call sites).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TranslationRequest:
    """Input for a single translation operation.

    Attributes:
        text: The source text to translate.  May be empty; the basic
            translator short-circuits empty input without contacting
            the provider.
        source_lang: ISO 639-1 code of the source language (e.g. ``"en"``).
        target_lang: ISO 639-1 code of the target language (e.g. ``"hr"``).
    """

    text: str
    source_lang: str
    target_lang: str


@dataclass(frozen=True)
class TranslationResult:
    """Output of a translation operation.

    Attributes:
        text: The translated text.
    """

    text: str
    # Reserved for future fields: token usage, latency, intermediate
    # steps, confidence, etc.  Adding fields here is non-breaking
    # thanks to ``dataclass``-style construction at call sites.
