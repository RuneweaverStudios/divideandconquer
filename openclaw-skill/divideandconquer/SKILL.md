# Divide and Conquer — OpenClaw Agent Skill

Task decomposition and parallel execution engine for OpenClaw agent platforms.

## Overview

This skill takes any complex task, decomposes it into atomic subtasks, builds a dependency DAG (directed acyclic graph), groups independent work into parallel execution waves, and dispatches agents concurrently. The goal is wall-clock time = critical path length, not sum of all work.

## How It Works

### 1. Decompose

Given a task, break it into atomic subtasks across five dimensions:
- **Code**: Files, modules, functions to create or modify
- **Research**: Lookups, exploration, docs to read
- **Tests**: Test cases to write
- **Config**: Setup, infrastructure, environment
- **Docs**: Documentation changes

### 1.5 Estimate Complexity and Subdivide

Assign each subtask a **weight** (1–4+) and approximate **tool calls**. If a task is **massive** (weight 4+ or 31+ tool calls), split it into smaller subtasks before mapping dependencies.

| Weight | Band (tool calls) | Examples |
|--------|-------------------|----------|
| 1 | 1–5 | Single read/edit, one command |
| 2 | 6–15 | Small feature slice, one module + tests |
| 3 | 16–30 | Multi-file work, non-trivial refactor |
| 4+ | 31+ | **Subdivide** — do not leave as one parallel agent |

Pass `weight` and optional `tool_calls` into `decompose.py` JSON. After the first wave plan, **balance** (Phase 3.5 in the Claude Code skill): flag waves where one task is ≥3× heavier than the average of the *lighter* tasks — the script groups **light vs heavy** in the markdown output.

### 2. Map Dependencies

For each subtask, identify what it truly depends on. Challenge false dependencies aggressively:

| False Dependency | Reality |
|-----------------|---------|
| "Tests need implementation" | Tests can be skeletons written first (TDD) |
| "UI needs API" | UI can use mock data |
| "Config needs code" | Config structure is usually known upfront |
| "File B imports from A" | Define interface first, build both in parallel |

### 3. Compute Waves

Use the `scripts/decompose.py` engine to compute optimal parallel execution waves. Include **`weight`** (and optional **`tool_calls`**) per subtask so the plan shows **~tool calls**, **total wave weight**, and **light vs heavy** grouping when one task is an outlier. Use `--no-balance` only if you want raw waves without complexity grouping.

```bash
python scripts/decompose.py --plan '[
  {"id":1, "desc":"Define types", "deps":[], "category":"code", "weight":1},
  {"id":2, "desc":"Research libs", "deps":[], "category":"research", "weight":2},
  {"id":3, "desc":"Build API",    "deps":[1], "category":"code", "weight":2},
  {"id":4, "desc":"Build UI",     "deps":[1], "category":"code", "weight":2},
  {"id":5, "desc":"Integration",  "deps":[3,4], "category":"code", "weight":3},
  {"id":6, "desc":"Tests",        "deps":[5], "category":"test", "weight":2}
]'
```

Output (abbreviated; includes per-task weight / tool-call estimates and per-wave totals):
```
## Execution Plan

### Wave 1 (parallel, 2 agents) ~~ No dependencies
- [1] Define types [weight: 1, ~5 tool calls]
- [2] Research libs [weight: 2, ~12 tool calls] [Explore]
  *Total wave weight: 3 | Wall-clock driver (max task): ~12 tool calls*

### Wave 2 (parallel, 2 agents) ~~ Depends on Wave 1
- [3] Build API [weight: 2, ~12 tool calls]
- [4] Build UI [weight: 2, ~12 tool calls]
  *Total wave weight: 4 | Wall-clock driver (max task): ~12 tool calls*

### Wave 3 (1 agent) ~~ Depends on Wave 2
- [5] Integration [weight: 3, ~22 tool calls]
  *Total wave weight: 3 | Wall-clock driver (max task): ~22 tool calls*

### Wave 4 (1 agent) ~~ Depends on Wave 3
- [6] Tests [weight: 2, ~12 tool calls]
  *Total wave weight: 2 | Wall-clock driver (max task): ~12 tool calls*

### Summary:
- Parallelism: 2 + 2 + 1 + 1 = 6 tasks across 4 waves
- Speedup: ~…
- Complexity: grouping appears when a wave mixes much lighter and much heavier tasks
```

### 4. Execute

On OpenClaw, dispatch agents via `sessions_spawn` for each wave. On Claude Code, use the Agent tool with multiple calls per message.

### 5. Merge

Collect results, resolve conflicts (worktrees if needed), verify coherence, run integration checks.

## Agent Routing

The script auto-routes subtask categories to agent types:

| Category | Agent Type | Model Tier |
|----------|-----------|------------|
| research, exploration | Explore | haiku |
| code, implementation, test, config | general-purpose | sonnet |
| architecture, review, security | architect / code-reviewer / security-reviewer | opus |

Override via `config.json` routing rules.

## Tools

### `decompose`
Break a task into subtasks with dependency mapping.

### `plan_waves`
Given subtasks with dependencies, compute optimal wave groupings.

### `execute`
Dispatch agents for each wave. Supports dry-run mode.

### `analyze`
Full pipeline: decompose + plan + estimate. Output without executing.

## Files

- `_meta.json` — OpenClaw metadata and tool definitions
- `config.json` — Routing tiers, concurrency limits, decomposition settings
- `scripts/decompose.py` — Core DAG engine (topological sort, wave computation, critical path, **balance_waves** complexity grouping)
- `workflows/` — Reserved for YAML workflow definitions

## Minimum Viable Parallelism

| Task Size | Approach |
|-----------|----------|
| Trivial (1-2 steps) | Execute directly, no decomposition |
| Small (3-5 steps) | Quick decomposition, 2-3 parallel agents if obvious |
| Medium (5-10 steps) | Full decomposition with wave plan |
| Large (10+ steps) | Full decomposition with user checkpoints between phases |
