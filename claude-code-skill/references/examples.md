# Worked Examples

Complete walk-throughs showing how divideandconquer decomposes, maps, plans, and executes real tasks. Read this file when you need detailed guidance on applying the skill to a specific task type.

**Complexity-aware planning**: Every subtask below uses **`[w:N, ~T]`** = weight band and approximate tool calls. Massive work must be **subdivided** (Phase 1.5) before agents run. After waves are computed, apply **Phase 3.5** (balance): call out waves where one task is an outlier, or run `scripts/decompose.py` with `weight` / `tool_calls` in JSON to get **light vs heavy** grouping in the execution plan.

---

## Example 1: Full-Stack Feature — Team Chat System

**User prompt**: "Add a team chat feature to our app. Need a messages table, WebSocket server, REST API for message history, a ChatWindow React component, message notifications, and tests."

### Phase 1: Decompose

```
1. Define TypeScript types for Message, ChatRoom, ChatEvent     [w:1, ~5]
2. Create messages + chat_rooms DB migration                     [w:2, ~12]
3. Research WebSocket setup for our stack (e.g., Socket.IO vs ws) [w:2, ~14]
4. Implement GET /api/messages?roomId=X endpoint                 [w:2, ~12]
5. Implement POST /api/messages endpoint                         [w:2, ~12]
6. Set up WebSocket server with room join/leave/broadcast        [w:3, ~24]  ← wall-clock driver in Wave 2; subdivide if >30 tool calls
7. Build ChatWindow component with message list + input          [w:2, ~14]
8. Build ChatNotification component (unread badge)               [w:1, ~8]
9. Wire WebSocket client in React (useChat hook)               [w:2, ~14]
10. Unit tests for API endpoints                                 [w:2, ~12]
11. Unit tests for WebSocket events                             [w:2, ~12]
12. Integration test for send-and-receive flow                   [w:2, ~16]
13. Code review pass                                             [w:2, ~10]
```

### Phase 2: Map Dependencies

```
1  → []           # Types can be defined from requirements alone
2  → []           # Schema design is independent
3  → []           # Research is always a root
4  → [1, 2]       # Needs types + table
5  → [1, 2]       # Needs types + table
6  → [1, 3]       # Needs types + WS research findings
7  → [1]          # Needs types for props, but can use mock data for messages
8  → [1]          # Needs types for notification shape
9  → [6, 7]       # Needs WS server + component to connect
10 → [4, 5]       # Needs endpoints to exist
11 → [6]          # Needs WS server
12 → [9]          # Needs full client-server wiring
13 → [10, 11, 12] # Review after all tests pass
```

### Phase 3: Plan Execution Waves

```
Wave 1 (parallel, 3 agents) — balanced; similar weights
  [1] Define TypeScript types (Message, ChatRoom, ChatEvent)     [w:1]
  [2] Create DB migration (messages + chat_rooms tables)       [w:2]
  [3] Research WebSocket library choice for our stack          [w:2]

Wave 2 (parallel, 5 agents) — **imbalance**: [6] is heavier than [4],[5],[7],[8]
  Light: [4] GET /api/messages [w:2] | [5] POST /api/messages [w:2] | [7] ChatWindow [w:2] | [8] ChatNotification [w:1]
  Heavy driver: [6] WebSocket server [w:3] — dominates wall-clock for this wave; consider splitting [6] into server setup vs room logic if it grows past ~30 tool calls
  (deps unchanged: 4,5 need 1,2; 6 needs 1,3; 7,8 need 1)

Wave 3 (parallel, 3 agents):
  [9]  useChat hook — wire WS client to ChatWindow (needs: 6, 7)  [w:2]
  [10] Unit tests for API endpoints (needs: 4, 5)                 [w:2]
  [11] Unit tests for WebSocket events (needs: 6)                 [w:2]

Wave 4 (parallel, 1 agent):
  [12] Integration test: send-and-receive (needs: 9)                [w:2]

Wave 5 (parallel, 1 agent):
  [13] Code review (needs: 10, 11, 12)                             [w:2]

Parallelism: 3 + 5 + 3 + 1 + 1 = 13 tasks across 5 waves
Sequential equivalent: 13 waves
Speedup: ~2.6x (honest wall-clock for Wave 2 ≈ max agent time, usually task [6])
```

### Phase 4: Execute

**Wave 1** — single message, 3 Agent calls:
```
Agent 1 (general-purpose): "Define TypeScript interfaces in src/types/chat.ts:
  - Message { id, roomId, senderId, content, createdAt }
  - ChatRoom { id, name, memberIds, createdAt }
  - ChatEvent { type: 'join'|'leave'|'message', payload, timestamp }"

Agent 2 (general-purpose): "Create Prisma migration for:
  - chat_rooms table (id uuid PK, name text, created_at timestamptz)
  - messages table (id uuid PK, room_id FK→chat_rooms, sender_id FK→users,
    content text, created_at timestamptz, indexes on room_id+created_at)"

Agent 3 (Explore): "Research WebSocket libraries compatible with Next.js App Router.
  Compare Socket.IO vs ws vs Party Kit. Check which works with our deployment target.
  Return: recommended library, setup steps, gotchas."
```

**Wave 2** — after Wave 1 completes, single message, 5 Agent calls:
```
Agent 4 (general-purpose): "Implement GET /api/messages route..."
Agent 5 (general-purpose): "Implement POST /api/messages route..."
Agent 6 (general-purpose): "Set up WebSocket server using [Wave 1 recommendation]..."
Agent 7 (general-purpose): "Build ChatWindow React component with mock message data..."
Agent 8 (general-purpose): "Build ChatNotification badge component..."
```

And so on through Waves 3-5.

### Phase 5: Merge

- Verify all files compile: `npm run build`
- Run test suite: `npm test`
- Check that useChat hook correctly imports from both the WS module and ChatWindow
- Present summary: "Chat feature complete — 13 tasks across 5 waves, 5 agents max concurrency"

---

## Example 2: Bug Hunt — Intermittent Payment Failures

**User prompt**: "Stripe webhook handler is failing ~5% of the time. Customers get charged but their subscription status doesn't update. Fix it."

### Phase 1: Decompose

```
1. Search codebase for webhook handler implementation           [w:2, ~10]
2. Search error logs / Stripe dashboard for failure patterns      [w:2, ~12]
3. Check recent git changes to payment-related files             [w:2, ~10]
4. Read Stripe docs on webhook retry behavior and idempotency  [w:2, ~12]
5. Analyze the webhook handler code for race conditions          [w:2, ~14]
6. Check database transaction isolation level on subscription updates [w:2, ~12]
7. Implement fix (based on findings)                             [w:3, ~22]  ← single serial bottleneck after research; subdivide if fix is huge
8. Write regression test simulating concurrent webhook deliveries [w:2, ~14]
9. Security review of payment code changes                       [w:2, ~12]
```

### Phase 2: Map Dependencies

```
1 → []        # Root — just codebase search
2 → []        # Root — log/dashboard search
3 → []        # Root — git history search
4 → []        # Root — documentation lookup
5 → [1]       # Need to find the handler first
6 → [1]       # Need to find the DB calls
7 → [5, 6, 2, 4]  # Need all analysis + research
8 → [7]       # Need the fix to test against
9 → [7]       # Need the code changes to review
```

### Phase 3: Plan Execution Waves

```
Wave 1 (parallel, 4 agents):     Research blitz
  [1] Find webhook handler code
  [2] Search logs for error patterns
  [3] Check recent git changes to payment files
  [4] Stripe docs on webhook idempotency

Wave 2 (parallel, 2 agents):     Deep analysis
  [5] Analyze handler for race conditions (needs: 1)
  [6] Check DB transaction isolation (needs: 1)

Wave 3 (1 agent):                 Fix
  [7] Implement fix (needs: 2, 4, 5, 6)

Wave 4 (parallel, 2 agents):     Verify
  [8] Regression test (needs: 7)
  [9] Security review (needs: 7)

Parallelism: 4 + 2 + 1 + 2 = 9 tasks in 4 waves
Sequential: 9 waves
Speedup: ~2.25x
```

Key insight: the **research blitz** in Wave 1 is where most parallelism lives in bug investigations. Don't start debugging sequentially — cast a wide net simultaneously.

---

## Example 3: Greenfield Project — CLI Tool in Go

**User prompt**: "Build a CLI tool in Go that takes a CSV of customer emails, validates them against our API, and outputs a report. Needs flags for --input, --output, --format (json/csv), --concurrent (worker count), and --dry-run."

### Phase 1: Decompose

```
1. Research: Go CSV parsing best practices + cobra/urfave CLI libs
2. Research: Go concurrency patterns for worker pools
3. Define types: Config, Customer, ValidationResult, Report
4. Scaffold CLI with cobra: root command, flags, help text
5. Implement CSV reader (streaming, not load-all)
6. Implement email validation worker pool
7. Implement API client for validation endpoint
8. Implement report writer (JSON + CSV formatters)
9. Implement --dry-run mode (validate without API calls)
10. Table-driven unit tests for CSV reader
11. Table-driven unit tests for report writer
12. Integration test: full pipeline with mock API
13. Build verification: go build, go vet, golangci-lint
```

### Phase 2: Map Dependencies

```
1  → []          2  → []          3  → []
4  → [1]         # CLI framework from research
5  → [3]         # Needs types
6  → [2, 3, 7]   # Needs concurrency patterns + types + API client
7  → [3]         # Needs types
8  → [3]         # Needs types
9  → [6]         # Wraps worker pool with no-op API
10 → [5]         # Tests for CSV reader
11 → [8]         # Tests for report writer
12 → [6, 8]      # Needs worker pool + report writer
13 → [12]        # After all code + tests exist
```

### Phase 3: Plan Execution Waves

```
Wave 1 (3 agents):
  [1] Research CLI libs    [2] Research worker pools    [3] Define types

Wave 2 (4 agents):
  [4] Scaffold CLI (needs: 1)
  [5] CSV reader (needs: 3)
  [7] API client (needs: 3)
  [8] Report writer (needs: 3)

Wave 3 (3 agents):
  [6]  Worker pool (needs: 2, 3, 7)
  [10] CSV reader tests (needs: 5)
  [11] Report writer tests (needs: 8)

Wave 4 (1 agent):
  [9] Dry-run mode (needs: 6)

Wave 5 (1 agent):
  [12] Integration test (needs: 6, 8)

Wave 6 (1 agent):
  [13] Build + lint verification (needs: 12)

Parallelism: 3 + 4 + 3 + 1 + 1 + 1 = 13 tasks in 6 waves
Sequential: 13 waves
Speedup: ~2.2x
```

Note: Waves 4-6 are thin because the dependency chain narrows. This is normal — most task DAGs are wide at the top (research + independent foundations) and narrow at the bottom (integration + verification).

---

## Example 4: Refactoring — Monolith to Modules

**User prompt**: "Split our 900-line api-handler.ts into separate route modules. Currently handles /users, /products, /orders, and /admin. Each should be its own file with its own tests. Don't break the 23 existing integration tests."

### Phase 1: Decompose

```
1. Read and analyze api-handler.ts — map which functions serve which routes
2. Identify all imports and shared utilities used across routes
3. Run existing test suite to establish green baseline
4. Extract shared utilities into api-utils.ts
5. Extract /users routes → users.handler.ts
6. Extract /products routes → products.handler.ts
7. Extract /orders routes → orders.handler.ts
8. Extract /admin routes → admin.handler.ts
9. Update main router to import from new modules
10. Run full test suite — all 23 must pass
11. Write new unit tests for each handler module
12. Code review
```

### Phase 2: Map Dependencies

```
1 → []     2 → []     3 → []
4 → [1, 2]       # Need to know what's shared
5 → [4]           # Need shared utils extracted first
6 → [4]           # Same
7 → [4]           # Same
8 → [4]           # Same
9 → [5, 6, 7, 8] # Need all handlers extracted
10 → [9]          # Need router updated
11 → [5, 6, 7, 8] # Can test individual handlers
12 → [10, 11]     # After everything passes
```

### Phase 3: Plan Execution Waves

```
Wave 1 (3 agents):
  [1] Analyze api-handler.ts route map
  [2] Identify shared utilities + imports
  [3] Run test suite for green baseline

Wave 2 (1 agent):
  [4] Extract shared utils → api-utils.ts (needs: 1, 2)

Wave 3 (4 agents, USE WORKTREES):        ← Key parallelism
  [5] Extract /users handler (needs: 4)
  [6] Extract /products handler (needs: 4)
  [7] Extract /orders handler (needs: 4)
  [8] Extract /admin handler (needs: 4)

Wave 4 (2 agents):
  [9]  Update router imports (needs: 5-8) — merge worktrees first
  [11] Unit tests per handler (needs: 5-8)

Wave 5 (1 agent):
  [10] Full test suite verification (needs: 9)

Wave 6 (1 agent):
  [12] Code review (needs: 10, 11)

Parallelism: 3 + 1 + 4 + 2 + 1 + 1 = 12 tasks in 6 waves
```

**Critical**: Wave 3 MUST use `isolation: "worktree"` for agents 5-8. They all read from the same source file and write to new files, but the extraction process modifies the original file (removing code). Without worktrees, they'd conflict. After Wave 3, merge the worktrees sequentially before Wave 4.

---

## Example 5: Trivial Task — Handled Correctly

**User prompt**: "Fix the typo in the README — it says 'dependancies' instead of 'dependencies'"

### Correct behavior

```
This is a single-step task. No decomposition needed.
→ Execute directly: Edit README.md, fix the typo.
```

The skill's minimum viable parallelism table says: **Trivial (1-2 steps) → Just do it directly.** Launching agents for a typo fix would waste time and tokens.

---

## Example 6: Mostly Serial — Finding Hidden Parallelism

**User prompt**: "Our Kubernetes pod keeps crash-looping. Check the logs, find the error, fix it, rebuild the Docker image, push to registry, and redeploy."

### Decompose

```
1. Get pod logs (kubectl logs)
2. Get pod describe (kubectl describe pod)
3. Get recent deployment events
4. Check Dockerfile for issues
5. Diagnose root cause (from findings)
6. Fix the code/config
7. Rebuild Docker image
8. Push to registry
9. Redeploy
```

### Dependency Map

```
1 → []     2 → []     3 → []     4 → []     # All reading is independent
5 → [1, 2, 3, 4]    # Diagnosis needs all data
6 → [5]              # Fix needs diagnosis
7 → [6]              # Build needs fix
8 → [7]              # Push needs build
9 → [8]              # Deploy needs push
```

### Execution

```
Wave 1 (4 agents):   [1] [2] [3] [4]     ← Good parallelism here
Wave 2 (1 agent):    [5] Diagnose
Wave 3 (1 agent):    [6] Fix
Wave 4 (serial):     [7] → [8] → [9]     ← Unavoidably serial

Honest assessment: 4x parallelism in Wave 1, then serial.
Total: 9 tasks in 4-6 waves depending on whether build/push/deploy
       are batched into one agent.
Speedup: ~1.5x (modest, but the research phase still benefits)
```

The skill should be transparent: "The fix-build-push-deploy chain is inherently serial, but I parallelized the initial investigation to gather all diagnostic data simultaneously."
