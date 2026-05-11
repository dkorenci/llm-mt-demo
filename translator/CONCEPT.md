# `translator/` — Django app for the demo UI

The single Django app that owns every page, form, and asset of the
demo.  It is deliberately compact: one view, one form, one HTML
template, one stylesheet, one tiny JS file, plus the translation
abstractions under `translation/`.

## Files

| Path | Role |
|---|---|
| `apps.py` | `AppConfig` registration. |
| `urls.py` | Routes `""` to `views.index`. |
| `forms.py` | `TranslateForm`; carries the entire per-tab state. |
| `views.py` | `index()` view; action-dispatched on a hidden form field. |
| `fetcher/` | Swappable URL fetcher + extractor (default backend: trafilatura). See `fetcher/CONCEPT.md`. |
| `translation/` | Abstract `Translator` / `Workflow` interfaces, registry, stubs. |
| `templates/translator/base.html` | Page chrome and asset includes. |
| `templates/translator/index.html` | The form-driven single page. |
| `static/translator/css/style.css` | 50/50 soft-wrap layout, button styles. |
| `static/translator/js/app.js` | Client-side Switch handler. |

## Statelessness contract

The view never reads or writes a session.  Every POST contains the
complete current state of the page, and every response renders that
state back into the form's fields.  This is what makes "Clone to Tab"
yield genuinely independent tabs.

## Action dispatch

`TranslateForm` has a hidden `action` field.  Each submit button on the
page sets it (via `name="action" value="..."`).  The view branches:

| Action | Side-effect | Field written back |
|---|---|---|
| `translate` | Run the selected workflow + translator on `source_text`. | `target_text` |
| `fetch` | Run `fetcher.fetch_and_extract(url)`. | `source_text` |
| `clone` | None (just re-render the form). | — |
| (none/GET) | Empty form with defaults. | — |

The Switch button has no server round-trip — it swaps values in the
DOM via `static/translator/js/app.js`.

## Clone-to-Tab mechanics

The Clone button is a regular submit, but with `formtarget="_blank"`.
The browser submits the entire current form to `/`, the server
re-renders the same page with all values pre-populated, and the result
opens in a fresh tab.  The original tab's DOM is untouched.

## Where Phase 2 plugs in

Phase 2 changes nothing in this app's UI layer.  It only adds:

1. New concrete `Translator` subclasses (likely under
   `translator/translation/` in their own modules).
2. Entries in `config/models.py` (and optionally `config/workflows.py`).
3. New requirements in `requirements.txt` (LangChain etc.).

See `translation/CONCEPT.md` for the interface details.
