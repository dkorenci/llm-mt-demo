# `translator/translation/` — translation abstractions

The bridge between the Django UI and any number of LLM translation
backends.  The view depends *only* on the types declared here; no
concrete backend is imported anywhere outside this package and
`config/`.

## Modules

### `base.py`

The abstract interface.  All five names are part of the public contract:

- `TranslationRequest(text, source_lang, target_lang)` — frozen
  dataclass holding the inputs to a translation call.
- `TranslationResult(text)` — frozen dataclass for the output.  Reserved
  for non-breaking extension in Phase 2 (latency, token usage,
  intermediate steps, …).
- `Translator` — ABC.  Subclasses set `id` (registry key) and
  `display_name` (dropdown label) as class attributes and implement
  `translate(request) -> TranslationResult`.
- `Workflow` — ABC.  Wraps a translator and may invoke it multiple
  times.  Subclasses set `id`, `display_name`, and implement
  `run(request, translator) -> TranslationResult`.

### `stub.py`

Phase-1 implementations exercised by the demo UI before any LLMs are
wired up:

- `EchoTranslator` (`id="stub-echo"`) — returns
  `f"[{source}→{target}] {text}"`.
- `NoneWorkflow` (`id="none"`) — single direct invocation of the
  chosen translator.

`NoneWorkflow` is intended to stay in Phase 2 as the default
"no special workflow" option.

### `registry.py`

Indexes the lists declared in `config/models.py` and
`config/workflows.py` by their `id` and offers:

- `list_translators()` / `list_workflows()` —
  `[(id, display_name), ...]` for use as form choices.
- `get_translator(id)` / `get_workflow(id)` — lookup by id.
- `default_translator_id()` / `default_workflow_id()` — the first
  configured entry, used as the dropdown default.

Duplicate or empty ids raise at import time, which surfaces
configuration mistakes early.

## Adding a Phase-2 translator

1. Write a new module under `translator/translation/` (e.g.
   `huggingface.py`) defining a class that subclasses `Translator`,
   sets `id` and `display_name`, and implements `translate()`.
2. Append an instance of that class to `TRANSLATORS` in
   `config/models.py`.
3. Add any new third-party packages to `requirements.txt`.

The view, form, template, and CSS need no changes.
