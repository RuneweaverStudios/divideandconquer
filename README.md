# Divide and Conquer

**Your Claude Code tasks finish 2-3x faster. Drop in one skill and Claude starts parallelizing automatically.**

---

## The Problem

You ask Claude to build a feature. It does the database, then the API, then the frontend, then the tests — one thing at a time. You watch and wait while it works through a queue that didn't need to be a queue.

Half that work could have been running simultaneously.

## The Fix

Install this skill and Claude starts thinking in parallel by default. It figures out which pieces of your task are independent, launches them all at once, and only waits when something genuinely depends on something else.

A 9-step feature build becomes 4 waves of concurrent work. Same result, fraction of the wall-clock time.

---

## Proven Results

We ran 68 evaluation runs across 8 real-world task types. Here's what happened:

```
                        WITH SKILL          WITHOUT SKILL
                        ──────────          ─────────────
Task Quality:           100%                70% +/- 22%
Consistency:            Perfect             Varies wildly run to run
Token Efficiency:       +2.4%               baseline
Tool Call Waste:        36.9 avg            39.9 avg (7.5% more wasted calls)
```

### The Standout: Refactoring

Splitting a 900-line file into 6 modules:

```
WITH SKILL:     172 seconds     25K tokens      12 tool calls
WITHOUT SKILL:  541 seconds     64K tokens      55 tool calls
                ───────────     ──────────      ─────────────
                3.1x FASTER     60% CHEAPER     78% FEWER CALLS
```

The skill used worktree isolation to extract all modules in parallel. Without it, Claude re-read the same file over and over, one extraction at a time.

### Bug Investigation

Finding why a Stripe webhook fails 5% of the time:

```
WITH SKILL:     352 seconds     65K tokens      42 tool calls
WITHOUT SKILL:  377 seconds     91K tokens      76 tool calls
                ───────────     ──────────      ─────────────
                7% faster       29% cheaper     45% fewer calls
```

The skill launched 4 research agents simultaneously (logs, codebase, git history, Stripe docs). Without it, Claude investigated one lead at a time and backtracked twice.

### Per-Task Breakdown

| Task | With Skill | Without | What Made the Difference |
|------|-----------|---------|------------------------|
| Full-stack feature | 100% | 0-62% | Parallel module builds across DB, API, UI |
| Bug investigation | 100% | 25-50% | Simultaneous research blitz |
| Greenfield project | 100% | 0-71% | Independent scaffolding per module |
| **File refactoring** | **100%** | **20-83%** | **Worktree isolation = 3.1x speedup** |
| Research synthesis | 100% | 50-75% | Parallel queries per topic |
| DB migration | 100% | 50-60% | Independent table migrations |
| Trivial fix | 100% | 100% | Correctly skipped (both pass) |
| Serial pipeline | 100% | 25-80% | Honest about limits, parallelized research |

> Full benchmark data with methodology: **[docs/BENCHMARKS.md](docs/BENCHMARKS.md)**

---

## Divide. Then Conquer.

The name isn't just clever — it's literally what happens in two acts.

### The Divide

You hand Claude a big job. Before touching any code, it splits that job apart.

Not randomly — it looks at every piece and asks: *"Does this piece actually need to wait for anything else, or can it start right now?"*

Most of the time, the answer is surprising. Building the frontend doesn't need the backend to exist yet — it just needs to agree on what the data looks like. Writing tests doesn't need the code to exist yet — you can write the test first and fill in the code after. Research tasks *never* need to wait for each other.

So Claude maps out which pieces depend on which, and groups the independent ones together into **waves** — batches of work that can all happen at the same time.

Think of it like planning a house build. You don't wait for the electrician to finish before calling the plumber. They work different rooms at the same time. The only thing you *actually* wait for is the foundation — everything else can overlap.

### The Conquer

Now Claude attacks each wave all at once. It spins up multiple workers (subagents), hands each one a clear job description, and lets them run simultaneously.

Wave 1 finishes. Everything that was waiting on Wave 1 can now go — Wave 2 launches, again all at once. And so on until everything's done.

Then it pulls all the results together, checks that nothing conflicts, runs the tests, and reviews the code. One clean delivery.

**The divide is the thinking. The conquer is the doing. Both happen automatically — you just describe what you want.**

---

## How It Looks

### Without the skill — single lane

```
TIME ──────────────────────────────────────────────────────────────────►

 ┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐
 │ Research  ││  Types   ││ Database ││   API    ││ Frontend ││  Tests   │
 └──────────┘└──────────┘└──────────┘└──────────┘└──────────┘└──────────┘

 6 steps x ~60s = ~360 seconds
```

### With the skill — multi-lane

```
TIME ──────────────────────────────────────────────►

 WAVE 1    ┌──────────┐
           │ Research  │
           ├──────────┤
           │  Types   │
           ├──────────┤
           │  Config  │
           └──────────┘
                │
 WAVE 2    ┌──────────┐
           │ Database │
           ├──────────┤
           │   API    │
           ├──────────┤
           │ Frontend │
           └──────────┘
                │
 WAVE 3    ┌──────────┐
           │  Tests   │
           ├──────────┤
           │  Review  │
           └──────────┘

 3 waves x ~60s = ~180 seconds (2x faster)
```

### The dependency graph Claude builds internally

```
  ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ Research  │     │  Types   │     │  Config  │
  └─────┬────┘     └────┬─────┘     └──────────┘
        │               │
        ▼               ▼
  ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ Frontend │     │ Database │     │   API    │
  └─────┬────┘     └────┬─────┘     └────┬─────┘
        │               │                │
        └───────────┬───┘────────────────┘
                    ▼
              ┌──────────┐
              │  Tests   │
              └─────┬────┘
                    ▼
              ┌──────────┐
              │  Review  │
              └──────────┘

  Arrows = "depends on". Same level = runs at the same time.
```

---

## Quick Start

```bash
# Clone
git clone https://github.com/RuneweaverStudios/divideandconquer.git

# Install (Claude Code)
cp -r divideandconquer/claude-code-skill ~/.claude/skills/divideandconquer

# Done. Ask Claude to build something complex and watch it parallelize.
```

> Full installation guide with OpenClaw, symlinks, global rules, and config: **[docs/USER-GUIDE.md](docs/USER-GUIDE.md)**

---

## Real Examples

### "Add a payment system with Stripe"

```
Wave 1 (3 agents):  Research patterns + Stripe docs + Define types
Wave 2 (4 agents):  DB migration + Checkout endpoint + Webhook handler + Subscription API
Wave 3 (3 agents):  Invoice endpoint + CheckoutPage component + InvoiceHistory component
Wave 4 (2 agents):  Tests + Code review + Security review

11 tasks in 4 waves. ~2.75x speedup.
```

### "Why is /dashboard taking 8 seconds to load?"

```
Wave 1 (5 agents):  Profile API + Check DB queries + Analyze React renders +
                    Check network waterfall + Review recent commits

                    → Found 3 root causes simultaneously

Wave 2 (3 agents):  Fix N+1 query + Batch API calls + Add React.memo

Result: 8s → 1.2s load time
```

### "Split this 900-line file into modules"

```
Wave 1 (3 agents):  Analyze file + Find shared utils + Run baseline tests
Wave 2 (1 agent):   Extract shared utilities
Wave 3 (4 agents):  Extract /users + /products + /orders + /admin (WORKTREES)
Wave 4 (2 agents):  Update router + Write tests
Wave 5 (1 agent):   Full test suite
Wave 6 (1 agent):   Code review

Result: 172s vs 541s without skill (3.1x faster)
```

> 6 more worked examples with full dependency graphs: **[docs/EXAMPLES.md](docs/EXAMPLES.md)**

---

## Two Formats

| Format | Where It Works | Install |
|--------|---------------|---------|
| **Claude Code Skill** | [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) | `cp -r claude-code-skill ~/.claude/skills/divideandconquer` |
| **OpenClaw Skill** | [OpenClaw](https://github.com/openclaw) / API agents | `cp -r openclaw-skill/divideandconquer /your/skills/` |

Both teach the same strategy. The OpenClaw version includes a Python DAG engine (`decompose.py`) for programmatic wave computation.

---

## How It Works Under the Hood

### The 5 Phases

```
 ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐
 │ 1.DECOMPOSE│───▶│ 2.MAP DEPS│───▶│ 3.PLAN    │───▶│ 4.EXECUTE │───▶│ 5.VERIFY  │
 │            │    │           │    │   WAVES   │    │           │    │           │
 │ Break task │    │ Find real │    │ Group     │    │ Launch    │    │ Merge,    │
 │ into atoms │    │ vs false  │    │ independ- │    │ parallel  │    │ test,     │
 │            │    │ depends   │    │ ent work  │    │ agents    │    │ review    │
 └───────────┘    └───────────┘    └───────────┘    └───────────┘    └───────────┘
```

### Smart Sizing

Not every task needs the full treatment:

| Task Size | What Happens | Benchmark Result |
|-----------|-------------|-----------------|
| **Tiny** (1-2 steps) | Executes directly. No overhead. | 100% pass rate both with and without |
| **Small** (3-5 steps) | Quick split, 2-3 agents if obvious | Modest speedup |
| **Medium** (5-10 steps) | Full wave plan shown before execution | 2-3x speedup |
| **Large** (10+ steps) | Full plan with phase checkpoints | 2-3x+ speedup |

### Built-in Safety

- **Worktree isolation** — Parallel workers that might edit the same file get their own copy. Changes merge afterward.
- **Test gate** — Won't call the job done without 80%+ test coverage.
- **Code review gate** — Dispatches review agents on all changed files.
- **Honest sizing** — Won't waste time decomposing a one-line fix.

---

## File Structure

```
divideandconquer/
├── README.md                              # You're reading it
├── LICENSE                                # MIT
├── docs/
│   ├── BENCHMARKS.md                      # Full benchmark data (68 runs, 8 task types)
│   ├── USER-GUIDE.md                      # Installation, config, troubleshooting
│   └── EXAMPLES.md                        # 6 worked examples with dependency graphs
│
├── claude-code-skill/                     # Claude Code format
│   ├── SKILL.md                           # The skill (install this)
│   └── references/
│       └── examples.md                    # Task-type decomposition templates
│
├── openclaw-skill/                        # OpenClaw format
│   └── divideandconquer/
│       ├── _meta.json                     # OpenClaw metadata + tool definitions
│       ├── SKILL.md                       # Documentation
│       ├── config.json                    # Routing, concurrency, decomposition settings
│       ├── scripts/
│       │   └── decompose.py              # DAG engine (waves, critical path, balance_waves grouping)
│       └── workflows/                     # Reserved for YAML workflows
│
└── scripts/
    └── decompose.py                       # Standalone DAG engine (mirrors OpenClaw copy)
```

---

## FAQ

**Q: Does this actually make things faster?**
Yes. Benchmarked across 68 runs. Refactoring tasks see 3.1x speedup. Bug investigations use 29% fewer tokens. The skill adds ~2.4% token overhead on average — negligible cost for consistent quality. [Full data](docs/BENCHMARKS.md).

**Q: What if I don't want it to parallelize?**
The skill checks task size first. Trivial tasks (1-2 steps) are executed directly — benchmarks confirm both with and without the skill pass at 100% for small tasks. You can also tell Claude "do this sequentially."

**Q: Does this work on Claude.ai (the website)?**
The planning and decomposition work everywhere. Parallel *execution* requires Claude Code's Agent tool. On Claude.ai, the skill gives you a structured plan but executes waves one at a time.

**Q: Will parallel agents conflict with each other?**
The skill handles this with git worktrees — parallel agents that might edit the same file work in isolated copies. This is how the refactoring benchmark achieved 3.1x speedup.

**Q: What does it cost in tokens?**
On average, +2.4% more tokens. On bug investigations, it actually *saves* 29% because it avoids backtracking and wasted tool calls. [Detailed cost analysis](docs/BENCHMARKS.md#cost-benefit-summary).

---

## Documentation

| Document | What's In It |
|----------|-------------|
| **[docs/BENCHMARKS.md](docs/BENCHMARKS.md)** | 68 evaluation runs, per-task breakdowns, assertion analysis, cost-benefit summary |
| **[docs/USER-GUIDE.md](docs/USER-GUIDE.md)** | Installation, configuration, usage patterns, troubleshooting |
| **[docs/EXAMPLES.md](docs/EXAMPLES.md)** | 6 real-world examples with dependency graphs and wave plans |

---

## License

MIT

---

**[RuneweaverStudios](https://github.com/RuneweaverStudios)**
