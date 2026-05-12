# LLM MT Demo — top-level concept

A small Django web app for demonstrating machine translation with LLMs.
The web interface is wired to Hugging Face inference endpoints through
LangChain, with multi-step workflows implemented as LangGraph state
machines.  Adding a new LLM is one entry in `config/llms.py`; adding a
new multi-step workflow is one module under
`translator/translation/workflows/` plus one entry in
`config/workflows.py`.

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

./run.sh                                 # default: 127.0.0.1:8000
./run.sh --log                           # also write log-YYYYMMDD-HHMMSS.log
./run.sh --fetcher newspaper             # switch URL extractor backend
./run.sh --fetcher trafilatura --log     # flags can be combined
HOST=0.0.0.0 PORT=9000 ./run.sh          # bind/port overrides
./run.sh --help                          # usage
```

The first run copies `settings-template.py` → `settings.py` if needed.
`settings.py` is the secrets file (e.g. `HF_INFERENCE_ENDPOINT_TOKEN`)
and is gitignored; `settings-template.py` is the committed template.

## Repository map

| Path | Role |
|---|---|
| `manage.py` | Django CLI entrypoint. |
| `run.sh` | Convenience launcher (template-copy, venv activation, optional logging, optional fetcher selection, migrate, runserver). |
| `requirements.txt` | Phase-1 Python dependencies. |
| `.gitignore` | Excludes the secrets file, the SQLite DB, the `log-*.log` files, virtualenvs, IDE/OS detritus. |
| `settings.py` / `settings-template.py` | Repo-root secrets module + its template. |
| `mtdemo/` | Django project package: settings, root URLconf, WSGI/ASGI entrypoints. |
| `config/` | Application configuration: language catalogue, LLM catalogue, workflow registry. |
| `translator/` | The single Django app — view, form, fetcher subpackage, translation/LLM/workflow stack, templates, static assets. |
| `db.sqlite3` | Auto-created by `migrate` for Django's own tables; the app defines no models of its own. |
| `log-YYYYMMDD-HHMMSS.log` | Produced only when `./run.sh --log` is used; gitignored. |

See each subdirectory's `CONCEPT.md` for details.

## Design highlights

- **Statelessness for independent tabs.**  All per-tab state (language
  choices, model, workflow, URL, source text, target text) lives in the
  page's `<form>`.  No Django session is used.  Cloning a tab via the
  *Clone to Tab* button issues a `POST` with `formtarget="_blank"`, so
  the browser opens a new tab whose form is pre-populated identically;
  from that point on, the two tabs cannot influence one another.

- **Everything is a LangGraph.**
  - **LLM definitions** — `config/llms.py` lists spec records from a
    discriminated union: `HFSpec` (native HF inference protocol) and
    `OpenAISpec` (OpenAI-compatible Chat Completions, e.g. HF's
    OpenAI-compatible router).  `translator/translation/llm_factory.py`
    dispatches on the spec type to build the matching cached LangChain
    wrapper (`ChatHuggingFace` or `ChatOpenAI`).
  - **Basic translator** — `translator/translation/basic.py` exposes
    `create_basic_translator(llm)` returning a one-node compiled
    graph.  `make_instruction(request)` is the single source of truth
    for the translation instruction string and is reused by workflows.
  - **Workflows** — `translator/translation/workflows/` contains one
    module per workflow, each providing a
    `create_<workflow>(translator_graph, translator_llm, **knobs)`
    factory.  `correction.py` slots the basic translator's graph in as
    a subgraph node (`graph.add_node("translate", translator_graph)`),
    so multi-step workflows compose with the basic translator at the
    graph level rather than via method calls.

- **Configurable workflow registry.**  `config/workflows.py` declares
  `WorkflowEntry` records (id, display name, factory, seed-state and
  result-extraction callables).  Per-instance knobs (override LLM,
  reasoning length, …) are captured in closures around the factory.
  By default the corrector reuses the basic translator's LLM (true
  self-correction); set `override_llm_id` on a registration to point
  it at a different factory LLM.

- **Retries on every LLM call.**  All chain invocations go through
  `translator.translation.retry.invoke_chain`, which retries 3× with
  exponential backoff (1 s → 2 s → 4 s) on transient cloud failures
  before surfacing the exception to the view.

- **Swappable URL fetcher.**  `translator/fetcher/` is a subpackage
  with two interchangeable backends behind a `Fetcher` ABC:
  `trafilatura` (default — actively maintained, broader recall) and
  `newspaper` (stricter, often cleaner). Selection is via
  `./run.sh --fetcher <name>` (which exports `MT_FETCHER`). Both
  share the same realistic-browser HTTP layer in `fetcher/http.py`.

- **Soft-wrapping 50/50 text panels.**  The two textareas use
  `flex: 1 1 0; min-width: 0` and `overflow-wrap: anywhere`, so any
  text reflows on resize without ever producing a horizontal
  scrollbar.

- **Silent UI on errors.**  The page never displays specific error
  text.  Any failure (network, extraction, translation, validation)
  renders the same generic notice: *"An error occurred. Check the
  log."*  Actual failure reasons go to the Python log via
  `logger.warning` / `logger.exception`, which lands in
  `log-YYYYMMDD-HHMMSS.log` when the server is started with `--log`.

## UI layout (top to bottom)

1. Source language / target language selectors
2. Model selector / Workflow selector (default `NONE`)
3. URL input + **Load** button (fetch + extract page body)
4. **Translate** (muted-red frame), **Switch** (client-side swap),
   **Clone to Tab**
5. Source textarea | Target textarea — fills remaining height, 50/50
