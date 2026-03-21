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

### 2. Map Dependencies

For each subtask, identify what it truly depends on. Challenge false dependencies aggressively:

| False Dependency | Reality |
|-----------------|---------|
| "Tests need implementation" | Tests can be skeletons written first (TDD) |
| "UI needs API" | UI can use mock data |
| "Config needs code" | Config structure is usually known upfront |
| "File B imports from A" | Define interface first, build both in parallel |

### 3. Compute Waves

Use the `scripts/decompose.py` engine to compute optimal parallel execution waves:

```bash
python scripts/decompose.py --plan '[
  {"id":1, "desc":"Define types", "deps":[], "category":"code"},
  {"id":2, "desc":"Research libs", "deps":[], "category":"research"},
  {"id":3, "desc":"Build API",    "deps":[1], "category":"code"},
  {"id":4, "desc":"Build UI",     "deps":[1], "category":"code"},
  {"id":5, "desc":"Integration",  "deps":[3,4], "category":"code"},
  {"id":6, "desc":"Tests",        "deps":[5], "category":"test"}
]'
```

Output:
```
## Execution Plan

### Wave 1 (parallel, 2 agents) ~~ No dependencies
- [1] Define types
- [2] Research libs [Explore]

### Wave 2 (parallel, 2 agents) ~~ Depends on Wave 1
- [3] Build API
- [4] Build UI

### Wave 3 (1 agent) ~~ Depends on Wave 2
- [5] Integration

### Wave 4 (1 agent) ~~ Depends on Wave 3
- [6] Tests

Summary:
- Parallelism: 2 + 2 + 1 + 1 = 6 tasks across 4 waves
- Speedup: ~1.5x
- Critical path: 4
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
- `scripts/decompose.py` — Core DAG engine (topological sort, wave computation, critical path)
- `workflows/` — Reserved for YAML workflow definitions

## Minimum Viable Parallelism

| Task Size | Approach |
|-----------|----------|
| Trivial (1-2 steps) | Execute directly, no decomposition |
| Small (3-5 steps) | Quick decomposition, 2-3 parallel agents if obvious |
| Medium (5-10 steps) | Full decomposition with wave plan |
| Large (10+ steps) | Full decomposition with user checkpoints between phases |
