# `config/` — application configuration

The three modules in this package declare *what is available to the
user* in the demo.  Nothing in `config/` does any work itself: each
module exposes plain data structures (lists, instances) that the rest
of the app consumes.

## Modules

### `languages.py`

The catalogue of languages offered in the source/target selectors.

- `Language` — frozen dataclass (`code`, `name`, with a `label` property
  formatted as `"Name (CODE)"`).
- `PINNED` — languages that always render at the top.  Currently
  English and Croatian.
- `OTHERS` — the rest of the catalogue, kept alphabetical by ISO code.
- `ALL` — `PINNED + OTHERS`, the single ordered list rendered into the
  dropdowns.
- `choices()` — returns Django `[(value, label), ...]` choices.
- `is_valid(code)` / `by_code(code)` — lookup helpers.
- `DEFAULT_SOURCE` / `DEFAULT_TARGET` — initial dropdown values.

To add or remove a language, edit `OTHERS` (or `PINNED`); no other code
needs to change.

### `models.py`

Declares the LLM-backed translators available in the *Model* dropdown.
The module exposes a single list, `TRANSLATORS`, of `Translator`
instances.  Order is preserved in the UI; the first entry is the
default selection.

Phase 1 ships a single `EchoTranslator` stub.  Phase 2 will append real
Hugging Face / LangChain-backed instances here.

### `workflows.py`

Declares the translation workflows available in the *Workflow*
dropdown.  Exposes `WORKFLOWS`, a list of `Workflow` instances.  The
first entry is the default; it is always `NoneWorkflow` (the direct
pass-through to the chosen translator).

Multi-step workflows (back-translation, agreement between two models,
self-correction, …) will be added here in Phase 2.

## Wiring

The view layer never imports from these modules directly.  Instead it
goes through `translator/translation/registry.py`, which indexes the
`TRANSLATORS` / `WORKFLOWS` lists by their `id` attribute and exposes
lookup helpers.
