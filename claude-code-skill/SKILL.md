---
name: divideandconquer
description: "Decompose complex tasks into parallel execution waves using dependency-mapped subagents. Activates on: build/implement/create/refactor requests, 3+ independent subtasks, multi-file changes, research with multiple questions, bug investigation. Default strategy for any non-trivial task."
version: 1.0.0
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

**Fast path**: <4 truly independent subtasks — skip Phases 2-3, go directly to execution with a minimal plan.

## Execution Protocol

### Phase 1: Decompose

Break the request into **atomic subtasks** (smallest units producing a meaningful artifact). Consider: code, research, tests, config, docs. Output a numbered task list, one line per subtask.

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

Present the plan:
```
## Execution Plan
### Wave 1 (parallel) ~~ No dependencies
- [1] Subtask description
- [2] Subtask description
### Wave 2 (parallel) ~~ Depends on Wave 1
- [3] Description (needs: 1)
- [4] Description (needs: 1, 2)
Parallelism: X tasks across Y waves | Speedup: ~Zx
```

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
