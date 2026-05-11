"""Abstract translation interfaces.

These are the *only* types that the view layer should depend on.  Adding
a new translator backend in Phase 2 means writing a concrete
:class:`Translator` subclass and appending it to
:data:`config.models.TRANSLATORS`; the view does not change.

The :class:`Workflow` abstraction sits one level above and may invoke a
translator multiple times (e.g. back-translation, self-correction, or
agreement between two models).  The default ``NONE`` workflow is a
one-shot pass-through (see :mod:`translator.translation.stub`).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class TranslationRequest:
    """Input for a single translation operation.

    Attributes:
        text: The source text to translate.  May be empty; concrete
            translators are expected to short-circuit empty input.
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
    # Reserved for Phase 2: token usage, latency, intermediate steps,
    # confidence, etc.  Adding fields here is non-breaking thanks to
    # ``dataclass``-style construction at call sites.


class Translator(ABC):
    """Abstract base class for all translation backends.

    Subclasses must set the class attributes :attr:`id` (registry key,
    stable identifier used by the form) and :attr:`display_name` (label
    shown in the model dropdown), and implement :meth:`translate`.
    """

    # Concrete subclasses override these.  They are declared here so that
    # the registry layer and the view can read them in a uniform way.
    id: str = ""
    display_name: str = ""

    @abstractmethod
    def translate(self, request: TranslationRequest) -> TranslationResult:
        """Translate ``request.text`` from its source to its target language."""
        raise NotImplementedError


class Workflow(ABC):
    """Abstract base class for translation workflows.

    A workflow orchestrates one or more invocations of a :class:`Translator`.
    The simplest workflow (``NONE``) just delegates a single call; more
    elaborate workflows may chain calls, run multiple translators in
    parallel, or post-edit results.
    """

    id: str = ""
    display_name: str = ""

    @abstractmethod
    def run(
        self, request: TranslationRequest, translator: Translator
    ) -> TranslationResult:
        """Execute the workflow, returning the final translation result."""
        raise NotImplementedError
