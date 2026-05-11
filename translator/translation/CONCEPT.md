# `translator/translation/` — LLM translation stack

The bridge between the Django UI and Hugging Face inference endpoints.
The package is split into three transparently separated layers:

1. **LLM definitions** (`config/llms.py` + `llm_factory.py`) — what LLMs
   exist and how to build them.
2. **Basic translator** (`basic.py`) — wraps one LLM with the
   translation prompt.
3. **Workflows** (`workflows/`) — LangGraph state machines that
   orchestrate one or more LLM calls around a basic translator.

The view depends *only* on the ABCs in `base.py` and on the registry
helpers; no concrete backend is imported anywhere outside this package
and `config/`.

## Modules

### `base.py`

The abstract interface.  Five public names:

- `TranslationRequest(text, source_lang, target_lang)` — frozen
  dataclass for the inputs to a translation call.
- `TranslationResult(text)` — frozen dataclass for the output.  Reserved
  for non-breaking extension (latency, token usage, intermediate
  steps, …).
- `Translator` — ABC.  Subclasses set `id` (registry key) and
  `display_name` (dropdown label) and implement
  `translate(request) -> TranslationResult`.
- `Workflow` — ABC.  Wraps a translator and may invoke it multiple
  times.  Subclasses set `id`, `display_name`, and implement
  `run(request, translator) -> TranslationResult`.

### `llm_factory.py`

`create_llm(llm_id) -> BaseChatModel` — builds a cached LangChain
`ChatHuggingFace` wrapper from the spec in `config/llms.py`.  Cached via
`functools.lru_cache` so each LLM has at most one wrapper for the life
of the process.

### `retry.py`

Single-place retry policy for every LLM call:

- `retry_with_backoff(delays, exceptions)` — decorator.  Default delays
  are `(1.0, 2.0, 4.0)` (three retries; four attempts total).
- `invoke_chain(chain, inputs)` — the one invocation point used by
  `basic.py` and every workflow node, decorated with the default
  policy.  Tweak `DEFAULT_DELAYS` to change retry behaviour globally.

Each failed attempt is logged at WARNING with the next delay; the final
failure is logged with the total attempt count before re-raising.

### `basic.py`

`BasicLLMTranslator(llm_id)` — concrete `Translator` that wraps one
factory LLM.  Implemented as a **one-node LangGraph state machine** so
the basic translator and the multi-step workflows in `workflows/` use
identical primitives (`TypedDict` state, node functions, `StateGraph`
construction, `compile()`, `invoke()`).

- `BasicState(TypedDict)` — `{request, instruction, translation}`.
  Every artefact of the translation step is in the state, so anything
  inspecting the post-run state (logging, future graph-level
  composition by a multi-step workflow) sees a single, complete record.
- The graph is compiled once in `__init__` and reused on every
  `translate()` call.  The registry caches the translator instance, so
  one compilation per LLM per process.
- `TRANSLATION_PROMPT` — `"{instruction}\n\n<text>\n{text}\n</text>"`.
  The instruction substitution is the single source of truth used by
  both the prompt and by workflows that quote the instruction
  downstream.

Two public contracts the workflow layer depends on:

- `.llm` — the underlying `BaseChatModel`, used by default by
  multi-step workflows for their auxiliary LLM calls.
- `.instruction(request)` — the natural-language translation
  instruction (without the source text).  Workflows that embed the
  original instruction in a downstream prompt (e.g. `CorrectionWorkflow`)
  read it here.

### `workflows/`

One module per workflow.  Like `basic.py`, every workflow is built as a
LangGraph state machine (with the trivial exception of `NoneWorkflow`,
which delegates directly):

- `none.py` — `NoneWorkflow`, the default pass-through.  Single direct
  call to `translator.translate(request)`; no extra graph nodes (the
  basic translator's own graph runs underneath).
- `correction.py` — `CorrectionWorkflow`, *Self correction*.  A
  three-node LangGraph (`translate → correct → parse`) ported from
  `bench-translate`'s `translation_correction_workflow.py`.  The
  correction prompt is the verbatim text from the reference, and the
  workflow state preserves every intermediate artefact (initial
  translation, raw correction response, parsed `<solution>` content,
  `solution_found` flag) for inspection / logging.

  Knobs (all constructor args, all settable from `config/workflows.py`):

  - `id`, `display_name` — registry id and menu label.
  - `override_llm_id` — if set, the correction step uses this factory
    LLM instead of `translator.llm`; default = self-correction.
  - `reasoning_words` — target length, in words, of the reasoning
    section the corrector is asked to produce (default `300`, matching
    the reference).

  Falls back to the initial translation and logs a warning if the
  corrector response is missing `<solution>...</solution>` tags.

### `registry.py`

The view-facing lookup layer:

- `list_translators()` — `[(id, display_name), ...]` mirroring
  `config.llms.LLMS`.
- `get_translator(id)` — returns a cached `BasicLLMTranslator` for the
  selected LLM.  Raises `KeyError` for unknown ids (the view catches
  this and renders the generic error notice).
- `list_workflows()` / `get_workflow(id)` — same for workflows declared
  in `config/workflows.py`.
- `default_translator_id()` / `default_workflow_id()` — the first
  configured entry of each list.

Duplicate or empty workflow ids raise at import time, surfacing
configuration mistakes early.

## How to add things

### A new LLM

1. Append an `LLMSpec` to `LLMS` in `config/llms.py` (id, display name,
   HF `repo_id`, inference provider; defaults for the rest are usually
   fine).
2. Done — the Model dropdown picks it up and the registry builds a
   `BasicLLMTranslator` for it on demand.

### A new multi-step workflow

1. Add a module under `translator/translation/workflows/` with:
   - the workflow's prompts as module-level strings (co-located with
     the nodes that use them),
   - a `TypedDict` describing the graph state,
   - one node function per step,
   - a class subclassing `Workflow` whose `run()` builds and invokes a
     LangGraph `StateGraph`.  Use `retry.invoke_chain(chain, inputs)`
     for every LLM call so the retry policy applies uniformly.
   - Accept `id` and `display_name` (and any per-instance knobs such as
     `override_llm_id`) as constructor arguments so the menu label
     lives in `config/workflows.py`.
2. Append one instance to `WORKFLOWS` in `config/workflows.py`,
   choosing its menu name.

The view, form, template, and CSS need no changes.
