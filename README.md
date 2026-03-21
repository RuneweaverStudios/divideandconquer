# Divide and Conquer

**Make your AI coding assistant do multiple things at once instead of one thing at a time.**

## What Is This?

When you ask an AI assistant like Claude to build something — say, "add a chat feature with a database, an API, a frontend, and tests" — it normally does each piece one at a time. First the database, then the API, then the frontend, then the tests. Like a single cook making a four-course meal.

**Divide and Conquer changes that.** It teaches Claude to work more like a kitchen brigade: figure out which dishes can be prepared simultaneously, assign each to a different chef (subagent), and get the whole meal done in a fraction of the time.

Here's what happens when you install this skill:

1. **You describe what you want** — "Build me X" or "Fix this bug" or "Refactor these files"
2. **Claude breaks your request into small pieces** — What can be researched? What can be coded independently? What depends on what?
3. **Claude figures out what can happen at the same time** — Research tasks don't need to wait for each other. The frontend and backend can be built in parallel if they agree on data shapes upfront.
4. **Claude launches multiple workers simultaneously** — Instead of doing tasks 1 through 10 in order, it runs tasks 1, 2, and 3 at the same time, then 4, 5, and 6 together once 1-3 finish, and so on.
5. **Claude merges everything together and verifies it works** — Runs tests, checks for conflicts, reviews the code.

The result: tasks that would take 10 sequential steps finish in 3-4 "waves" of parallel work. That's a real wall-clock speedup.

### A Quick Example

You say: *"Add a /analytics endpoint with rate limiting and tests"*

Without Divide and Conquer, Claude does 9 steps one after another.

With Divide and Conquer:

| Wave | What Happens (all at the same time) |
|------|-------------------------------------|
| **Wave 1** | Research API patterns + Research rate limiting + Define data types |
| **Wave 2** | Build the database query + Build the endpoint + Set up rate limiting |
| **Wave 3** | Write unit tests + Write integration tests + Write rate limit tests |
| **Wave 4** | Code review + Security review |

**9 tasks in 4 waves instead of 9 sequential steps.** Roughly 2-3x faster.

## Two Flavors

This skill comes in two formats:

| Format | Where It Works | Best For |
|--------|---------------|----------|
| **Claude Code Skill** | [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) | Daily coding with Claude Code |
| **OpenClaw Skill** | [OpenClaw](https://github.com/openclaw) / API-based agents | Custom agent platforms, API integrations |

You can install one or both. They teach the same strategy, just packaged for different environments.

---

## Installation

### Claude Code Skill

The Claude Code version is a `SKILL.md` file that Claude loads when it detects a task that would benefit from parallel execution.

#### Option 1: Copy the files (recommended)

```bash
# Clone this repo
git clone https://github.com/RuneweaverStudios/divideandconquer.git

# Copy the Claude Code skill to your global skills directory
cp -r divideandconquer/claude-code-skill ~/.claude/skills/divideandconquer
```

That's it. Next time you start Claude Code and give it a complex task, it will automatically use the skill.

#### Option 2: Symlink (stays up to date with the repo)

```bash
git clone https://github.com/RuneweaverStudios/divideandconquer.git ~/tools/divideandconquer

ln -s ~/tools/divideandconquer/claude-code-skill ~/.claude/skills/divideandconquer
```

Now you can `git pull` to get updates.

#### Verify it's installed

Start Claude Code and type:

```
/divideandconquer
```

If it shows up in the skill list, you're good.

#### Optional: Add a global rule to always use it

Create `~/.claude/rules/common/divideandconquer.md`:

```markdown
# Divide and Conquer — Default Execution Strategy

For ANY non-trivial task (3+ steps, multiple files, or independent subtasks),
use the `divideandconquer` skill BEFORE starting implementation.
Parallel is the default. Serial requires justification.
```

This tells Claude to proactively use the skill even when you don't explicitly ask for it.

---

### OpenClaw Skill

The OpenClaw version includes a Python-based DAG engine (`decompose.py`) that handles the graph math — topological sorting, wave computation, critical path analysis, and speedup estimation.

#### Install

```bash
git clone https://github.com/RuneweaverStudios/divideandconquer.git

# Copy the OpenClaw skill to your skills directory
cp -r divideandconquer/openclaw-skill/divideandconquer /path/to/your/openclaw/skills/
```

#### Requirements

- Python 3.10+ (for the `decompose.py` engine)
- No external dependencies — standard library only

#### Standalone Usage (the DAG engine)

You can use `decompose.py` directly to plan parallel execution:

```bash
python scripts/decompose.py --plan '[
  {"id":1, "desc":"Define types",       "deps":[],    "category":"code"},
  {"id":2, "desc":"Research WebSocket",  "deps":[],    "category":"research"},
  {"id":3, "desc":"Build API endpoint",  "deps":[1],   "category":"code"},
  {"id":4, "desc":"Build UI component",  "deps":[1],   "category":"code"},
  {"id":5, "desc":"Wire integration",    "deps":[3,4], "category":"code"},
  {"id":6, "desc":"Write tests",         "deps":[5],   "category":"test"}
]'
```

Output:
```
## Execution Plan

### Wave 1 (parallel, 2 agents) ~~ No dependencies
- [1] Define types
- [2] Research WebSocket [Explore]

### Wave 2 (parallel, 2 agents) ~~ Depends on Wave 1
- [3] Build API endpoint
- [4] Build UI component

### Wave 3 (1 agent) ~~ Depends on Wave 2
- [5] Wire integration

### Wave 4 (1 agent) ~~ Depends on Wave 3
- [6] Write tests

Summary:
- Parallelism: 2 + 2 + 1 + 1 = 6 tasks across 4 waves
- Speedup: ~1.5x
- Critical path length: 4
```

You can also validate a dependency graph for cycles:

```bash
python scripts/decompose.py --validate '[
  {"id":1, "desc":"A", "deps":[2]},
  {"id":2, "desc":"B", "deps":[1]}
]'
# Output: {"valid": false, "error": "Dependency graph contains a cycle"}
```

---

## How It Works Under the Hood

### The 5 Phases

1. **Decompose** — Break the task into atomic subtasks across five dimensions: code, research, tests, config, and docs.

2. **Map Dependencies** — For each subtask, figure out what it genuinely depends on. The skill aggressively challenges false dependencies (e.g., "tests need implementation" — no, test skeletons can be written first).

3. **Plan Waves** — Group independent subtasks into waves. Wave 1 is everything with no dependencies. Wave 2 is everything that only depends on Wave 1. And so on.

4. **Execute** — Launch all tasks in each wave simultaneously using Claude's Agent tool (in Claude Code) or `sessions_spawn` (in OpenClaw). Each wave finishes before the next one starts.

5. **Merge & Verify** — Collect all results, resolve any conflicts, run tests, check code coverage, and do a code review.

### Smart Sizing

Not every task needs the full treatment:

| Task Size | What Happens |
|-----------|-------------|
| **Tiny** (1-2 steps) | Just does it directly. No overhead. |
| **Small** (3-5 steps) | Quick mental split, maybe 2-3 parallel agents. |
| **Medium** (5-10 steps) | Full wave plan shown to you before execution. |
| **Large** (10+ steps) | Full plan with checkpoints between phases. |

### Built-in Safety

- **Worktree isolation** — When two parallel workers might edit the same file, they get their own copy of the code. Changes are merged afterward.
- **Test gate** — Won't call the job done unless tests exist and pass (80%+ coverage target).
- **Code review gate** — Automatically dispatches a review agent on all changed files before presenting results.

---

## File Structure

```
divideandconquer/
├── README.md                          # You're reading it
├── LICENSE                            # MIT
│
├── claude-code-skill/                 # Claude Code format
│   ├── SKILL.md                       # The skill (install this)
│   └── references/
│       └── examples.md                # Worked examples for complex tasks
│
├── openclaw-skill/                    # OpenClaw format
│   └── divideandconquer/
│       ├── _meta.json                 # OpenClaw metadata + tool definitions
│       ├── SKILL.md                   # Documentation
│       ├── config.json                # Routing + execution settings
│       ├── scripts/
│       │   └── decompose.py           # DAG engine (topological sort, waves)
│       └── workflows/                 # Reserved for YAML workflows
│
└── scripts/
    └── decompose.py                   # Standalone copy of the DAG engine
```

## FAQ

**Q: Does this actually make things faster?**
A: Yes. The speedup depends on how much parallelism exists in your task. A task with 9 independent research steps gets close to 9x speedup. A task that's mostly sequential (step 2 needs step 1, step 3 needs step 2...) gets modest improvement, mainly from parallelizing the initial research phase. The skill is honest about this — it shows you the expected speedup before executing.

**Q: What if I don't want it to parallelize?**
A: The skill checks task size first. Trivial tasks (1-2 steps) are executed directly. You can also just tell Claude "do this sequentially" and it will.

**Q: Does this work on Claude.ai (the website)?**
A: The planning and decomposition work everywhere. The parallel *execution* requires Claude Code's Agent tool (subagents). On Claude.ai, the skill still gives you a structured plan, but executes the waves one at a time.

**Q: Will parallel agents conflict with each other?**
A: The skill handles this with git worktrees — parallel agents that might edit the same file work in isolated copies. Changes are merged afterward, one at a time, with build checks between each merge.

---

## License

MIT

---

## Author

[RuneweaverStudios](https://github.com/RuneweaverStudios)
