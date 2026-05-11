"""Single-page view that drives the entire demo.

The view is intentionally stateless: every request carries the full
per-tab state in the submitted form, and every response renders that
state back into the page.  This keeps cloned tabs independent of each
other (no shared server-side session is consulted).

Submit-button dispatch is done via a hidden ``action`` field on the
form.  The supported actions are listed in :mod:`translator.forms`.
"""
from __future__ import annotations

import logging

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from config import languages

from .fetcher import FetchError, fetch_and_extract
from .forms import (
    ACTION_CLONE,
    ACTION_FETCH,
    ACTION_TRANSLATE,
    TranslateForm,
)
from .translation.base import TranslationRequest
from .translation.registry import (
    get_translator,
    get_workflow_entry,
)

logger = logging.getLogger(__name__)


def index(request: HttpRequest) -> HttpResponse:
    """Render the demo page, dispatching on the submitted ``action``.

    GET renders an empty form with defaults.  POST inspects the
    ``action`` field on the form and performs the matching side-effect
    (translate / fetch URL / clone), then re-renders the form with all
    fields preserved.
    """
    error: str | None = None

    if request.method == "POST":
        form = TranslateForm(request.POST)
        # The action dropdown defaults to "" if not provided; we treat
        # that as "no-op re-render" (which is what Clone-to-Tab also
        # effectively does on the server side).
        if form.is_valid():
            action = form.cleaned_data.get("action") or ""
            if action == ACTION_TRANSLATE:
                error = _do_translate(form)
            elif action == ACTION_FETCH:
                error = _do_fetch(form)
            elif action == ACTION_CLONE:
                # No server-side work; the browser opened a new tab via
                # ``formtarget="_blank"`` and we simply echo the state
                # back so the new tab is pre-populated.
                pass
            # Any other (or empty) action falls through to a plain
            # re-render, which is the desired behaviour.
    else:
        form = TranslateForm()

    return render(
        request,
        "translator/index.html",
        {
            "form": form,
            "error": error,
        },
    )


# ---------------------------------------------------------------------------
# Action helpers
# ---------------------------------------------------------------------------

# Sentinel string returned by the action helpers when *anything* goes
# wrong.  The template renders a single generic notice (``"An error
# occurred. Check the log."``) regardless of the value; the actual
# cause is recorded in the log via ``logger.*`` calls below.
_ERROR: str = "error"


def _do_translate(form: TranslateForm) -> str | None:
    """Run the selected workflow + translator and write back into ``form``.

    Returns :data:`_ERROR` if anything prevented translation, else
    ``None``.  The translated text is injected into the form's bound
    ``target_text`` field so the template renders it.  Specific
    failure reasons are written to the log, never shown in the UI.
    """
    data = form.cleaned_data
    source_lang = data.get("source_language") or languages.DEFAULT_SOURCE
    target_lang = data.get("target_language") or languages.DEFAULT_TARGET
    text = data.get("source_text") or ""

    if not text.strip():
        logger.warning("Translate aborted: empty source text.")
        return _ERROR
    if source_lang == target_lang:
        logger.warning(
            "Translate aborted: identical source/target language %r.",
            source_lang,
        )
        return _ERROR

    try:
        translator_graph, translator_llm = get_translator(data.get("model") or "")
        entry = get_workflow_entry(data.get("workflow") or "")
    except KeyError as exc:
        logger.warning(
            "Translate aborted: unknown model or workflow selection (%s).",
            exc,
        )
        return _ERROR

    request = TranslationRequest(
        text=text, source_lang=source_lang, target_lang=target_lang
    )
    try:
        # Build the workflow-specific graph (basic translator subgraph
        # included where relevant), invoke it on the seed state, and
        # let the entry pull the user-facing translation back out.
        graph = entry.factory(translator_graph, translator_llm)
        final_state = graph.invoke(entry.initial_state(request))
        result = entry.extract_result(final_state)
    except Exception:
        logger.exception(
            "Translation failed (model=%s workflow=%s %s->%s)",
            data.get("model"),
            data.get("workflow"),
            source_lang,
            target_lang,
        )
        return _ERROR

    _replace_field(form, "target_text", result.text)
    return None


def _do_fetch(form: TranslateForm) -> str | None:
    """Fetch and extract the URL, then write the body into ``source_text``.

    Returns :data:`_ERROR` on any failure (network, extraction, empty
    result); the actual reason is recorded in the log.
    """
    url = form.cleaned_data.get("url") or ""
    if not url:
        logger.warning("Fetch aborted: empty URL.")
        return _ERROR

    try:
        result = fetch_and_extract(url)
    except FetchError as exc:
        # ``fetch_and_extract`` already logged the full traceback; here
        # we just record the URL once at warning level.
        logger.warning("URL fetch failed for %s: %s", url, exc)
        return _ERROR

    if not result.text:
        logger.warning(
            "URL fetch returned empty article text for %s (title=%r)",
            url,
            result.title,
        )
        return _ERROR

    _replace_field(form, "source_text", result.text)
    return None


def _replace_field(form: TranslateForm, name: str, value: str) -> None:
    """Mutate a bound form's submitted data so the rendered widget shows ``value``.

    Django form widgets render from ``form.data`` on bound forms (and from
    ``form.initial`` on unbound forms).  When we want a server-side
    computation to appear in the page on re-render, the cleanest path is
    to update ``form.data`` and force the form to re-bind.
    """
    # ``form.data`` is a QueryDict; make it mutable, replace, then
    # invalidate the cached cleaned_data so the form behaves consistently
    # if anything reads it again.
    data = form.data.copy()
    data[name] = value
    form.data = data
    if hasattr(form, "_errors"):
        form._errors = None  # type: ignore[attr-defined]
    if "cleaned_data" in form.__dict__:
        del form.__dict__["cleaned_data"]
    form.is_bound = True
    form.full_clean()
