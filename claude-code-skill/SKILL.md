---
name: divideandconquer
description: "Decompose complex tasks into parallel execution waves using dependency-mapped subagents. Activates on: build/implement/create/refactor requests, 3+ independent subtasks, multi-file changes, research with multiple questions, bug investigation. Default strategy for any non-trivial task."
version: 1.1.0
---

# Divide and Conquer

Break any task into its smallest independent units, build a dependency graph, identify the critical path, and execute with maximum concurrency using the Agent tool.

## Core Philosophy

**Serial is the enemy. Parallel is the default.**

## When This Skill Activates

- 3+ distinct subtasks with some independence between them
- Build/implement/set up/refactor requests
- User explicitly asks to parallelize work
- You recognize hidden parallelism the user didn't mention

## Minimum Viable Parallelism

Check this table BEFORE entering Phase 1. Planning overhead must not exceed parallelism savings.

| Task Size | Approach | Planning Output |
|-----------|----------|-----------------|
| **Trivial** (1-2 steps) | Execute directly. No decomposition. | None — just do it. |
| **Small** (3-5 steps) | Quick decomposition. 2-3 agents only if parallelism is obvious. | One-line note at most. |
| **Mostly-serial** (>70% dependent) | Acknowledge serial constraint. Only parallelize Wave 1 research/reading. | Brief note + Wave 1 parallel list. |
| **Medium** (5-10 independent steps) | Full decomposition with wave plan. | Full wave plan. |
| **Large** (10+ steps) | Full decomposition with user checkpoints between phases. | Full wave plan + phase boundaries. |

**Fast path**: <4 truly independent subtasks — skip Phases 2–3, go directly to execution with a minimal plan.

## Execution Protocol

### Phase 1: Decompose

Break the request into **atomic subtasks** (smallest units producing a meaningful artifact). Consider: code, research, tests, config, docs. Output a numbered task list, one line per subtask.

### Phase 1.5: Estimate Complexity and Subdivide

For each subtask, estimate **relative effort** and **approximate tool calls** (reads, searches, edits, test runs). Use this scale:

| Complexity | Weight | Tool calls (approx.) | Examples |
|------------|--------|----------------------|----------|
| **Light** | 1 | 1–5 | Read a file, run one command, fix a typo |
| **Medium** | 2 | 6–15 | Implement a small function, unit tests for one module |
| **Heavy** | 3 | 16–30 | Multi-file component, refactor a module |
| **Massive** | 4+ | 31+ | Full feature slice, large integration, broad exploration |

**Rule**: If a subtask is **Massive** (weight 4+, or 31+ tool calls), **subdivide** it into smaller subtasks (easy/medium chunks with bounded tool calls), then re-number and **re-map dependencies** (Phase 2).

Output example:

```
1. Define types [weight: 1, ~5 tool calls]
2. Research WebSocket libs [weight: 2, ~12 tool calls]
3a. API handler — types and validation [weight: 2, ~12 tool calls]  (split from oversized task 3)
3b. API handler — business logic [weight: 2, ~14 tool calls]
3c. API handler — errors and logging [weight: 2, ~10 tool calls]
```

When using `scripts/decompose.py`, pass **`weight`** (1–4+; maps to effort bands) and optionally **`tool_calls`** per subtask so the engine can group and summarize complexity.

### Phase 2: Map Dependencies

For each subtask, determine what it **cannot start without**. Be aggressive about finding independence.

Challenge false dependencies: tests can be written before implementation (TDD), UI can use mock data, config structure is usually known upfront, interfaces can be defined before implementations.

Build a dependency map: `Subtask → [list of dependency IDs]`. Empty list = root task (starts immediately).

### Phase 3: Plan Execution Waves

Group into waves — sets of tasks that execute simultaneously:
- **Wave 1**: All root tasks (no dependencies) — launch ALL in parallel
- **Wave 2**: Tasks whose dependencies are satisfied by Wave 1
- **Wave N**: Continue until all tasks scheduled

**Optional**: If `scripts/decompose.py` is available, validate with `python scripts/decompose.py --validate '<JSON>'`. This catches cycles and missing dependencies the LLM decomposition might introduce and provides an authoritative speedup estimate.

Pass each subtask’s **`weight`** (and optional **`tool_calls`**) in the JSON you give to `--plan`. The script will **group** light vs heavy tasks within a wave when one task is an outlier (see Phase 3.5) and print per-wave complexity totals.

Present the plan:
```
## Execution Plan
### Wave 1 (parallel) ~~ No dependencies
- [1] Subtask description [weight: 1, ~5 tool calls]
- [2] Subtask description [weight: 2, ~12 tool calls]
  Total wave weight: 3 | Wall-clock driver: ~12 tool calls (max task)
### Wave 2 (parallel) ~~ Depends on Wave 1
- [3] Description (needs: 1)
- [4] Description (needs: 1, 2)
Parallelism: X tasks across Y waves | Speedup: ~Zx
```

### Phase 3.5: Balance Waves (after initial wave plan)

Run this **immediately after** Phase 3 produces an initial wave list (or after `decompose.py --plan` output).

1. **Outlier detection**: Within a wave, if the heaviest task’s weight is **≥ 3×** the average weight of the **other** tasks in that wave, treat it as a **heavy outlier**. Visually **group** light vs heavy in the plan (or isolate the heavy slice into its **own sub-phase** in the same wave so the team sees where wall-clock time goes).
2. **Prefer subdivision over “grouping alone”**: If imbalance is extreme, return to Phase 1.5 and **split** the heavy task into smaller parallelizable subtasks instead of relying on one agent.
3. **Wave weight cap**: If **sum of weights** in one wave is very large (e.g. > 10), consider splitting work across more subtasks or more waves—**unless** dependencies force one serial chain.
4. **Honest reporting**: If dependencies make imbalance unavoidable, say so explicitly (e.g. “Wave 3 wall-clock is dominated by task [7]; others finish early.”).

**Isolation rule**: Complex / high–tool-call work should **not** be lumped with quick tasks in a way that hides risk—either **subdivide** it (preferred) or **call it out** in its own wave group so it does not “pretend” to be the same size as sibling tasks.

**Tooling**: Use `scripts/decompose.py --plan '<JSON>'` to compute waves from weighted JSON. Use `--no-balance` only if you intentionally want raw dependency-only waves without complexity grouping.

### Phase 4: Execute

Launch each wave using the **Agent tool**. You MUST call the Agent tool to spawn subagents — do not execute tasks yourself sequentially. If you catch yourself writing code directly while agents could be running, stop and dispatch agents instead. The plan is the means, not the end — parallel agent dispatch is what delivers wall-clock savings.

Critical rules:
1. **All tasks within a wave launch in a single message** — multiple Agent tool calls in one response.
2. **Pick the right agent type** — Research → `Explore`, architecture → `architect`, code review → `code-reviewer`, security → `security-reviewer`, build errors → `build-error-resolver`, general coding → default.
3. **Use `run_in_background: true`** for tasks that don't block the next wave.
4. **Use `isolation: "worktree"`** when parallel agents might edit the same file.
5. **Give agents complete context** — each starts fresh, include file paths, requirements, constraints, expected output.
6. **Prefer structured tool calls over ad-hoc exploration** — the plan tells you exactly what tools each subtask needs.

### Phase 5: Merge, Verify, and Synthesize

After all waves complete:
1. **Collect results** from all agents
2. **Merge worktrees** (if used) — one at a time, run build/lint after each, resolve conflicts before proceeding. Order by dependency.
3. **Verify coherence** — confirm combined output is consistent
4. **Run integration checks** (build, lint, tests) if code was produced
5. **Test completeness gate** (MANDATORY for code tasks):
   - Tests exist for every new module/function
   - Coverage 80%+ (if below, launch a test-completion agent NOW)
   - Both unit and integration tests present where appropriate
6. **Review gate** (MANDATORY for code tasks):
   - Launch `code-reviewer` on all changed files
   - Launch `security-reviewer` if task touches auth, user input, API endpoints, or sensitive data
   - Address CRITICAL and HIGH issues before presenting results
7. **Present summary**: tasks completed, waves executed, conflicts resolved, test coverage, review findings

## Additional References

For detailed walk-throughs of real decompositions, read `references/examples.md`.

For task-type templates, anti-patterns, and worked examples, load `references/heuristics.md`
