# Export contract — for every telemetry pet project

Contract version **1.3** (1.0 was given to Z4, 1.2 to Z3 and Z5; the
changes are listed at the end). Put the version you were given in
`MANIFEST.json`.

You are building a small, ordinary AI agent. Its only job beyond working is
to be **instrumented by stock instrumentation and to export its telemetry
over OTLP**. You do not know, and must not guess, what consumes the
telemetry. Build the agent the way anyone would build one; let the
instrumentor decide what a span looks like.

## 1. What you deliver

A repository with:

- the agent, runnable with `make run` (and `make run ENDPOINT=http://host:port`
  to override where telemetry goes; default `http://localhost:4318`);
- `make run-recorded`: the same run against a **key-free** OpenAI-compatible
  stub you provide (a tiny local server returning scripted completions and
  tool calls is fine), so a stranger can run it with no credentials;
- `make run-real`: the same run against a real model. **You do not run it**;
  the operator on our side runs it once, against the endpoint and gateway we
  name, and keeps the telemetry. Its only requirements on you are §4's
  variables and that the README says how to invoke it;
- `README.md` with: the framework and instrumentation packages **pinned to
  exact versions**, the model used for the real run, and a one-paragraph
  description of what the agent does;
- a `MANIFEST.json` written by `make run` next to nothing else:
  `{"contract_version": "1.3", "framework": "...", "framework_version": "...",
  "instrumentation": ["pkg==ver", ...], "sdk": {"opentelemetry-sdk": "...",
  "exporter": "pkg==ver"}, "python": "3.x.y", "platform": "...",
  "model": "...", "base_url": "...", "mode": "recorded" | "real",
  "endpoint": "...", "started_at": "<ISO-8601, UTC, with Z>"}`. When there
  is no agent framework (a bare client), `framework` is the client library
  and `framework_version` its version. `base_url` is the API base the model
  client actually used — the stub's URL under `recorded`, the gateway's under
  `real` — because a model name alone does not say who served it.
  `started_at` is taken from the clock when the run starts, before the first
  model call, and `MANIFEST.json` is **written before the first model call**
  too, so it exists however the run ends.
- `make run` with no arguments is the recorded mode, so the default works
  with no credentials. A full lock of the dependency tree installed with
  `--no-deps` is the recommended way to keep the pins exact.

## 2. Instrumentation rules

- Use the **stock instrumentation package** your brief names (an OpenInference
  instrumentor, or the OpenTelemetry GenAI instrumentation). Do not write
  spans by hand, do not add attributes, do not rename anything, do not
  filter. If the instrumentor emits something odd, that is the point.
- Pin the **newest versions of the framework and the instrumentor that work
  together**. If the newest of one is incompatible with the other, pin the
  newest compatible pair and say in `README.md` what broke — that
  incompatibility is itself something we want recorded, not worked around
  silently.
- If the instrumentation offers a **content-capture** setting, turn it on in
  the mode that puts message content **on spans** (some packages' legacy
  mode puts it on log records, which never leave the process here), using
  only the environment variables the instrumentation documents. Record the
  exact variables and values in `README.md`.
- Use the **stock OpenTelemetry SDK** with a `BatchSpanProcessor` at its
  defaults and the stock OTLP/HTTP exporter at its defaults. Do not switch
  to a simple processor to make export tidy; do not set a custom encoding
  unless your brief says so.
- Export to `$ENDPOINT/v1/traces` (the SDK's default path). Nothing else is
  required of the endpoint; whatever the exporter sends by default is
  correct.
- Do **not** install, import, read, or mention any trace-consuming library.
  If you find yourself wondering what the receiver wants, stop: it wants
  whatever your exporter sends.

## 3. The run

- `make run` performs **one complete agent run** of the scenario in your
  brief, then exits — flushing the tracer provider on exit the way the SDK
  documents (`shutdown()`), and no other way.
- The run must be **deterministic under `make run-recorded`**: same prompts,
  same tool results, same number of steps on every run — and the same
  values in what the SDK records on its own: a fixed stub port, a fixed
  service name (`OTEL_SERVICE_NAME`, stock SDK resource configuration), a
  fixed stub model name. Randomness in the real run is fine.
- Do not catch and hide errors the scenario is meant to produce; let them
  reach the instrumentor.
- If the real model or gateway breaks the scenario before it completes (a
  crash, a malformed stream, a refused tool call), **that run is not the
  capture**: do not code around the gateway's behaviour, report it under §6,
  and we choose another model. The agent's handling of the model's output
  stays the plain, documented way the client library expects it.
- A manual span your brief asks for carries exactly the attributes the
  brief lists — none, when it lists none. Do not add attributes to make it
  look like the instrumentor's spans.

## 4. What you must not do

- No knowledge of the consumer. No "making the spans nicer". No sampling.
- No custom exporter, no custom span processor, no manual `start_span` around
  framework calls the instrumentor already covers (manual spans are allowed
  only where your brief asks for them, and then only with the SDK's own API).
- No secrets in the repository. `make run-real` reads `OPENAI_API_KEY` and
  `OPENAI_BASE_URL` from the environment — or your framework's documented
  equivalents, named in `README.md` — and takes the model as `MODEL=<id>` on
  the make command line, so one credential set and one gateway drive every
  pet project. The real run is made against an OpenAI-compatible gateway we
  name, not necessarily OpenAI; nothing in the agent may assume which. **What
  the gateway serves** is `/v1/chat/completions` with tool calling and
  streaming, and nothing else is assumed: a framework whose default is
  another API (the Responses API, say) is configured to use chat
  completions, and the README says so. A model id is an opaque string the
  gateway serves and may contain `/` (`vendor/model-name`); the agent passes
  it to the gateway unchanged and never reads a provider out of it.

## 5. Definition of done

A stranger with Python and no credentials can clone the repository, run
`make run-recorded ENDPOINT=http://localhost:4318` against any OTLP endpoint
(or none — the SDK logs export failures and the run still completes), and
read `MANIFEST.json` afterwards. A reviewer will do exactly that on a
machine that has never seen the repository. `make run-real` is documented
and untested by you. You could not say what the consumer of the telemetry
is, and you have not tried to find out.

## 6. Report back

When you are done, report in ten lines: the repository URL, the packages and
versions pinned, the model intended for the real run, and **every point
where this contract or your brief left you guessing** — what you guessed and
why. Those guesses are how the contract improves.

---

Changes from 1.2 (after Z3's and Z5's reports): the real run is the
operator's, not the implementer's (§1, §5 — both implementers found the
old §5 contradicted their instructions); the gateway's API surface is stated
(§4: chat completions with tools and streaming; a framework defaulting to
another API is configured away from it); `MANIFEST.json` is written before
the first model call (§1); a model id may contain `/` and is passed through
unchanged (§4 — Z3's framework read `vendor/` as a provider). Not changed,
on purpose: the processor and
exporter defaults — Z5 showed that a run shorter than the batch schedule
delay that exits abruptly exports nothing, and the brief, not the SDK
settings, is what decides how long a run lasts.

Changes from 1.1 (after Z4's captures): manifest gains `base_url`, and
`started_at` is UTC with `Z`, taken before the first model call; `make
run-real` reads `OPENAI_API_KEY`/`OPENAI_BASE_URL` (or the framework's named
equivalents) and `MODEL=` — the real run goes to an OpenAI-compatible gateway
we name; a real run the gateway breaks is not the capture and is reported,
never coded around (Z4's first real run crashed on a gateway that split one
streamed tool call across two indices; the capture was taken with another
model); a manual span carries only what the brief lists.

Changes from 1.0 (after the Z4 pilot's ten recorded assumptions): newest
compatible pair with the incompatibility recorded; content capture on spans
with the variables recorded; determinism covers SDK-recorded values;
`make run` defaults to recorded; manifest gains `contract_version`,
`python`, `platform`, `mode`, and defines `framework` for a bare client;
the stranger run is stated as a review step; §6 added.
