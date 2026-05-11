# `translator/translation/` — LLM translation stack

The bridge between the Django UI and Hugging Face inference endpoints.
Every translation flow in this project is a **compiled LangGraph**:

- The *basic translator* is a one-node graph.
- A *workflow* is a graph that composes the basic translator's graph
  (as a subgraph node) with one or more additional nodes.

There is no `Translator` or `Workflow` class hierarchy.  Each
translator/workflow is built by a small factory function that returns
a `CompiledStateGraph`; the per-entry metadata (id, display name, seed
state, result extraction) lives in `config/`.

## Modules

### `base.py`

Two small dataclasses:

- `TranslationRequest(text, source_lang, target_lang)` — input.
- `TranslationResult(text)` — output.

### `llm_factory.py`

`create_llm(llm_id) -> BaseChatModel` — cached LangChain
`ChatHuggingFace` wrapper built from the spec in `config/llms.py`.

### `retry.py`

Single-place retry policy for every LLM call:

- `retry_with_backoff(delays, exceptions)` — decorator.  Default delays
  are `(1.0, 2.0, 4.0)` (three retries; four attempts total).
- `invoke_chain(chain, inputs)` — the one invocation point used by
  `_translate_node` and every workflow node, decorated with the default
  policy.  Tweak `DEFAULT_DELAYS` to change retry behaviour globally.

### `basic.py`

The basic translator — one LLM call, expressed as a one-node graph so
it can be slotted into workflow graphs by direct composition.

- `BasicState(TypedDict)` — `{request, instruction, translation}`.
- `TRANSLATION_PROMPT` — `"{instruction}\n\n<text>\n{text}\n</text>"`.
- `make_instruction(request)` — natural-language translation instruction
  (no source text).  Reused verbatim by `correction.py`, so the
  corrector sees exactly what the translator was told.
- `_translate_node(state, llm)` — single graph node; uses
  `invoke_chain` so the retry policy applies.
- `create_basic_translator(llm) -> CompiledStateGraph` — factory.
- `basic_initial_state(request)` / `basic_extract_result(state)` —
  helpers used by the NONE workflow's `WorkflowEntry`.

### `workflows/`

One module per workflow.  Each module exposes a factory function with
signature `(translator_graph, translator_llm, **knobs) ->
CompiledStateGraph` and -- if the workflow's state shape differs from
`BasicState` -- its own `*_initial_state` / `*_extract_result` helpers.

- `none.py` — `create_none_workflow(translator_graph, translator_llm)`
  returns the translator graph unchanged.  Its `WorkflowEntry` reuses
  `basic_initial_state` / `basic_extract_result`.
- `correction.py` — `create_correction_workflow(translator_graph,
  translator_llm, *, override_llm_id=None, reasoning_words=300)`.
  A three-node graph (`translate → correct → parse`) over
  `CorrectionState`, with the translator graph slotted in as the
  ``translate`` subgraph.  LangGraph passes overlapping state keys
  (`request`, `instruction`, `translation`) between parent and
  subgraph automatically, so no rename node is needed.
  Falls back to the initial translation and logs a warning (in
  `correction_extract_result`) if the corrector response is missing
  `<solution>...</solution>` tags.

### `registry.py`

The view-facing lookup layer.

- `list_translators()` — `[(id, display_name), ...]` mirroring
  `config.llms.LLMS`.
- `get_translator(llm_id) -> (CompiledStateGraph, BaseChatModel)` —
  returns the basic translator graph **and** the underlying LLM.
  Workflow factories use the LLM for their auxiliary calls (defaulting
  to "the same LLM" gives a natural self-correction).
- `list_workflows()` / `get_workflow_entry(id)` — workflow records
  declared in `config/workflows.py`.
- `default_translator_id()` / `default_workflow_id()` — first
  configured entry of each list.

Duplicate or empty workflow ids raise at import time, surfacing
configuration mistakes early.

## How the view runs a translation

```python
translator_graph, translator_llm = get_translator(model_id)
entry = get_workflow_entry(workflow_id)
graph = entry.factory(translator_graph, translator_llm)
state = graph.invoke(entry.initial_state(request))
result = entry.extract_result(state)
```

Three lookups, one graph build, one graph invocation.

## How to add things

### A new LLM

1. Append an `LLMSpec` to `LLMS` in `config/llms.py` (id, display name,
   HF `repo_id`, inference provider).
2. Done — the Model dropdown picks it up.

### A new multi-step workflow

1. Add a module under `translator/translation/workflows/` with:
   - the workflow's prompt strings,
   - a `TypedDict` for its graph state (overlap field names with
     `BasicState` where the basic translator's outputs should flow in),
   - one node function per step (each LLM call wrapped via
     `invoke_chain`),
   - a `create_<workflow>(translator_graph, translator_llm, **knobs)`
     factory that builds the graph (use
     `graph.add_node("translate", translator_graph)` to absorb the
     basic translator as a subgraph),
   - `_initial_state(request)` and `_extract_result(state)` helpers.
2. Append a `WorkflowEntry(id, display_name, factory, initial_state,
   extract_result)` to `WORKFLOWS` in `config/workflows.py`.
   Per-instance knobs (override LLM, reasoning length, …) are captured
   in a small closure around the factory.

The view, form, template, and CSS need no changes.

### A new single-translation prompt

The current `basic.py` ships one prompt; replacing it is a single-file
edit of `TRANSLATION_PROMPT` + `make_instruction`.  If you want
multiple prompt variants selectable from the UI, either:

- extend the Model dropdown to enumerate `(LLM, prompt)` pairs (turn
  `config/llms.py` into a richer translator catalogue), or
- add a separate `create_<variant>_translator(llm)` factory and a
  third dropdown for "Prompt style".

Either path stays in the function-based pattern -- a new factory + a
new config row.
