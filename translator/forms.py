"""Form definition for the single demo page.

The form carries the *entire* per-tab state on every request: language
selections, model/workflow choice, URL, source text and target text.
Because no session-side state is used, two tabs holding two forms are
completely independent (which is what "Clone to Tab" relies on).
"""
from __future__ import annotations

from django import forms

from config import languages
from translator.translation import registry


# Allowed values for the hidden ``action`` field, dispatched by the view.
ACTION_TRANSLATE: str = "translate"
ACTION_FETCH: str = "fetch"
ACTION_CLONE: str = "clone"
_ACTION_CHOICES: list[tuple[str, str]] = [
    (ACTION_TRANSLATE, "Translate"),
    (ACTION_FETCH, "Fetch URL"),
    (ACTION_CLONE, "Clone to tab"),
]


class TranslateForm(forms.Form):
    """Main form bound to every interactive control on the page.

    Field names line up 1:1 with the HTML inputs in ``index.html``.
    All fields are optional at the form level; the view enforces the
    constraints that matter per action.
    """

    source_language = forms.ChoiceField(
        choices=languages.choices,
        required=False,
        initial=languages.DEFAULT_SOURCE,
    )
    target_language = forms.ChoiceField(
        choices=languages.choices,
        required=False,
        initial=languages.DEFAULT_TARGET,
    )

    # Model and workflow choices are computed dynamically so changes in
    # ``config/`` take effect on next server start without touching this
    # module.
    model = forms.ChoiceField(
        choices=registry.list_translators,
        required=False,
    )
    workflow = forms.ChoiceField(
        choices=registry.list_workflows,
        required=False,
    )

    url = forms.URLField(
        required=False,
        assume_scheme="https",
    )
    source_text = forms.CharField(required=False, widget=forms.Textarea)
    target_text = forms.CharField(required=False, widget=forms.Textarea)

    # Set by whichever submit button fired the request; the view branches
    # on this value.
    action = forms.ChoiceField(
        choices=_ACTION_CHOICES,
        required=False,
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Pre-select sensible defaults in the model/workflow dropdowns the
        # first time the page is rendered (when no value has been POSTed).
        self.fields["model"].initial = registry.default_translator_id()
        self.fields["workflow"].initial = registry.default_workflow_id()
