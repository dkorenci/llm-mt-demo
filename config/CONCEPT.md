# `config/` — application configuration

The modules in this package declare *what is available to the user* in
the demo.  Nothing in `config/` does any work itself: each module
exposes plain data structures (lists, instances) that the rest of the
app consumes.

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

### `llms.py`

The Hugging Face inference-endpoint LLM catalogue.  Exposes a list
`LLMS` of `LLMSpec` instances:

- `LLMSpec(id, display_name, repo_id, provider, ...)` — parameters for a
  single LLM.  `temperature=None` together with `do_sample=False`
  selects greedy decoding (the deterministic baseline).
- Helpers: `list_llms()` (Django-style choices), `get_spec(id)`,
  `default_llm_id()`.

Order is preserved in the *Model* dropdown; the first entry is the
default selection.  Adding a new LLM is one new `LLMSpec` entry — no
other code needs to change.

### `workflows.py`

The translation workflow registry.  Exposes a list `WORKFLOWS` of
`Workflow` instances.  Both the registry id (form value) and the
dropdown label are passed to each workflow's constructor, so this file
is the single place that *names* workflows.

The first entry is the default; it is always `NoneWorkflow` (the direct
pass-through to the chosen LLM-backed translator).

Phase 2 ships `NoneWorkflow` and `CorrectionWorkflow` (Self correction).
Adding another multi-step workflow is one new module under
`translator/translation/workflows/` and one append to this file.

## Wiring

The view layer never imports from these modules directly.  Instead it
goes through `translator/translation/registry.py`, which:

- builds a `BasicLLMTranslator` on demand for each LLM declared in
  `llms.py` (so the *Model* dropdown directly mirrors that catalogue),
  and
- indexes the `WORKFLOWS` list by `id` for the *Workflow* dropdown.
