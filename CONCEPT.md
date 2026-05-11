# LLM MT Demo — top-level concept

A small Django web app for demonstrating machine translation with LLMs.
Phase 1 (this branch's state) delivers the complete web interface with
mocked translator/workflow plumbing.  Phase 2 will plug in LangChain +
Hugging Face inference endpoints behind the abstractions described
below; the UI does not need to change.

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
| `config/` | Application configuration: language catalogue, model & workflow registries. |
| `translator/` | The single Django app — view, form, fetcher subpackage, translation abstractions, templates, static assets. |
| `db.sqlite3` | Auto-created by `migrate` for Django's own tables; the app defines no models in Phase 1. |
| `log-YYYYMMDD-HHMMSS.log` | Produced only when `./run.sh --log` is used; gitignored. |

See each subdirectory's `CONCEPT.md` for details.

## Design highlights

- **Statelessness for independent tabs.**  All per-tab state (language
  choices, model, workflow, URL, source text, target text) lives in the
  page's `<form>`.  No Django session is used.  Cloning a tab via the
  *Clone to Tab* button issues a `POST` with `formtarget="_blank"`, so
  the browser opens a new tab whose form is pre-populated identically;
  from that point on, the two tabs cannot influence one another.

- **Generic translator abstraction.**  The view depends only on
  `Translator` and `Workflow` ABCs in
  `translator/translation/base.py`.  Concrete implementations are
  declared in `config/models.py` and `config/workflows.py`; adding a
  Phase-2 backend is one new class plus one line of configuration.

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
