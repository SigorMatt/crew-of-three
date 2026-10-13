"""One complete run of the release-notes crew, exported over OTLP/HTTP.

    python run.py recorded   # against the local key-free stub
    python run.py real       # against OPENAI_BASE_URL / OPENAI_API_KEY with MODEL=<id>

Where telemetry goes is the stock SDK's business: OTEL_EXPORTER_OTLP_ENDPOINT
(set by the Makefile from ENDPOINT) and OTEL_SERVICE_NAME.
"""

from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timezone
from importlib.metadata import version

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from openinference.instrumentation.crewai import CrewAIInstrumentor
from openinference.instrumentation.openai import OpenAIInstrumentor

INSTRUMENTATION = ["openinference-instrumentation-crewai", "openinference-instrumentation-openai"]
EXPORTER = "opentelemetry-exporter-otlp-proto-http"


def write_manifest(*, mode: str, model: str, base_url: str, started_at: str) -> None:
    manifest = {
        "contract_version": "1.3",
        "framework": "crewai",
        "framework_version": version("crewai"),
        "instrumentation": [f"{p}=={version(p)}" for p in INSTRUMENTATION],
        "sdk": {
            "opentelemetry-sdk": version("opentelemetry-sdk"),
            "exporter": f"{EXPORTER}=={version(EXPORTER)}",
        },
        "python": platform.python_version(),
        "platform": platform.platform(),
        "model": model,
        "base_url": base_url,
        "mode": mode,
        "endpoint": os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"),
        "started_at": started_at,
    }
    with open("MANIFEST.json", "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


def main(mode: str) -> None:
    started_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    if mode == "recorded":
        import stub

        stub.start(os.environ.get("STUB_LOG") or None)
        model, base_url, api_key = stub.MODEL, stub.base_url(), "stub-key-not-a-secret"
    elif mode == "real":
        model = os.environ.get("MODEL", "")
        base_url = os.environ.get("OPENAI_BASE_URL", "")
        api_key = os.environ.get("OPENAI_API_KEY", "")
        missing = [n for n, v in (("MODEL", model), ("OPENAI_BASE_URL", base_url), ("OPENAI_API_KEY", api_key)) if not v]
        if missing:
            sys.exit(f"run-real needs {', '.join(missing)} (MODEL on the make command line, the others in the environment)")
    else:
        sys.exit(f"unknown mode {mode!r}: expected 'recorded' or 'real'")

    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    CrewAIInstrumentor().instrument(tracer_provider=provider)
    OpenAIInstrumentor().instrument(tracer_provider=provider)

    write_manifest(mode=mode, model=model, base_url=base_url, started_at=started_at)

    from release_crew import build_crew

    try:
        result = build_crew(model=model, base_url=base_url, api_key=api_key).kickoff()
        print("\n=== crew result ===\n" + str(result))
    finally:
        provider.shutdown()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "recorded")
