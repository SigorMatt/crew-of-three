# crew-of-three

A "release notes" crew built with CrewAI: three agents run one after another
(a sequential process). A **Commit Collector** calls the `list_commits()` tool
and reports the commits merged since the last release; a **Release Notes
Writer** turns them into a Markdown draft; a **Release Notes Reviewer** runs
`lint_markdown(text)` on the draft, sends it back to the writer once through
CrewAI's own delegation tool (*Delegate work to coworker*) with the problems
to fix, lints the revision and approves it. Each agent is its own persona
(role, goal, backstory) with its own LLM instance. The run is instrumented by
two stock OpenInference instrumentors — one for CrewAI, one for the OpenAI
client CrewAI calls the model through — and exported over OTLP/HTTP by the
stock OpenTelemetry SDK.

Built under export contract 1.3 (`EXPORT-CONTRACT.md`) and brief Z6
(`BRIEF-Z6.md`).

## Run it

Needs Python 3.10–3.13 (CrewAI does not support 3.14 yet) and `make`. No
credentials, no network beyond PyPI for the first install.

```bash
make run                                       # same as make run-recorded
make run-recorded ENDPOINT=http://localhost:4318
make run-real MODEL=<model-id>                 # real model; see below
```

- `ENDPOINT` (default `http://localhost:4318`) is where telemetry goes; spans
  are posted to `$ENDPOINT/v1/traces`. With nothing listening, the SDK logs
  the export failure and the run still completes.
- The first `make` creates `.venv` with `python3 -m venv` (override with
  `PYTHON=python3.12`) and installs the full lock `requirements.lock` with
  `pip install --no-deps --require-hashes`, then `pip check`.
- Every run writes `MANIFEST.json` in the repository root before the first
  model call.

### Recorded mode (`make run-recorded`, the default)

`stub.py` is a tiny OpenAI-compatible server started inside the run on
`http://127.0.0.1:18765/v1`, model name `stub-release-model`, API key
`stub-key-not-a-secret`. It serves `/v1/chat/completions` (plain and
streamed) and picks each reply from the request alone, so every run is the
same eight model calls:

1. collector → `list_commits()` (eight canned commits)
2. collector → reports the commits
3. writer → first draft (fails lint)
4. reviewer → `lint_markdown(draft)`
5. reviewer → `Delegate work to coworker` → **Release Notes Writer** (the one send-back)
6. writer (delegated) → revised draft
7. reviewer → `lint_markdown(revision)` → `OK`
8. reviewer → `APPROVED` + final notes

Response ids, `created` timestamps and token counts are fixed per step.

### Real mode (`make run-real`) — run by the operator, not by the author

```bash
export OPENAI_API_KEY=...                # gateway key
export OPENAI_BASE_URL=https://gateway.example/v1
make run-real MODEL=vendor/model-name ENDPOINT=http://collector:4318
```

- `OPENAI_API_KEY` and `OPENAI_BASE_URL` are read from the environment (the
  same names CrewAI's native OpenAI provider documents); `MODEL` is taken from
  the make command line.
- The model id is passed to the gateway **unchanged**, including any `/`.
  CrewAI normally reads a `provider/` prefix out of a model string; here the
  LLM is built with an explicit `provider="openai"`, which makes CrewAI use
  its native OpenAI-SDK provider and send the id as given. LiteLLM is not
  installed and is never used.
- CrewAI's OpenAI provider is configured with `api="completions"`, so all
  calls go to `/v1/chat/completions` with tool calling (CrewAI also has a
  Responses-API mode; it is not used). Streaming is CrewAI's default (off).
- Model intended for the real run: **`gpt-4.1-mini`** (any id the gateway
  serves works; the operator chooses).

## Pinned versions

Framework and instrumentation (exact pins in `pyproject.toml`; the whole tree
is locked in `uv.lock` and `requirements.lock`):

| package | version |
|---|---|
| `crewai` | 1.15.27 |
| `openinference-instrumentation-crewai` | 1.1.21 |
| `openinference-instrumentation-openai` | 0.1.65 |
| `opentelemetry-sdk` | 1.45.1 |
| `opentelemetry-exporter-otlp-proto-http` | 1.45.1 |
| `openai` (the client CrewAI uses; from the lock) | 2.54.0 |
| `openinference-instrumentation` (from the lock) | 0.1.71 |

**Compatibility.** These are the newest releases of CrewAI and both
instrumentors at the time of writing, and they resolve and run together; no
incompatibility between framework and instrumentors was found. One cap worth
recording: `crewai` 1.15.27 requires `openai<3`, so the OpenAI client is the
newest 2.x (2.54.0), not the newest release (3.29.0). The lock also contains
`opentelemetry-exporter-otlp-proto-grpc`, pulled in transitively by CrewAI's
dependencies; it is installed but not used — export is OTLP/HTTP only.

## Telemetry configuration

- Stock `TracerProvider()` (resource from the SDK's own environment
  handling), one `BatchSpanProcessor` at its defaults, the stock
  `OTLPSpanExporter` from `opentelemetry-exporter-otlp-proto-http` at its
  defaults; `shutdown()` on exit, however the run ends.
- Environment set by the `Makefile`:
  - `OTEL_SERVICE_NAME=crew-of-three`
  - `OTEL_EXPORTER_OTLP_ENDPOINT=$(ENDPOINT)`
- `CrewAIInstrumentor().instrument(tracer_provider=...)` and
  `OpenAIInstrumentor().instrument(tracer_provider=...)`, both with their
  default configuration (the CrewAI instrumentor in its default wrapper mode).
- **Content capture.** OpenInference records message content on spans by
  default; the `Makefile` sets the documented switches explicitly anyway:
  - `OPENINFERENCE_HIDE_INPUTS=false`
  - `OPENINFERENCE_HIDE_OUTPUTS=false`
  - `OPENINFERENCE_HIDE_INPUT_MESSAGES=false`
  - `OPENINFERENCE_HIDE_OUTPUT_MESSAGES=false`
  - `OPENINFERENCE_HIDE_INPUT_TEXT=false`
  - `OPENINFERENCE_HIDE_OUTPUT_TEXT=false`

  `OPENINFERENCE_ENABLE_GENAI_SEMCONV` is left unset (default: off).
- **CrewAI's own telemetry is turned off**: CrewAI ships an anonymous
  telemetry exporter of its own (a separate tracer provider that posts to
  CrewAI's servers) and an opt-in hosted tracing feature. Neither is part of
  this agent's telemetry, and a stranger's run should not phone home, so the
  `Makefile` sets `CREWAI_DISABLE_TELEMETRY=true` and
  `CREWAI_TRACING_ENABLED=false`. Neither touches the global provider or the
  OTLP export above.

## Files

- `run.py` — entry point: telemetry setup, `MANIFEST.json`, one crew run, `shutdown()`
- `release_crew.py` — the agents, tasks and the two tools
- `stub.py` — the key-free scripted OpenAI-compatible server
- `requirements.lock` / `uv.lock` — the full dependency lock (`make lock` regenerates both; needs `uv`)
