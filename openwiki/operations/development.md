---
type: operations guide
title: Development, CI, release, and wiki automation
description: Runtime and extra dependencies, local quality commands, enforced package boundaries, release controls, and automated OpenWiki update operations.
tags: [operations, ci, release, development]
---

# Development, CI, release, and wiki automation

## Runtime and installation

`endoxa` is pre-alpha version `0.0.1`, built by `uv_build` and requiring Python `>=3.14`. Core runtime dependency is `lark>=1.3.1`. Install optional integrations deliberately:

```bash
pip install "endoxa[trace]"     # pydantic-backed Proposition
pip install "endoxa[coverage]"  # networkx graph metrics
```

For full repository work, sync all extras and development tooling:

```bash
uv sync --all-extras --dev
```

Development dependencies include pytest/pytest-asyncio, Hypothesis, Ruff, import-linter, and `z3-solver` for solver differential tests. Pytest discovers under `tests`, uses strict markers/configuration, and adds repository root to `pythonpath` for the differential harness.

## Dependency architecture check

The import-linter contract in `pyproject.toml` enforces the package DAG described in [architecture](../architecture/overview.md): `instruments`, `trace`, `governance`, `solver`, `syntax`. A new top-level `endoxa` package must be added to the layer list; `tests/test_package_boundary.py` checks declared and actual package sets both ways. The special design constraint is that no package imports `instruments`, preserving independent measurement.

Run the standard local gate:

```bash
uv run ruff check .
uv run ruff format --check .
uv run lint-imports
uv run pytest
```

Use the focused commands on individual wiki pages first; use the full suite for cross-layer changes.

## CI and publishing

`.github/workflows/ci.yml` runs on pushes to `main` and pull requests. It uses Ubuntu, installs uv, synchronizes all extras/dev dependencies, then runs Ruff lint, format check, import contracts, and pytest.

`.github/workflows/release.yml` runs only for tags matching `v*`. It repeats the CI checks, runs `uv build`, compares the tag after `v` with the built source-distribution version, then publishes through the `pypi` GitHub environment with an OIDC `id-token: write` permission. It stores no persistent PyPI account credential in the repository. A release is intentionally a tagged commit, not merely whatever is currently on `main`.

## OpenWiki update automation

`.github/workflows/openwiki-update.yml` is distinct from product CI. It runs manually (`workflow_dispatch`) and daily at `0 8 * * *`. It checks out **full history** (`fetch-depth: 0`) because `openwiki code --update` compares `HEAD` with the last documented commit; a shallow clone makes that change summary empty.

The job installs Node 22 and global pinned tooling: `openwiki@0.3.3`, `mermaid@11.16.0`, and `jsdom@29.1.1`, then executes:

```bash
openwiki code --update --print
```

It configures `OPENWIKI_PROVIDER=openai-chatgpt` and a model ID. Browser-login OpenAI authentication has no unattended equivalent, so CI credentials must be supplied by maintainers. The LangSmith connector key is injected from `OPENWIKI_LANGSMITH_API_KEY`; optional tracing uses `LANGSMITH_API_KEY`, `LANGCHAIN_PROJECT=openwiki`, and `LANGCHAIN_TRACING_V2=true`. Do not put secret values in source, generated wiki content, or workflow logs.

The workflow has `contents: write` and `pull-requests: write`, so treat it as a privileged documentation writer. It creates branch `openwiki/update` and a PR whose configured add-paths are `openwiki`, `AGENTS.md`, `CLAUDE.md`, and this workflow file. Review that PR as generated change: source-grounding, link validity, diagram correctness, and any changes outside expected generated scope deserve particular scrutiny. Update workflow dependencies/runtime together when Mermaid validation or OpenWiki behavior changes.

## Maturity boundary

The README and changelog describe an extraction from a research system and explicitly classify this package as pre-alpha. Public APIs can move before 1.0. Keep compatibility assumptions narrow, retain the solver's Z3 differential checks, and update public exports plus focused tests with any API change.