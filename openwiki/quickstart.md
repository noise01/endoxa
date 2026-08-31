---
type: wiki entrypoint
title: Endoxa code wiki
description: "A source-grounded guide to Endoxa's governed-belief library: packages, change routes, public APIs, tests, and operational checks."
tags: [endoxa, navigation, architecture]
---

# Endoxa code wiki

Endoxa is a Python 3.14+ pre-alpha library for governed agent beliefs: it checks logical consistency, selects or holds revision outcomes, records decisions as an append-only ledger, provides a separate ordered proposition-store port, and measures calibration and rule connectivity. The public package is deliberately a DAG, not an agent framework. Start with [architecture](architecture/overview.md) for ownership and dependency direction.

## Main sections

| Area | Canonical page | What it answers |
|---|---|---|
| Package architecture and dependency boundary | [Architecture overview](architecture/overview.md) | Why the five packages exist, allowed imports, primary runtime flow, and public entrypoints. |
| Governance decisions and revision | [Decision and revision](governance/decision-and-revision.md) | How `govern` turns beliefs and TPTP constraints into host-applied operations. |
| Ledger, derived view, audit compatibility | [Ledger and view](governance/ledger-and-view.md) | `LedgerOp`, audit replay, evidence, holds, support, provenance, and epistemic statuses. |
| SMT engine | [Solver API and engine](solver/api-and-engine.md) | AST/TPTP/DIMACS paths, `Solver`, tri-state bounded checks, cores, and validation. |
| Trace persistence port | [Trace proposition store](trace/proposition-store.md) | `Proposition` and the asynchronous `TraceStore` ordering contract. |
| Calibration instruments | [Calibration](instruments/calibration.md) | Live accumulators and replayed tumbling-window curves. |
| Coverage instruments | [Coverage](instruments/coverage.md) | Rule predicate graph, directional antecedents, and coverage snapshots. |
| Atom utility | [Atom syntax](syntax/atoms.md) | The intentionally narrow `parse_atom` contract. |
| Build and automation | [Development and operations](operations/development.md) | Extras, CI, release, import layers, and OpenWiki maintenance. |

## Task routing

| Engineering intent | Read / change entrypoints | Focused tests | Minimal validation |
|---|---|---|---|
| Integrate governed beliefs or change conflict policy | [Decision and revision](governance/decision-and-revision.md); `endoxa.governance.govern`, `resolution.py`, `revision/` | `tests/governance/test_resolution.py`, `tests/governance/revision/` | `uv run pytest tests/governance/test_resolution.py tests/governance/revision -q` |
| Alter ledger schema, audit mapping, view/evidence semantics | [Ledger and view](governance/ledger-and-view.md); `ledger.py`, `derive.py`, `view.py` | `test_ledger_schema.py`, `test_derive.py`, `test_view.py` | `uv run pytest tests/governance/test_ledger_schema.py tests/governance/test_derive.py tests/governance/test_view.py -q` |
| Extend SMT functionality or parsing | [Solver API and engine](solver/api-and-engine.md); `endoxa.solver`, `engine.py`, `parsers/` | `tests/solver/`, `tests/differential/` | `uv run pytest tests/solver tests/differential -q` |
| Implement a trace persistence adapter | [Trace proposition store](trace/proposition-store.md); `TraceStore` | `tests/trace/test_trace_store.py` | `uv run pytest tests/trace/test_trace_store.py -q` |
| Change calibration/replay/window behavior | [Calibration](instruments/calibration.md); `instruments/calibration/` | calibration accumulator and windowed suites | `uv run pytest tests/instruments/test_calibration_accumulators.py tests/instruments/test_calibration_windowed.py -q` |
| Change rule-network diagnostics | [Coverage](instruments/coverage.md); `coverage/graph.py`, `snapshot.py` | `tests/instruments/test_coverage.py` | `uv run pytest tests/instruments/test_coverage.py -q` |
| Change atom extraction | [Atom syntax](syntax/atoms.md); `syntax/atoms.py` | `tests/syntax/test_atoms.py` | `uv run pytest tests/syntax/test_atoms.py -q` |
| Change packaging, CI, release, or documentation automation | [Development and operations](operations/development.md); `pyproject.toml`, `.github/workflows/` | `tests/test_package_boundary.py`, `tests/test_smoke.py` | `uv run lint-imports && uv run pytest tests/test_package_boundary.py tests/test_smoke.py -q` |

## Repository-wide check

The CI-equivalent command sequence is documented in [Development and operations](operations/development.md). For a broad local gate, install all extras and dev dependencies, then run:

```bash
uv sync --all-extras --dev
uv run ruff check .
uv run ruff format --check .
uv run lint-imports
uv run pytest
```

## Scope and backlog

All manifest-backed runtime packages, their public APIs, representative tests, and workflows are documented above. There are no evidence-blocked deferrals in this initialization.