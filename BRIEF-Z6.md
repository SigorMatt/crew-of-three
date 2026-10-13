# Pet project brief

This brief is given to its implementer together with `EXPORT-CONTRACT.md`
and nothing else. It says what the agent does and which packages instrument
it. It never says what the telemetry should look like. Pin exact versions of
every package named; the versions mentioned are "current at time of writing"
and are yours to confirm.

---

## Z6 — `crew-of-three`: multi-agent delegation under OpenInference / CrewAI

**Framework and instrumentation.** CrewAI with three agents and a sequential
process, instrumented by `openinference-instrumentation-crewai`, **and**
`openinference-instrumentation-openai` for the underlying client (two
instrumentors, as in Z3, but across a multi-agent framework).

**What it does.** A "release notes" crew: a *collector* agent calls
`list_commits()` (tool), a *writer* agent drafts notes, a *reviewer* agent
calls `lint_markdown(text)` (tool) and either approves or sends it back
once. Each agent is its own LLM persona; delegation between agents goes
through the framework.

**Scenario, fixed.** Eight canned commits; the reviewer sends the draft back
exactly once, then approves.

**Why this shape.** Agent-to-agent delegation as spans, tasks nested under
agents nested under a crew, and the same model client seen through two
instrumentors across process-internal handoffs.

---

## What every brief has in common

- `make run-recorded` is deterministic; `make run-real` is run once against
  a real model with the endpoint we give.
- The implementer does not know what consumes the traces and does not look.
- Where a brief asks for something the contract forbids (Z4's one manual
  span, Z5's missing shutdown), the brief wins, exactly as far as it says.
