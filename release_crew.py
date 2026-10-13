"""The release-notes crew: three agents, three tasks, one sequential process."""

from __future__ import annotations

import json
import re

from crewai import LLM, Agent, Crew, Process, Task
from crewai.tools import tool

COLLECTOR = "Commit Collector"
WRITER = "Release Notes Writer"
REVIEWER = "Release Notes Reviewer"

# The eight commits the collector's tool always returns.
COMMITS = [
    {"sha": "a1c3e5f", "author": "dana", "message": "feat: add --since flag to export command"},
    {"sha": "b2d4f6a", "author": "lee", "message": "fix: handle empty config file without crashing"},
    {"sha": "c3e5a7b", "author": "dana", "message": "feat: support YAML output format"},
    {"sha": "d4f6b8c", "author": "sam", "message": "docs: document the plugin API"},
    {"sha": "e5a7c9d", "author": "lee", "message": "fix: correct timezone in log timestamps"},
    {"sha": "f6b8d0e", "author": "kim", "message": "perf: cache parsed templates between runs"},
    {"sha": "a7c9e1f", "author": "sam", "message": "chore: bump minimum Python to 3.10"},
    {"sha": "b8d0f2a", "author": "kim", "message": "fix: retry uploads on HTTP 503"},
]


@tool("list_commits")
def list_commits() -> str:
    """List the commits merged since the last release, as a JSON array."""
    return json.dumps(COMMITS)


@tool("lint_markdown")
def lint_markdown(text: str) -> str:
    """Lint a Markdown document and return the problems found, or 'OK' when there are none."""
    problems = []
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# "):
        problems.append("line 1: document must start with a level-1 heading ('# ')")
    for n, line in enumerate(lines, 1):
        if line != line.rstrip():
            problems.append(f"line {n}: trailing whitespace")
        if re.match(r"^\s*[*+] ", line):
            problems.append(f"line {n}: use '-' for list items")
        if len(line) > 100:
            problems.append(f"line {n}: longer than 100 characters")
    if not any(line.startswith("## ") for line in lines):
        problems.append("document has no '## ' sections")
    return "OK" if not problems else "\n".join(problems)


def build_crew(model: str, base_url: str, api_key: str) -> Crew:
    def llm() -> LLM:
        # provider="openai" sends the model id to the server exactly as given
        # (no provider prefix is read out of it); api="completions" keeps the
        # client on /v1/chat/completions.
        return LLM(
            model=model,
            provider="openai",
            api="completions",
            base_url=base_url,
            api_key=api_key,
        )

    collector = Agent(
        role=COLLECTOR,
        goal="Gather every commit merged since the last release, exactly as recorded.",
        backstory="You are a meticulous release engineer who never paraphrases a commit.",
        tools=[list_commits],
        llm=llm(),
        allow_delegation=False,
    )
    writer = Agent(
        role=WRITER,
        goal="Turn a list of commits into clear, well-structured Markdown release notes.",
        backstory="You are a technical writer who groups changes by kind and writes for users.",
        llm=llm(),
        allow_delegation=False,
    )
    reviewer = Agent(
        role=REVIEWER,
        goal="Make sure the release notes are complete and lint-clean before they ship.",
        backstory="You are a strict editor. You lint every draft and send it back once if it needs work.",
        tools=[lint_markdown],
        llm=llm(),
        allow_delegation=True,
    )

    collect = Task(
        description="Call list_commits and report every commit it returns (sha, author, message).",
        expected_output="The full list of commits since the last release.",
        agent=collector,
    )
    write = Task(
        description="Draft Markdown release notes for version 2.4.0 from the collected commits.",
        expected_output="A Markdown release-notes draft covering every commit.",
        agent=writer,
        context=[collect],
    )
    review = Task(
        description=(
            "Review the draft release notes. Run lint_markdown on the draft. "
            f"Send the draft back to the {WRITER} exactly once, through the delegation tool, "
            "with the lint problems and any missing commits to fix. Then run lint_markdown on "
            "the revised notes and approve them."
        ),
        expected_output="The word APPROVED on the first line, followed by the final release notes.",
        agent=reviewer,
        context=[write],
    )

    return Crew(
        name="release-notes",
        agents=[collector, writer, reviewer],
        tasks=[collect, write, review],
        process=Process.sequential,
        verbose=True,
    )
