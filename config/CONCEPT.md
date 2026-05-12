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

The LLM catalogue.  Exposes a list `LLMS` whose entries are members of
a discriminated union — one dataclass per access protocol:

- `HFSpec(id, display_name, repo_id, provider, ...)` — accessed via the
  native HF inference-endpoint protocol.  Carries HF-native knobs
  (`do_sample`, `top_k`, `repetition_penalty`, `model_kwargs`).
  Greedy decoding = `temperature=None` + `do_sample=False`.
- `OpenAISpec(id, display_name, model, base_url, ...)` — accessed via
  the OpenAI-compatible Chat Completions protocol.  Used to talk to
  HF's OpenAI-compatible router (`base_url` =
  `https://router.huggingface.co/v1`, with provider routing encoded in
  the `model` string as `"<repo_id>:<provider>"`) or any other
  OpenAI-compatible server.  Greedy decoding = `temperature=0.0`.
  Non-standard knobs (`top_k`, `repetition_penalty`, ...) go in
  `extra_body`; HF's router honours them, strict OpenAI ignores them.
- `LLMSpec = HFSpec | OpenAISpec` — the union type used elsewhere.
- Helpers: `list_llms()` (Django-style choices), `get_spec(id)`,
  `default_llm_id()`.

The factory in `translator/translation/llm_factory.py` dispatches on
the spec's runtime type to build the matching LangChain wrapper.

Order is preserved in the *Model* dropdown; the first entry is the
default selection.  Adding a new LLM is one new spec entry of either
type — no other code needs to change.

### `workflows.py`

The translation workflow registry.  Exposes a list `WORKFLOWS` of
`WorkflowEntry` records.  Each entry has:

- `id` — form value (used by the dropdown / view).
- `display_name` — menu label.
- `factory(translator_graph, translator_llm) -> CompiledStateGraph` —
  builds the workflow's compiled graph.  Per-workflow knobs (e.g.
  `override_llm_id`, `reasoning_words`) are captured in a closure
  around the factory.
- `initial_state(request) -> dict` — seeds the graph's input state.
- `extract_result(state) -> TranslationResult` — turns the graph's
  final state into the user-visible result (and is where workflow-
  specific fallback warnings are logged).

This file is the single place that *names* workflows.  The first entry
is the default; it is conventionally the `NONE` pass-through.

Ships with `NONE` and `Self correction`.  Adding a multi-step
workflow is one new module under `translator/translation/workflows/`
plus one append to this list.

## Wiring

The view layer never imports from these modules directly.  Instead it
goes through `translator/translation/registry.py`, which:

- builds a `BasicLLMTranslator` on demand for each LLM declared in
  `llms.py` (so the *Model* dropdown directly mirrors that catalogue),
  and
- indexes the `WORKFLOWS` list by `id` for the *Workflow* dropdown.
