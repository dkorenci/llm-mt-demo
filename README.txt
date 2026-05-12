Machine translation demo app implementing the translation workflow described in the paper:
IRB-MT at WMT25 Translation Task: A Simple Agentic System Using an Off-the-Shelf LLM
https://aclanthology.org/2025.wmt-1.51.pdf

The demo was created as a companion to the presentation about the approach.
The presentation is in the presentation/ folder.
It enables one to play with MT based on smaller LLMs and multi-LLM workflows.

LLM MT Demo
===========

A small Django web app for demonstrating machine translation with LLMs.
Translations run through Hugging Face inference endpoints (via
LangChain) and multi-step translation workflows are built as LangGraph
state machines.

Repository structure overview is in CONCEPT.md (each subdirectory has
its own CONCEPT.md with more detail).


1. Installation
---------------

Requirements: Python 3.12+ and pip.

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

A Hugging Face access token is required for inference. On the first
run, ./run.sh seeds a local settings.py from settings-template.py:

    HF_INFERENCE_ENDPOINT_TOKEN = ""

Paste your token between the quotes. The file is gitignored.
Several dollars of HF credits should allow processing of at least hundreds of texts.


2. Running
----------

    ./run.sh                                 # default: 127.0.0.1:8000
    ./run.sh --log                           # also write a timestamped
                                             #   log-YYYYMMDD-HHMMSS.log
                                             #   file next to run.sh
    ./run.sh --fetcher newspaper             # switch URL extractor
    ./run.sh --fetcher trafilatura --log     # flags can be combined
    HOST=0.0.0.0 PORT=9000 ./run.sh          # bind / port overrides
    ./run.sh --help                          # usage

The first invocation also creates db.sqlite3 for Django's own auth /
contenttypes tables; the app itself defines no DB models.


3. Using the app
----------------

Open http://127.0.0.1:8000/ in a browser. The single page contains:

  Row 1   Source language / target language selectors.
          Default is Croatian -> English. English and Croatian are
          pinned at the top of both lists; ~50 languages total.

  Row 2   Model selector / Workflow selector.
          The Model dropdown lists the LLMs declared in
          config/llms.py. The Workflow dropdown lists the workflows
          declared in config/workflows.py. NONE is the default
          (single-pass translation).

  Row 3   URL field + Load button. Fetches the page, extracts the
          main article text, and places it into the Source panel.
          Target is not touched.

  Row 4   [Translate]    Run the selected workflow + model.
          [Switch]       Swap source/target languages and texts
                         (client-side; no server round-trip).
          [Clone to Tab] Open a new browser tab pre-populated with
                         every current field. The two tabs are then
                         fully independent (the server is stateless;
                         per-tab state lives in the form DOM).

  Row 5   Source textarea | Target textarea (50/50 width). Long
          words / URLs reflow on resize without a horizontal scroll.

Error handling is intentionally silent: any failure (network,
extraction, translation, validation) renders the same generic notice
("An error occurred. Check the log.") and the actual reason is
recorded in the Python log. Use ./run.sh --log to capture the log to
a file.


4. Adding a new LLM
-------------------

Entries in config/llms.py belong to a discriminated union; pick the
spec type that matches how the LLM should be accessed:

  HFSpec       Native Hugging Face inference-endpoint protocol.
               Carries HF-native knobs (do_sample, top_k,
               repetition_penalty, model_kwargs). Greedy decoding =
               temperature=None + do_sample=False.

  OpenAISpec   OpenAI-compatible Chat Completions protocol. Use this
               to talk to HF's OpenAI-compatible router (set base_url
               = HF_OPENAI_BASE_URL and encode the HF provider in the
               model string as "<repo_id>:<provider>"), or any other
               OpenAI-compatible server. Greedy decoding =
               temperature=0.0. Non-standard knobs (top_k,
               repetition_penalty, ...) go in extra_body.

The factory dispatches on the spec's runtime type, so the rest of the
code stays the same.

Append the new entry to LLMS:

    LLMS: list[LLMSpec] = [
        OpenAISpec(
            id="gemma3-12b",
            display_name="Gemma 3 12B Instruct",
            model="google/gemma-3-12b-it:featherless-ai",
            base_url=HF_OPENAI_BASE_URL,
        ),
        # ...

        # An OpenAI-compatible-protocol entry:
        OpenAISpec(
            id="my-new-model",
            display_name="My New Model",
            model="<hf-org>/<hf-repo>:<hf-inference-provider>",
            base_url=HF_OPENAI_BASE_URL,
            # Optional knobs (defaults are greedy decoding):
            #   temperature=0.0, max_tokens=4096, top_p=None,
            #   extra_body={"top_k": 50, "repetition_penalty": 1.1},
        ),

        # ...or a native-HF-protocol entry:
        HFSpec(
            id="my-other-model",
            display_name="My Other Model",
            repo_id="<hf-org>/<hf-repo>",
            provider="<hf-inference-provider>",
            # Optional knobs (defaults are greedy decoding):
            #   temperature=None, max_new_tokens=4096,
            #   do_sample=False, top_p=None, top_k=None,
            #   repetition_penalty=None, model_kwargs={},
        ),
    ]

Restart the server. The new model shows up in the Model dropdown and
is selectable for every workflow. No other code changes are needed.


5. Adding a new multi-step workflow
-----------------------------------

A workflow is a function that builds a compiled LangGraph. The basic
translator is itself a one-node graph; multi-step workflows compose
with it by adding it as a subgraph node.

Use translator/translation/workflows/correction.py as a template.

Step 1. Create translator/translation/workflows/<name>.py with:

  (a) Prompt strings as module-level constants.

  (b) A TypedDict for the graph state. Include the fields the basic
      translator writes (request, instruction, translation) if you
      want to slot it in as a subgraph -- LangGraph auto-maps state
      keys with matching names between parent and child graphs.

          class MyState(TypedDict):
              request: TranslationRequest
              instruction: str
              translation: str        # basic translator writes this
              # ... fields the workflow itself writes ...

  (c) One node function per step, signature (state) -> dict. Every
      LLM call must go through invoke_chain so the retry policy
      (3 retries, exponential backoff) applies:

          from ..retry import invoke_chain

          def _my_node(state, llm):
              chain = ChatPromptTemplate.from_messages(
                  [("human", MY_PROMPT)]) | llm
              resp = invoke_chain(chain, {...})
              return {"my_field": resp.content}

  (d) A factory that builds the graph. Use add_node("translate",
      translator_graph) to absorb the basic translator as a subgraph:

          from langgraph.graph import END, StateGraph

          def create_my_workflow(
              translator_graph, translator_llm,
              *, override_llm_id=None, **knobs,
          ):
              aux_llm = (
                  create_llm(override_llm_id)
                  if override_llm_id else translator_llm
              )
              g = StateGraph(MyState)
              g.add_node("translate", translator_graph)
              g.add_node("step2", functools.partial(_my_node, llm=aux_llm))
              # ... add more nodes / edges as needed ...
              g.set_entry_point("translate")
              g.add_edge("translate", "step2")
              g.add_edge("step2", END)
              return g.compile()

  (e) Helpers that seed the initial state and extract the result:

          from ..basic import make_instruction

          def my_initial_state(request):
              return {
                  "request": request,
                  "instruction": make_instruction(request),
                  "translation": "",
                  # ... zero values for the rest of MyState ...
              }

          def my_extract_result(state):
              return TranslationResult(text=state["final_text"])

Step 2. Register the workflow in config/workflows.py:

    from translator.translation.workflows.<name> import (
        create_my_workflow, my_initial_state, my_extract_result,
    )

    def _my_factory(override_llm_id=None, **knobs):
        def factory(translator_graph, translator_llm):
            return create_my_workflow(
                translator_graph, translator_llm,
                override_llm_id=override_llm_id, **knobs,
            )
        return factory

    WORKFLOWS: list[WorkflowEntry] = [
        # ... existing entries ...
        WorkflowEntry(
            id="my-workflow",
            display_name="My Workflow",
            factory=_my_factory(),
            initial_state=my_initial_state,
            extract_result=my_extract_result,
        ),
        # To use a different LLM for the workflow's auxiliary calls:
        # WorkflowEntry(
        #     id="my-workflow-27b",
        #     display_name="My Workflow (aux: Gemma 27B)",
        #     factory=_my_factory(override_llm_id="gemma3-27b"),
        #     initial_state=my_initial_state,
        #     extract_result=my_extract_result,
        # ),
    ]

Restart the server. The new workflow shows up in the Workflow dropdown
and can be combined with any LLM listed in config/llms.py.


6. Adding a new single-translation prompt
-----------------------------------------

The basic translator ships one prompt. Replacement is a single-file
edit of TRANSLATION_PROMPT and make_instruction() in
translator/translation/basic.py.

If you want multiple prompt variants selectable from the UI you have
two reasonable options:

  (a) Extend config/llms.py into a richer translator catalogue with
      one entry per (LLM, prompt) pair. The Model dropdown lists
      e.g. "Gemma 12B (literal)" and "Gemma 12B (idiomatic)".

  (b) Add a separate create_<variant>_translator(llm) factory and a
      third dropdown for "Prompt style".

Both stay in the function-based pattern: a new factory plus a new
config row. See translator/translation/CONCEPT.md for the details.


7. Where to look
----------------

  CONCEPT.md                                  Top-level overview.
  config/CONCEPT.md                           LLM / workflow / language config.
  translator/CONCEPT.md                       The Django app.
  translator/translation/CONCEPT.md          The translation stack.
  translator/fetcher/CONCEPT.md              The URL fetcher subpackage.
