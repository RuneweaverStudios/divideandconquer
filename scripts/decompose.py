#!/usr/bin/env python3
"""
Divide and Conquer — Task Decomposition Engine

Decomposes a task into atomic subtasks, builds a dependency DAG,
computes parallel execution waves via topological sort, and estimates speedup.

Usage:
    python decompose.py --task "Build a user auth system with OAuth, JWT, and tests"
    python decompose.py --task "..." --output json
    python decompose.py --plan '[ {"id":1,"desc":"...","deps":[]} ]'
    python decompose.py --analyze "..." --max-concurrency 4

This script handles the deterministic graph operations (topological sort,
wave grouping, critical path, speedup calculation). The creative decomposition
of a task into subtasks is done by the LLM using the SKILL.md instructions;
this script validates and optimizes that decomposition.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from typing import Optional


def default_tool_calls_for_weight(weight: int) -> int:
    """Midpoint of each complexity band (for display when tool_calls omitted)."""
    bands = {1: 5, 2: 12, 3: 22, 4: 40}
    return bands.get(weight, max(40, weight * 10))


@dataclass
class Subtask:
    id: int
    description: str
    depends_on: list[int] = field(default_factory=list)
    category: str = "general"  # research, code, test, config, docs
    estimated_weight: int = 1  # relative effort (1=light .. 4+=massive)
    estimated_tool_calls: Optional[int] = None  # optional explicit estimate
    agent_type: str = "general-purpose"

    def __post_init__(self):
        if self.estimated_weight < 1:
            raise ValueError(
                f"Subtask {self.id}: estimated_weight must be >= 1, got {self.estimated_weight}"
            )


def effective_tool_calls(subtask: Subtask) -> int:
    if subtask.estimated_tool_calls is not None:
        return subtask.estimated_tool_calls
    return default_tool_calls_for_weight(subtask.estimated_weight)


@dataclass
class Wave:
    number: int
    subtasks: list[Subtask]
    depends_on_waves: list[int] = field(default_factory=list)
    # When set, partitions subtasks into light vs heavy (same wave; same deps).
    groups: Optional[list[list[Subtask]]] = None

    @property
    def parallelism(self) -> int:
        return len(self.subtasks)

    @property
    def max_weight(self) -> int:
        return max((s.estimated_weight for s in self.subtasks), default=0)

    @property
    def total_weight(self) -> int:
        return sum(s.estimated_weight for s in self.subtasks)

    @property
    def display_groups(self) -> list[list[Subtask]]:
        if self.groups is not None:
            return self.groups
        return [list(self.subtasks)]


def balance_waves(waves: list[Wave]) -> None:
    """
    Group tasks within each wave into light vs heavy when one task is an outlier.

    Outlier rule: max_w >= 3 * average weight of tasks strictly lighter than max_w,
    with more than one task in the wave. Does not change dependency order or wave
    membership — only adds a visual / planning grouping for wall-clock awareness.
    """
    for w in waves:
        if len(w.subtasks) <= 1:
            w.groups = [list(w.subtasks)]
            continue

        weights = [s.estimated_weight for s in w.subtasks]
        max_w = max(weights)
        lighter = [s for s in w.subtasks if s.estimated_weight < max_w]
        heaviest = [s for s in w.subtasks if s.estimated_weight == max_w]

        if not lighter or len(heaviest) == len(w.subtasks):
            w.groups = [list(w.subtasks)]
            continue

        avg_others = sum(s.estimated_weight for s in lighter) / len(lighter)
        if max_w >= 3 * avg_others:
            w.groups = [lighter, heaviest]
        else:
            w.groups = [list(w.subtasks)]


def validate_dag(subtasks: list[Subtask]) -> tuple[bool, Optional[str]]:
    """Validate that the dependency graph is a valid DAG (no cycles)."""
    ids = {s.id for s in subtasks}
    adj = defaultdict(list)
    in_degree = defaultdict(int)

    for s in subtasks:
        for dep in s.depends_on:
            if dep not in ids:
                return False, f"Subtask {s.id} depends on unknown subtask {dep}"
            adj[dep].append(s.id)
            in_degree[s.id] += 1

    # Kahn's algorithm for cycle detection
    queue = deque(sid for sid in ids if in_degree[sid] == 0)
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited != len(ids):
        return False, "Dependency graph contains a cycle"

    return True, None


def compute_waves(
    subtasks: list[Subtask],
    max_concurrency: int = 0,
    balance: bool = True,
) -> WavePlan:
    """
    Compute parallel execution waves from a dependency graph.

    Uses topological sort to group subtasks into waves where all
    dependencies are satisfied by previous waves.
    """
    valid, error = validate_dag(subtasks)
    if not valid:
        raise ValueError(f"Invalid dependency graph: {error}")

    task_map = {s.id: s for s in subtasks}
    ids = set(task_map.keys())
    adj = defaultdict(list)
    in_degree = {sid: 0 for sid in ids}

    for s in subtasks:
        for dep in s.depends_on:
            adj[dep].append(s.id)
            in_degree[s.id] += 1

    # BFS-based wave computation
    waves: list[Wave] = []
    remaining = set(ids)
    completed = set()

    while remaining:
        # Find all subtasks whose dependencies are satisfied
        ready = sorted(
            sid for sid in remaining
            if all(dep in completed for dep in task_map[sid].depends_on)
        )

        if not ready:
            raise ValueError("Deadlock detected — remaining tasks have unsatisfied deps")

        # Apply concurrency limit if set
        if max_concurrency > 0:
            wave_batches = [
                ready[i:i + max_concurrency]
                for i in range(0, len(ready), max_concurrency)
            ]
        else:
            wave_batches = [ready]

        for batch in wave_batches:
            wave_subtasks = [task_map[sid] for sid in batch]

            # Determine which previous waves this wave depends on
            dep_waves = set()
            for sid in batch:
                for dep in task_map[sid].depends_on:
                    for i, w in enumerate(waves):
                        if any(ws.id == dep for ws in w.subtasks):
                            dep_waves.add(i + 1)

            waves.append(Wave(
                number=len(waves) + 1,
                subtasks=wave_subtasks,
                depends_on_waves=sorted(dep_waves),
            ))

            completed.update(batch)
            remaining -= set(batch)

    if balance:
        balance_waves(waves)

    # Compute critical path length (longest chain of dependent weights)
    critical = compute_critical_path(subtasks)

    total = len(subtasks)
    max_par = max((w.parallelism for w in waves), default=0)

    # Weighted speedup: sequential_time / parallel_time
    sequential_time = sum(s.estimated_weight for s in subtasks)
    parallel_time = sum(w.max_weight for w in waves)
    speedup = round(max(sequential_time / parallel_time, 1.0), 2) if parallel_time > 0 else 1.0

    any_grouped = any(
        w.groups is not None and len(w.display_groups) > 1 for w in waves
    )

    return WavePlan(
        waves=waves,
        total_subtasks=total,
        total_waves=len(waves),
        max_parallelism=max_par,
        critical_path_length=critical,
        speedup_estimate=speedup,
        has_complexity_grouping=any_grouped,
    )


@dataclass
class WavePlan:
    waves: list[Wave]
    total_subtasks: int
    total_waves: int
    max_parallelism: int
    critical_path_length: int
    speedup_estimate: float
    has_complexity_grouping: bool = False


def compute_critical_path(subtasks: list[Subtask]) -> int:
    """Compute the critical path length (longest dependency chain)."""
    task_map = {s.id: s for s in subtasks}
    memo: dict[int, int] = {}

    def longest_path(sid: int) -> int:
        if sid in memo:
            return memo[sid]
        s = task_map[sid]
        if not s.depends_on:
            memo[sid] = s.estimated_weight
        else:
            memo[sid] = s.estimated_weight + max(
                longest_path(dep) for dep in s.depends_on
            )
        return memo[sid]

    return max((longest_path(s.id) for s in subtasks), default=0)


def _format_subtask_line(s: Subtask) -> str:
    tc = effective_tool_calls(s)
    agent_note = f" [{s.agent_type}]" if s.agent_type != "general-purpose" else ""
    return (
        f"- [{s.id}] {s.description}{agent_note} "
        f"[weight: {s.estimated_weight}, ~{tc} tool calls]"
    )


def format_wave_plan(plan: WavePlan, fmt: str = "markdown") -> str:
    """Format the wave plan for display."""
    if fmt == "json":
        return json.dumps(asdict(plan), indent=2)

    lines: list[str] = []
    lines.append("## Execution Plan\n")

    for wave in plan.waves:
        dep_note = ""
        if wave.depends_on_waves:
            dep_note = f" ~~ Depends on Wave {', '.join(str(w) for w in wave.depends_on_waves)}"
        else:
            dep_note = " ~~ No dependencies"

        lines.append(
            f"### Wave {wave.number} (parallel, {wave.parallelism} agents){dep_note}"
        )

        groups = wave.display_groups
        if len(groups) > 1:
            max_tc_light = max(
                (effective_tool_calls(s) for s in groups[0]), default=0
            )
            max_tc_heavy = max(
                (effective_tool_calls(s) for s in groups[1]), default=0
            )
            lines.append(
                f"**Light tasks** (finish early; max ~{max_tc_light} tool calls in this group)"
            )
            for s in groups[0]:
                lines.append(_format_subtask_line(s))
            lines.append(
                f"**Heavy outlier(s)** (wall-clock driver; max ~{max_tc_heavy} tool calls)"
            )
            for s in groups[1]:
                lines.append(_format_subtask_line(s))
        else:
            for s in wave.subtasks:
                lines.append(_format_subtask_line(s))

        tw = wave.total_weight
        driver = max((effective_tool_calls(s) for s in wave.subtasks), default=0)
        lines.append(
            f"  *Total wave weight: {tw} | Wall-clock driver (max task): ~{driver} tool calls*"
        )
        lines.append("")

    lines.append("**Summary:**")
    par_parts = " + ".join(str(w.parallelism) for w in plan.waves)
    lines.append(
        f"- Parallelism: {par_parts} = {plan.total_subtasks} tasks across {plan.total_waves} waves"
    )
    lines.append(f"- Sequential equivalent: {plan.total_subtasks} waves")
    lines.append(f"- Speedup: ~{plan.speedup_estimate}x")
    lines.append(f"- Critical path length: {plan.critical_path_length}")
    lines.append(f"- Max concurrency: {plan.max_parallelism} agents")
    if plan.has_complexity_grouping:
        lines.append(
            "- Complexity: at least one wave has **light vs heavy** grouping (outlier rule)"
        )
    else:
        lines.append(
            "- Complexity: no wave triggered light/heavy grouping (use weights to surface imbalance)"
        )

    return "\n".join(lines)


def route_agent(category: str) -> str:
    """Map subtask category to recommended agent type."""
    routing = {
        "research": "Explore",
        "exploration": "Explore",
        "code": "general-purpose",
        "implementation": "general-purpose",
        "test": "general-purpose",
        "config": "general-purpose",
        "docs": "general-purpose",
        "architecture": "everything-claude-code:architect",
        "review": "everything-claude-code:code-reviewer",
        "security": "everything-claude-code:security-reviewer",
        "build": "everything-claude-code:build-error-resolver",
    }
    return routing.get(category, "general-purpose")


def parse_subtasks_json(raw: str) -> list[Subtask]:
    """Parse subtasks from JSON input."""
    data = json.loads(raw)
    subtasks = []
    for item in data:
        weight = item.get("weight", 1)
        tc = item.get("tool_calls")
        if tc is not None:
            tc = int(tc)
        subtasks.append(Subtask(
            id=item["id"],
            description=item.get("description", item.get("desc", "")),
            depends_on=item.get("depends_on", item.get("deps", [])),
            category=item.get("category", "general"),
            estimated_weight=weight,
            estimated_tool_calls=tc,
            agent_type=route_agent(item.get("category", "general")),
        ))
    return subtasks


def main():
    parser = argparse.ArgumentParser(
        description="Divide and Conquer — Task Decomposition Engine"
    )
    parser.add_argument(
        "--plan",
        type=str,
        help="JSON array of subtasks to compute waves for",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="markdown",
        choices=["markdown", "json", "text"],
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=0,
        help="Max parallel agents per wave (0=unlimited)",
    )
    parser.add_argument(
        "--no-balance",
        action="store_true",
        help="Skip complexity grouping (light vs heavy) within waves",
    )
    parser.add_argument(
        "--validate",
        type=str,
        help="JSON array of subtasks to validate (check for cycles, missing deps)",
    )

    args = parser.parse_args()

    if args.validate:
        subtasks = parse_subtasks_json(args.validate)
        valid, error = validate_dag(subtasks)
        if valid:
            print(json.dumps({"valid": True, "subtasks": len(subtasks)}))
        else:
            print(json.dumps({"valid": False, "error": error}))
        sys.exit(0 if valid else 1)

    if args.plan:
        subtasks = parse_subtasks_json(args.plan)
        plan = compute_waves(
            subtasks,
            max_concurrency=args.max_concurrency,
            balance=not args.no_balance,
        )
        print(format_wave_plan(plan, fmt=args.output))
    else:
        parser.print_help()
        print("\nExample:")
        print('  python decompose.py --plan \'[')
        print('    {"id":1,"desc":"Define types","deps":[],"category":"code","weight":1},')
        print('    {"id":2,"desc":"Research WebSocket libs","deps":[],"category":"research","weight":2},')
        print('    {"id":3,"desc":"Build API endpoint","deps":[1],"category":"code","weight":2},')
        print('    {"id":4,"desc":"Build UI component","deps":[1],"category":"code","weight":2},')
        print('    {"id":5,"desc":"Wire integration","deps":[3,4],"category":"code","weight":3},')
        print('    {"id":6,"desc":"Write tests","deps":[5],"category":"test","weight":2}')
        print("  ]'")


if __name__ == "__main__":
    main()
