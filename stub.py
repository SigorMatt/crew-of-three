"""A key-free, OpenAI-compatible stub for `make run-recorded`.

Serves POST /v1/chat/completions (plain and streamed) with scripted replies.
The script is chosen from the request alone -- which agent's system prompt it
carries and which tool calls are already in the conversation -- so every run
gets the same replies, ids, timestamps and token counts.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 18765
MODEL = "stub-release-model"
CREATED = 1767225600  # 2026-01-01T00:00:00Z, fixed so responses never vary

REVISE_TASK = "Revise the 2.4.0 release notes draft so it passes lint_markdown"

DRAFT_V1 = """Release notes 2.4.0

New features
* Add --since flag to the export command (a1c3e5f)
* Support YAML output format (c3e5a7b)

Fixes
* Handle an empty config file without crashing (b2d4f6a)
* Correct the timezone in log timestamps (e5a7c9d)
* Retry uploads on HTTP 503 (b8d0f2a)

Other
* Cache parsed templates between runs (f6b8d0e)
* Document the plugin API (d4f6b8c)
* Minimum Python is now 3.10 (a7c9e1f)"""

DRAFT_V2 = """# Release notes 2.4.0

## New features

- Add `--since` flag to the export command (a1c3e5f)
- Support YAML output format (c3e5a7b)

## Fixes

- Handle an empty config file without crashing (b2d4f6a)
- Correct the timezone in log timestamps (e5a7c9d)
- Retry uploads on HTTP 503 (b8d0f2a)

## Performance

- Cache parsed templates between runs (f6b8d0e)

## Documentation and maintenance

- Document the plugin API (d4f6b8c)
- Minimum Python is now 3.10 (a7c9e1f)"""


def _system(messages: list[dict]) -> str:
    return "\n".join(
        m.get("content") or "" for m in messages if m.get("role") == "system" and isinstance(m.get("content"), str)
    )


def _text(messages: list[dict]) -> str:
    parts = []
    for m in messages:
        c = m.get("content")
        if isinstance(c, str):
            parts.append(c)
        elif isinstance(c, list):
            parts.extend(p.get("text", "") for p in c if isinstance(p, dict))
    return "\n".join(parts)


def _calls_made(messages: list[dict]) -> list[str]:
    return [
        tc["function"]["name"]
        for m in messages
        if m.get("role") == "assistant"
        for tc in (m.get("tool_calls") or [])
    ]


def _tool_results(messages: list[dict]) -> list[str]:
    return [m.get("content") or "" for m in messages if m.get("role") == "tool"]


def script(messages: list[dict]) -> tuple[str, dict]:
    """Return (step name, assistant message) for one request."""
    system = _system(messages)
    calls = _calls_made(messages)

    if "Commit Collector" in system:
        if "list_commits" not in calls:
            return "collector.call", _tool_call("list_commits", {}, len(calls) + 1)
        commits = json.loads(_tool_results(messages)[-1])
        lines = [f"- {c['sha']} ({c['author']}): {c['message']}" for c in commits]
        return "collector.answer", _answer(f"{len(commits)} commits since the last release:\n" + "\n".join(lines))

    if "Release Notes Writer" in system:
        if REVISE_TASK in _text(messages):
            return "writer.revise", _answer(DRAFT_V2)
        return "writer.draft", _answer(DRAFT_V1)

    if "Release Notes Reviewer" in system:
        delegated = "delegate_work_to_coworker" in calls
        lints = calls.count("lint_markdown")
        if lints == 0:
            return "reviewer.lint1", _tool_call("lint_markdown", {"text": DRAFT_V1}, len(calls) + 1)
        if not delegated:
            return "reviewer.send_back", _tool_call(
                "delegate_work_to_coworker",
                {
                    "task": REVISE_TASK,
                    "context": "Lint problems:\n" + _tool_results(messages)[-1] + "\n\nDraft:\n" + DRAFT_V1,
                    "coworker": "Release Notes Writer",
                },
                len(calls) + 1,
            )
        if lints == 1:
            return "reviewer.lint2", _tool_call("lint_markdown", {"text": DRAFT_V2}, len(calls) + 1)
        return "reviewer.approve", _answer("APPROVED\n\n" + DRAFT_V2)

    raise ValueError("stub: request matches no scripted agent")


def _tool_call(name: str, args: dict, n: int) -> dict:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": f"call_{n}_{name}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}
        ],
    }


def _answer(text: str) -> dict:
    return {"role": "assistant", "content": text}


def _usage(messages: list[dict], reply: dict) -> dict:
    # Deterministic stand-in for token counts: roughly four characters a token.
    prompt = len(json.dumps(messages, sort_keys=True)) // 4
    completion = len(json.dumps(reply, sort_keys=True)) // 4
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    log_requests = False

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        if self.log_requests:
            super().log_message(format, *args)

    def _send_json(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") not in ("/v1/chat/completions", "/chat/completions"):
            self._send_json(404, {"error": {"message": f"stub serves only /v1/chat/completions, not {self.path}"}})
            return
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        messages = body.get("messages", [])
        step, reply = script(messages)
        if "tool_calls" in reply and not body.get("tools"):
            raise ValueError(f"stub: step {step} needs tools but the request offered none")
        if self.server.log_file:  # type: ignore[attr-defined]
            with open(self.server.log_file, "a") as f:  # type: ignore[attr-defined]
                f.write(json.dumps({"step": step, "request": body}) + "\n")
        resp_id = f"chatcmpl-stub-{step}"
        finish = "tool_calls" if "tool_calls" in reply else "stop"
        usage = _usage(messages, reply)
        if body.get("stream"):
            self._stream(resp_id, reply, finish, usage, body)
        else:
            self._send_json(
                200,
                {
                    "id": resp_id,
                    "object": "chat.completion",
                    "created": CREATED,
                    "model": MODEL,
                    "choices": [{"index": 0, "message": reply, "finish_reason": finish}],
                    "usage": usage,
                },
            )

    def _stream(self, resp_id: str, reply: dict, finish: str, usage: dict, body: dict) -> None:
        def chunk(delta: dict, finish_reason: str | None = None, **extra: object) -> bytes:
            c = {
                "id": resp_id,
                "object": "chat.completion.chunk",
                "created": CREATED,
                "model": MODEL,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
                **extra,
            }
            return f"data: {json.dumps(c)}\n\n".encode()

        out = [chunk({"role": "assistant", "content": ""})]
        if "tool_calls" in reply:
            tc = reply["tool_calls"][0]
            out.append(chunk({"tool_calls": [{"index": 0, **tc}]}))
        else:
            out.append(chunk({"content": reply["content"]}))
        out.append(chunk({}, finish))
        if (body.get("stream_options") or {}).get("include_usage"):
            u = {"id": resp_id, "object": "chat.completion.chunk", "created": CREATED, "model": MODEL,
                 "choices": [], "usage": usage}
            out.append(f"data: {json.dumps(u)}\n\n".encode())
        out.append(b"data: [DONE]\n\n")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(sum(len(b) for b in out)))
        self.end_headers()
        for b in out:
            self.wfile.write(b)


def start(log_file: str | None = None) -> ThreadingHTTPServer:
    """Start the stub on its fixed port in a daemon thread and return the server."""
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.log_file = log_file  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, name="stub", daemon=True).start()
    return server


def base_url() -> str:
    return f"http://{HOST}:{PORT}/v1"


if __name__ == "__main__":
    Handler.log_requests = True
    srv = start(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"stub listening on {base_url()}", flush=True)
    threading.Event().wait()
