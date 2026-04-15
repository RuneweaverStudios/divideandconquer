# Decomposition Heuristics & Reference

## Task Complexity and Tool Calls

Estimate **weight** (1–4+) and **approximate tool calls** for every subtask before you map dependencies. This prevents “3 agents” waves where two agents finish in minutes and the third runs for hours.

| Weight | Tool calls (approx.) | When to use |
|--------|----------------------|-------------|
| 1 | 1–5 | Single file read, one edit, one command |
| 2 | 6–15 | Small feature slice, one module + tests |
| 3 | 16–30 | Multi-file change, non-trivial refactor |
| 4+ | 31+ | **Too big for one agent task** — subdivide (Phase 1.5) |

**Rule of thumb**: If you cannot name ~3–8 concrete tool steps, the task is underspecified or too large.

Pass `weight` and optional `tool_calls` into `scripts/decompose.py --plan` so waves include **complexity grouping** (light vs heavy outliers within a wave).

## Subdividing Heavy Tasks

When a task estimates **> ~30 tool calls** (weight 4+), break it down before parallel execution:

**Implementation**

- Split by **file** (one subtask per new/changed file when possible)
- Split by **function / public API** boundary
- Split by **layer** (types → core logic → adapters → tests)

**Research**

- One subtask per **sub-question** or **source bucket** (codebase vs docs vs web)

**Tests**

- Split by **layer** (unit vs integration vs e2e) or by **module under test**

**Example**

```
BEFORE: [3] Implement user authentication  [weight 4+, ~80 tool calls]

AFTER:
  [3a] Auth types + interfaces              [weight 2, ~12 tool calls]
  [3b] Password hashing + verification      [weight 2, ~14 tool calls]
  [3c] JWT issue/verify + middleware       [weight 2, ~16 tool calls]
  [3d] Login/logout routes + validation     [weight 2, ~14 tool calls]
  [3e] Auth unit tests                      [weight 2, ~12 tool calls]
```

Then re-map dependencies so parallel work stays **actually** parallel.

## Balancing Waves (Outliers)

After an initial wave plan (Phase 3), check each wave:

1. **Outlier detection**: Let `max_w` be the largest weight in the wave and `avg_others` the average weight of tasks **strictly lighter** than `max_w`. If `max_w >= 3 * avg_others` and there is more than one task in the wave, the heaviest work is an **outlier** — it will dominate wall-clock time for that wave.
2. **Prefer splitting** (Phase 1.5) over living with one giant task.
3. **Call it out** in the plan: group light vs heavy, or put the heavy slice in its **own visible sub-phase** so “3 agents” does not look equal when it is not.

**Example — before / after balancing (conceptual)**

```
BEFORE (imbalanced dependency wave):
  Wave 2: [3] Light [w:1] | [4] Light [w:1] | [5] Heavy [w:4]
  → Wall-clock ≈ heavy task; two agents idle most of the time.

AFTER (preferred): subdivide [5] into [5a][5b][5c] with deps, or run [5] as explicitly isolated work with honest runtime notes.

AFTER (documentation-only): same wave, grouped:
  Light: [3], [4]  |  Heavy / driver: [5]  (~N tool calls)
```

## Task-Type Wave Templates

### Feature Implementation
```
Wave 1: [types/interfaces] [test skeletons] [config/env setup] [research/docs lookup]
Wave 2: [implementation modules - each independent file in parallel] [mock data/fixtures]
Wave 3: [integration points] [fill in test assertions]
Wave 4: [code review] [security review] [build verification]
```

### Bug Investigation
```
Wave 1: [read error logs] [search codebase for related code] [check recent git changes] [look up docs]
Wave 2: [analyze each suspect area in parallel]
Wave 3: [implement fix] [write regression test]
```

### Refactoring
```
Wave 1: [analyze current code] [identify all callers/dependents] [check test coverage]
Wave 2: [refactor independent modules in parallel using worktrees]
Wave 3: [update integration points] [update tests]
Wave 4: [verify build] [run full test suite]
```

### Research / Analysis
```
Wave 1: [search topic A] [search topic B] [search topic C] [fetch relevant docs]
Wave 2: [deep-dive findings from Wave 1 - each in parallel]
Wave 3: [synthesize and present]
```

### Project Setup
```
Wave 1: [init project structure] [research best practices] [identify dependencies]
Wave 2: [install deps] [create config files] [set up CI] [create initial types]
Wave 3: [scaffold main modules in parallel] [write initial tests]
```

## Anti-Patterns to Avoid

- **Over-decomposition**: Don't split a 5-line function into 3 agents. Use agents for meaningful chunks of work.
- **False parallelism**: Don't launch agents that will immediately block waiting for each other's files.
- **Context duplication**: Don't have 5 agents all read the same 10 files. Have one agent do the reading and share findings.
- **Ignoring the merge**: Parallel execution is pointless if merging the results takes longer than serial would have.
- **Skipping the plan**: Always show the user the wave plan before executing. They may spot dependencies you missed or want to adjust scope.
- **Unequal “parallel” tasks**: Don't group one **massive** task with two **tiny** tasks in the same wave without subdivision or explicit heavy/light grouping — two agents finish fast and idle while the third dominates wall-clock time.

## Worked Example: Analytics Endpoint

**User request**: "Add a new /analytics endpoint that reads from the events table, includes rate limiting, and has full test coverage"

**Decomposition** (with **weight** / ~**tool calls** per subtask):
```
1. Research: Check existing API patterns in codebase        [w:2, ~12]
2. Research: Look up rate limiting middleware in use       [w:2, ~12]
3. Types: Define analytics request/response types          [w:1, ~5]
4. DB: Write the events table query function               [w:2, ~14]
5. Handler: Implement the /analytics route handler         [w:2, ~14]
6. Middleware: Configure rate limiting for the endpoint    [w:2, ~12]
7. Tests: Unit tests for query function                    [w:2, ~10]
8. Tests: Integration tests for the endpoint               [w:2, ~14]
9. Tests: Rate limiting tests                              [w:2, ~10]
```

**Dependency map**:
```
1 → []        (root)
2 → []        (root)
3 → []        (root - types can be defined from requirements alone)
4 → [1, 3]    (needs patterns + types)
5 → [1, 3]    (needs patterns + types)
6 → [2]       (needs rate limit research)
7 → [4]       (needs query function)
8 → [5, 6]    (needs handler + middleware)
9 → [6]       (needs middleware)
```

**Execution plan**:
```
Wave 1 (parallel): [1] [2] [3]           — 3 agents: research + types
Wave 2 (parallel): [4] [5] [6]           — 3 agents: implementation
Wave 3 (parallel): [7] [8] [9]           — 3 agents: tests
Wave 4 (parallel): [10] code-review [11] security-review — 2 review agents
                                           Total: 11 tasks in 4 waves (~2.75x speedup)
```

## Platform Notes

| Platform | Agent Dispatch | Worktrees | Background Agents |
|----------|---------------|-----------|-------------------|
| **Claude Code CLI** | Full Agent tool with all subagent types | Yes | Yes |
| **Claude.ai** | No subagents — execute waves sequentially yourself | No | No |
| **OpenClaw / API** | Use `sessions_spawn` for parallel agents | Depends on runtime | Depends on runtime |

On platforms without subagents, the skill still provides value through structured decomposition and wave planning — you execute each wave's tasks yourself in optimal order.
