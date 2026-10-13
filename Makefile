# crew-of-three: one run of a three-agent CrewAI crew, exported over OTLP/HTTP.
#
#   make run                                  # = run-recorded, key-free local stub
#   make run-recorded ENDPOINT=http://host:4318
#   make run-real MODEL=<model-id>            # needs OPENAI_API_KEY, OPENAI_BASE_URL

ENDPOINT ?= http://localhost:4318
PYTHON   ?= python3
VENV     := .venv
PY       := $(VENV)/bin/python

# Stock OpenTelemetry SDK configuration: fixed service name, endpoint from ENDPOINT
# (the exporter appends its default /v1/traces).
export OTEL_SERVICE_NAME := crew-of-three
export OTEL_EXPORTER_OTLP_ENDPOINT = $(ENDPOINT)

# OpenInference content capture on spans (these are also the defaults; stated, not assumed).
export OPENINFERENCE_HIDE_INPUTS := false
export OPENINFERENCE_HIDE_OUTPUTS := false
export OPENINFERENCE_HIDE_INPUT_MESSAGES := false
export OPENINFERENCE_HIDE_OUTPUT_MESSAGES := false
export OPENINFERENCE_HIDE_INPUT_TEXT := false
export OPENINFERENCE_HIDE_OUTPUT_TEXT := false

# CrewAI's own phone-home telemetry and its hosted tracing are separate from ours; off.
export CREWAI_DISABLE_TELEMETRY := true
export CREWAI_TRACING_ENABLED := false

.PHONY: run run-recorded run-real install lock clean

run: run-recorded

run-recorded: $(VENV)/.installed
	$(PY) run.py recorded

run-real: $(VENV)/.installed
	MODEL='$(MODEL)' $(PY) run.py real

install: $(VENV)/.installed

$(VENV)/.installed: requirements.lock
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet --no-deps --require-hashes -r requirements.lock
	$(PY) -m pip check
	touch $@

# Maintainer only: re-resolve pyproject.toml and rewrite the full lock (needs uv).
lock:
	uv lock
	uv export --frozen --no-emit-project --no-dev --format requirements-txt -o requirements.lock

clean:
	rm -rf $(VENV) MANIFEST.json
