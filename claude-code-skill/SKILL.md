---
name: divideandconquer
description: "Analyze any task, decompose it into subtasks, map dependencies, and execute the maximum number of operations in parallel. Use this skill whenever the user gives you a complex task, multi-step project, feature request, refactoring job, research question, or any work that could benefit from parallel execution. Activate proactively when you detect a task has 3+ independent parts, when the user says 'build', 'implement', 'create', 'set up', 'migrate', or 'refactor' something non-trivial. Also use when the user explicitly asks to parallelize, speed up, or divide work. Even if the user doesn't mention parallelism, if you can see that a request has multiple independent subtasks, use this skill to maximize throughput. This skill is the default approach for any non-trivial task."
version: 1.0.0
---

# Divide and Conquer

Break any task into its smallest independent units, build a dependency graph, identify the critical path, and execute with maximum concurrency using the Agent tool. The goal is to turn wall-clock time into the length of the longest dependency chain, not the sum of all work.

## Core Philosophy

**Serial is the enemy. Parallel is the default.**

Most tasks contain hidden parallelism. A feature that looks sequential ("set up DB, build API, write tests, add UI") actually has independent subtrees that can execute simultaneously. Your job is to find every opportunity for concurrency and exploit it.

## When This Skill Activates

This skill should activate for any task where:
- There are 3+ distinct subtasks
- Some subtasks have no dependency on each other
- The user wants something "built", "implemented", "set up", or "refactored"
- The user explicitly asks to parallelize or speed up work
- You recognize the task would benefit from divide-and-conquer even if the user didn't ask

## Execution Protocol

### Phase 1: Decompose

Read the user's request carefully. Break it into **atomic subtasks** — the smallest units of work that produce a meaningful artifact (a file, a function, a config, a test, a research finding).

Think about the task across these dimensions:
- **Code**: What files/modules/functions need to be created or modified?
- **Research**: What needs to be looked up, explored, or understood first?
- **Tests**: What tests need to be written?
- **Config**: What configuration, setup, or infrastructure is needed?
- **Docs**: What documentation changes are needed?

Output a numbered task list. Keep it concise — one line per subtask.

### Phase 2: Map Dependencies

For each subtask, determine what it depends on. A subtask depends on another only if it **cannot start** without the other's output. Be aggressive about finding independence — most tasks are more parallel than they appear.

Common false dependencies to challenge:
- "Tests depend on implementation" — No. Tests can be written first (TDD). Write test skeletons in parallel with implementation.
- "UI depends on API" — No. UI can use mock data. Build both in parallel.
- "Config depends on code" — Rarely. Config structure is usually known upfront.
- "File B imports from File A" — Only a dependency if you need A's exact exports. Often you can define the interface first and build both.

Build a dependency map. Use this mental model:

```
Subtask → [list of subtask IDs it depends on]
```

If the dependency list is empty, the subtask is a **root** — it can start immediately.

### Phase 3: Plan Execution Waves

Group subtasks into **waves** — sets of tasks that can execute simultaneously:

- **Wave 1**: All root tasks (no dependencies). Launch ALL of these in parallel.
- **Wave 2**: Tasks whose dependencies are all satisfied by Wave 1. Launch ALL in parallel.
- **Wave N**: Continue until all tasks are scheduled.

**Optional validation**: If `scripts/decompose.py` is available, validate your plan for cycles and missing dependencies:
```bash
python scripts/decompose.py --validate '<your subtasks as JSON>'
```
This catches errors the LLM decomposition might introduce and provides an authoritative speedup estimate using weighted task times.

Present the execution plan to the user in this format:

```
## Execution Plan

### Wave 1 (parallel) ~~ No dependencies
- [1] Description of subtask
- [2] Description of subtask
- [3] Description of subtask

### Wave 2 (parallel) ~~ Depends on Wave 1
- [4] Description (needs: 1)
- [5] Description (needs: 2, 3)

### Wave 3 (parallel) ~~ Depends on Wave 2
- [6] Description (needs: 4, 5)

Parallelism: 3 + 2 + 1 = 6 tasks across 3 waves
Sequential equivalent: 6 waves
Speedup: ~2x
```

### Phase 4: Execute

Launch each wave using the **Agent tool**. You MUST actually call the Agent tool to spawn subagents — do not just execute tasks yourself sequentially. The entire point of this skill is concurrent execution via multiple agents. If a wave has 3 independent tasks, your response must contain 3 Agent tool calls in a single message.

Why this matters: benchmarks show that executing waves yourself (without subagents) produces structured plans but misses the actual speedup. The plan is the means, not the end — parallel agent dispatch is what delivers wall-clock savings.

Critical rules:

1. **All tasks within a wave launch in a single message** — Use multiple Agent tool calls in one response. If you catch yourself writing code directly for Wave 2 while Wave 1 agents could be running, stop and dispatch agents instead.
2. **Pick the right agent type** — Match subtasks to specialized agents when available:
   - Research/exploration → `subagent_type: "Explore"`
   - Architecture decisions → `subagent_type: "everything-claude-code:architect"`
   - Code review → `subagent_type: "everything-claude-code:code-reviewer"`
   - Build errors → `subagent_type: "everything-claude-code:build-error-resolver"`
   - Security review → `subagent_type: "everything-claude-code:security-reviewer"`
   - General coding → default (general-purpose)
3. **Use background agents for long-running tasks** — Set `run_in_background: true` for tasks that don't block the next wave. Continue working on other things while they complete.
4. **Use worktrees for file conflicts** — If two parallel agents might edit the same file, use `isolation: "worktree"` for at least one of them.
5. **Give agents complete context** — Each agent starts fresh. Include everything it needs: file paths, requirements, constraints, and expected output format.
6. **Prefer structured tool calls over ad-hoc exploration** — The decomposition plan tells you exactly what tools each subtask needs. This avoids wasted retries and failed tool calls that unstructured approaches suffer from (benchmarks show 5+ avoidable errors without planning).

### Phase 5: Merge, Verify, and Synthesize

After all waves complete:
1. **Collect results** from all agents
2. **Merge worktrees** (if used) — merge one at a time into the main branch. After each merge, run build/lint to catch conflicts early. If a conflict occurs, resolve it before merging the next worktree. Order merges by dependency (foundational modules first).
3. **Verify coherence** — confirm the combined output is consistent across all agent results
4. **Run integration checks** (build, lint, tests) if code was produced
5. **Test completeness gate** (MANDATORY for code tasks) — Do not skip this step. Verify:
   - Tests exist for every new module/function created in earlier waves
   - Run coverage and confirm 80%+ (if below, launch a test-completion agent NOW before proceeding)
   - Both unit and integration tests are present where appropriate
   - The planning overhead must not eat into test depth — if agents produced code without tests, this is a failure
6. **Review gate** (MANDATORY for code tasks) — Dispatch review agents in the final wave:
   - Launch `code-reviewer` agent on all changed files
   - Launch `security-reviewer` agent if the task touches auth, user input, API endpoints, or sensitive data
   - Address CRITICAL and HIGH issues before presenting results
7. **Present summary** to the user: tasks completed, waves executed, conflicts resolved, test coverage, and review findings

## Decomposition Heuristics

Use these patterns to find parallelism in common task types:

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

## Minimum Viable Parallelism

Not every task needs full decomposition. Check this table FIRST before entering Phase 1. The overhead of planning must not exceed the savings from parallelism.

| Task Size | Approach | Planning Output |
|-----------|----------|-----------------|
| **Trivial** (1-2 steps) | Execute directly. No decomposition, no agents, no skip-decision documentation. | None — just do it. |
| **Small** (3-5 steps) | Quick mental decomposition. Launch 2-3 agents only if parallelism is obvious and agents save real wall-clock time. | One-line note at most. No formal wave plan. |
| **Mostly-serial** (dependency chain >70% of tasks) | Acknowledge serial constraint upfront. Only parallelize Wave 1 research/reading. Skip formal wave plan formatting. | Brief acknowledgment + Wave 1 parallel list. |
| **Medium** (5-10 independent steps) | Full decomposition with wave plan. Show the user before executing. | Full wave plan. |
| **Large** (10+ steps) | Full decomposition. Break into phases with user checkpoints between them. | Full wave plan + phase boundaries. |

**Fast path**: If the task has fewer than 4 truly independent subtasks, skip Phases 2-3 and go directly to execution with a minimal plan. The formal wave plan format is only worth the tokens when there are 4+ independent tasks to schedule.

## Example

**User request**: "Add a new /analytics endpoint that reads from the events table, includes rate limiting, and has full test coverage"

**Decomposition**:
```
1. Research: Check existing API patterns in codebase
2. Research: Look up rate limiting middleware in use
3. Types: Define analytics request/response types
4. DB: Write the events table query function
5. Handler: Implement the /analytics route handler
6. Middleware: Configure rate limiting for the endpoint
7. Tests: Unit tests for query function
8. Tests: Integration tests for the endpoint
9. Tests: Rate limiting tests
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

This skill works across environments:

| Platform | Agent Dispatch | Worktrees | Background Agents |
|----------|---------------|-----------|-------------------|
| **Claude Code CLI** | Full Agent tool with all subagent types | Yes | Yes |
| **Claude.ai** | No subagents — execute waves sequentially yourself | No | No |
| **OpenClaw / API** | Use `sessions_spawn` for parallel agents | Depends on runtime | Depends on runtime |

On platforms without subagents, the skill still provides value through structured decomposition and wave planning — you execute each wave's tasks yourself but in the optimal order, and the user sees the plan upfront.

## Worked Examples

For detailed walk-throughs of real decompositions (full-stack features, bug hunts, greenfield projects, refactors, and serial tasks), read `references/examples.md`. Load it when you need guidance on a specific task type or when the decomposition feels ambiguous.
