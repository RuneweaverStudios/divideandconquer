"""
Comprehensive tests for the DAG decomposition engine (decompose.py).

Covers:
  - validate_dag: valid DAGs, cycle detection, unknown dependency detection
  - compute_waves: linear chains, fully parallel, diamond patterns, max_concurrency
  - compute_critical_path: various graph shapes
  - format_wave_plan: markdown and JSON output
  - route_agent: known categories and unknown fallback
  - parse_subtasks_json: valid input, desc/deps aliases, weight / tool_calls mapping
  - balance_waves: light vs heavy grouping when outlier rule applies
  - Subtask dataclass: weight validation
  - Edge cases: single task, empty deps, self-dependency, empty input
"""

import json
import subprocess
import sys
import pytest

from decompose import (
    Subtask,
    Wave,
    WavePlan,
    balance_waves,
    compute_critical_path,
    compute_waves,
    format_wave_plan,
    parse_subtasks_json,
    route_agent,
    validate_dag,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _st(id: int, deps: list[int] | None = None, weight: int = 1,
        category: str = "general", desc: str = "") -> Subtask:
    """Shorthand factory for Subtask."""
    return Subtask(
        id=id,
        description=desc or f"task-{id}",
        depends_on=deps if deps is not None else [],
        category=category,
        estimated_weight=weight,
    )


# ===================================================================
# 1. validate_dag
# ===================================================================

class TestValidateDag:
    """Tests for validate_dag()."""

    def test_valid_linear_chain(self):
        tasks = [_st(1), _st(2, [1]), _st(3, [2])]
        valid, err = validate_dag(tasks)
        assert valid is True
        assert err is None

    def test_valid_diamond(self):
        tasks = [_st(1), _st(2, [1]), _st(3, [1]), _st(4, [2, 3])]
        valid, err = validate_dag(tasks)
        assert valid is True
        assert err is None

    def test_valid_fully_parallel(self):
        tasks = [_st(1), _st(2), _st(3)]
        valid, err = validate_dag(tasks)
        assert valid is True
        assert err is None

    def test_valid_single_task(self):
        tasks = [_st(1)]
        valid, err = validate_dag(tasks)
        assert valid is True
        assert err is None

    def test_cycle_two_nodes(self):
        tasks = [_st(1, [2]), _st(2, [1])]
        valid, err = validate_dag(tasks)
        assert valid is False
        assert err is not None
        assert "cycle" in err.lower()

    def test_cycle_three_nodes(self):
        tasks = [_st(1, [3]), _st(2, [1]), _st(3, [2])]
        valid, err = validate_dag(tasks)
        assert valid is False
        assert "cycle" in err.lower()

    def test_self_dependency(self):
        tasks = [_st(1, [1])]
        valid, err = validate_dag(tasks)
        assert valid is False
        # Self-dep creates a cycle
        assert "cycle" in err.lower()

    def test_unknown_dependency(self):
        tasks = [_st(1), _st(2, [99])]
        valid, err = validate_dag(tasks)
        assert valid is False
        assert "unknown" in err.lower()
        assert "99" in err

    def test_empty_task_list(self):
        valid, err = validate_dag([])
        assert valid is True
        assert err is None

    def test_multiple_roots_valid(self):
        tasks = [_st(1), _st(2), _st(3, [1, 2])]
        valid, err = validate_dag(tasks)
        assert valid is True


# ===================================================================
# 2. compute_waves
# ===================================================================

class TestComputeWaves:
    """Tests for compute_waves()."""

    def test_linear_chain_produces_sequential_waves(self):
        tasks = [_st(1), _st(2, [1]), _st(3, [2])]
        plan = compute_waves(tasks)
        assert plan.total_waves == 3
        assert plan.total_subtasks == 3
        # Each wave has exactly 1 task
        for w in plan.waves:
            assert w.parallelism == 1

    def test_fully_parallel(self):
        tasks = [_st(1), _st(2), _st(3), _st(4)]
        plan = compute_waves(tasks)
        assert plan.total_waves == 1
        assert plan.max_parallelism == 4
        assert plan.waves[0].parallelism == 4

    def test_diamond_pattern(self):
        # 1 -> 2, 1 -> 3, 2&3 -> 4
        tasks = [_st(1), _st(2, [1]), _st(3, [1]), _st(4, [2, 3])]
        plan = compute_waves(tasks)
        assert plan.total_waves == 3
        # Wave 1: [1], Wave 2: [2,3], Wave 3: [4]
        assert plan.waves[0].parallelism == 1
        assert plan.waves[1].parallelism == 2
        assert plan.waves[2].parallelism == 1

    def test_max_concurrency_splits_waves(self):
        # 4 independent tasks with max_concurrency=2
        tasks = [_st(1), _st(2), _st(3), _st(4)]
        plan = compute_waves(tasks, max_concurrency=2)
        # Should split into 2 waves of 2 instead of 1 wave of 4
        assert plan.total_waves == 2
        assert plan.max_parallelism == 2
        for w in plan.waves:
            assert w.parallelism <= 2

    def test_max_concurrency_one_forces_sequential(self):
        tasks = [_st(1), _st(2), _st(3)]
        plan = compute_waves(tasks, max_concurrency=1)
        assert plan.total_waves == 3
        for w in plan.waves:
            assert w.parallelism == 1

    def test_max_concurrency_zero_means_unlimited(self):
        tasks = [_st(1), _st(2), _st(3)]
        plan = compute_waves(tasks, max_concurrency=0)
        assert plan.total_waves == 1
        assert plan.max_parallelism == 3

    def test_invalid_dag_raises_value_error(self):
        tasks = [_st(1, [2]), _st(2, [1])]
        with pytest.raises(ValueError, match="Invalid dependency graph"):
            compute_waves(tasks)

    def test_single_task(self):
        tasks = [_st(1)]
        plan = compute_waves(tasks)
        assert plan.total_waves == 1
        assert plan.total_subtasks == 1
        assert plan.max_parallelism == 1

    def test_wave_depends_on_waves_populated(self):
        # 1 -> 2 -> 3
        tasks = [_st(1), _st(2, [1]), _st(3, [2])]
        plan = compute_waves(tasks)
        assert plan.waves[0].depends_on_waves == []
        assert plan.waves[1].depends_on_waves == [1]
        assert plan.waves[2].depends_on_waves == [2]

    def test_speedup_estimate_for_parallel_tasks(self):
        tasks = [_st(1), _st(2), _st(3)]
        plan = compute_waves(tasks)
        # Sequential = 3, Parallel = 1 wave with max_weight=1 → speedup = 3.0
        assert plan.speedup_estimate == 3.0

    def test_speedup_estimate_for_linear_chain(self):
        tasks = [_st(1), _st(2, [1]), _st(3, [2])]
        plan = compute_waves(tasks)
        # Sequential = 3, Parallel = 3 waves each weight 1 → speedup = 1.0
        assert plan.speedup_estimate == 1.0

    def test_speedup_with_weighted_tasks(self):
        # Two parallel tasks: weight 3 and weight 1
        tasks = [_st(1, weight=3), _st(2, weight=1)]
        plan = compute_waves(tasks)
        # Sequential = 4, Parallel = max(3,1) = 3, speedup = 4/3 ≈ 1.33
        assert plan.speedup_estimate == 1.33

    def test_balance_groups_heavy_outlier_in_parallel_wave(self):
        tasks = [_st(1, weight=1), _st(2, weight=1), _st(3, weight=4)]
        plan = compute_waves(tasks)
        assert plan.has_complexity_grouping is True
        md = format_wave_plan(plan)
        assert "Light tasks" in md
        assert "Heavy outlier" in md

    def test_balance_disabled_skips_grouping(self):
        tasks = [_st(1, weight=1), _st(2, weight=1), _st(3, weight=4)]
        plan = compute_waves(tasks, balance=False)
        assert plan.has_complexity_grouping is False

    def test_wide_then_narrow_topology(self):
        # 1,2,3,4 all independent, then 5 depends on all
        tasks = [_st(1), _st(2), _st(3), _st(4), _st(5, [1, 2, 3, 4])]
        plan = compute_waves(tasks)
        assert plan.total_waves == 2
        assert plan.waves[0].parallelism == 4
        assert plan.waves[1].parallelism == 1


# ===================================================================
# 3. compute_critical_path
# ===================================================================

class TestComputeCriticalPath:
    """Tests for compute_critical_path()."""

    def test_single_task(self):
        assert compute_critical_path([_st(1, weight=5)]) == 5

    def test_linear_chain(self):
        tasks = [_st(1, weight=2), _st(2, [1], weight=3), _st(3, [2], weight=1)]
        assert compute_critical_path(tasks) == 6  # 2+3+1

    def test_fully_parallel(self):
        tasks = [_st(1, weight=1), _st(2, weight=5), _st(3, weight=3)]
        # No deps, so critical path = max individual weight
        assert compute_critical_path(tasks) == 5

    def test_diamond_takes_heavier_branch(self):
        # 1 -> 2 (weight 3), 1 -> 3 (weight 1), both -> 4
        tasks = [
            _st(1, weight=1),
            _st(2, [1], weight=3),
            _st(3, [1], weight=1),
            _st(4, [2, 3], weight=1),
        ]
        # Longest: 1(1) + 2(3) + 4(1) = 5
        assert compute_critical_path(tasks) == 5

    def test_empty_list(self):
        assert compute_critical_path([]) == 0

    def test_all_weight_one_chain(self):
        tasks = [_st(i, [i - 1] if i > 1 else []) for i in range(1, 6)]
        assert compute_critical_path(tasks) == 5


# ===================================================================
# 4. format_wave_plan
# ===================================================================

class TestFormatWavePlan:
    """Tests for format_wave_plan()."""

    @pytest.fixture
    def simple_plan(self) -> WavePlan:
        return compute_waves([_st(1), _st(2, [1])])

    def test_markdown_output_contains_headers(self, simple_plan):
        md = format_wave_plan(simple_plan, fmt="markdown")
        assert "## Execution Plan" in md
        assert "### Wave 1" in md
        assert "### Wave 2" in md

    def test_markdown_contains_summary(self, simple_plan):
        md = format_wave_plan(simple_plan, fmt="markdown")
        assert "**Summary:**" in md
        assert "Speedup:" in md
        assert "Critical path length:" in md

    def test_markdown_shows_agent_type_when_not_default(self):
        s = Subtask(id=1, description="review code", agent_type="code-reviewer")
        plan = WavePlan(
            waves=[Wave(number=1, subtasks=[s])],
            total_subtasks=1,
            total_waves=1,
            max_parallelism=1,
            critical_path_length=1,
            speedup_estimate=1.0,
            has_complexity_grouping=False,
        )
        md = format_wave_plan(plan, fmt="markdown")
        assert "[code-reviewer]" in md

    def test_markdown_hides_agent_type_when_default(self, simple_plan):
        md = format_wave_plan(simple_plan, fmt="markdown")
        assert "[general-purpose]" not in md

    def test_json_output_is_valid_json(self, simple_plan):
        output = format_wave_plan(simple_plan, fmt="json")
        parsed = json.loads(output)
        assert parsed["total_subtasks"] == 2
        assert parsed["total_waves"] == 2
        assert "waves" in parsed

    def test_json_output_contains_all_fields(self, simple_plan):
        parsed = json.loads(format_wave_plan(simple_plan, fmt="json"))
        expected_keys = {
            "waves", "total_subtasks", "total_waves",
            "max_parallelism", "critical_path_length", "speedup_estimate",
            "has_complexity_grouping",
        }
        assert expected_keys == set(parsed.keys())

    def test_markdown_no_dependencies_note(self):
        plan = compute_waves([_st(1)])
        md = format_wave_plan(plan, fmt="markdown")
        assert "No dependencies" in md

    def test_markdown_depends_on_note(self):
        plan = compute_waves([_st(1), _st(2, [1])])
        md = format_wave_plan(plan, fmt="markdown")
        assert "Depends on Wave 1" in md

    def test_default_format_is_markdown(self, simple_plan):
        default_output = format_wave_plan(simple_plan)
        markdown_output = format_wave_plan(simple_plan, fmt="markdown")
        assert default_output == markdown_output


# ===================================================================
# 5. route_agent
# ===================================================================

class TestRouteAgent:
    """Tests for route_agent()."""

    @pytest.mark.parametrize("category,expected", [
        ("research", "Explore"),
        ("exploration", "Explore"),
        ("code", "general-purpose"),
        ("implementation", "general-purpose"),
        ("test", "general-purpose"),
        ("config", "general-purpose"),
        ("docs", "general-purpose"),
        ("architecture", "everything-claude-code:architect"),
        ("review", "everything-claude-code:code-reviewer"),
        ("security", "everything-claude-code:security-reviewer"),
        ("build", "everything-claude-code:build-error-resolver"),
    ])
    def test_known_categories(self, category, expected):
        assert route_agent(category) == expected

    def test_unknown_category_returns_general_purpose(self):
        assert route_agent("totally-made-up") == "general-purpose"

    def test_empty_string_returns_general_purpose(self):
        assert route_agent("") == "general-purpose"


# ===================================================================
# 6. parse_subtasks_json
# ===================================================================

class TestParseSubtasksJson:
    """Tests for parse_subtasks_json()."""

    def test_basic_valid_input(self):
        raw = json.dumps([
            {"id": 1, "description": "First task", "depends_on": [], "category": "code"},
            {"id": 2, "description": "Second task", "depends_on": [1]},
        ])
        tasks = parse_subtasks_json(raw)
        assert len(tasks) == 2
        assert tasks[0].id == 1
        assert tasks[0].description == "First task"
        assert tasks[0].depends_on == []
        assert tasks[1].depends_on == [1]

    def test_desc_alias(self):
        raw = json.dumps([{"id": 1, "desc": "Alias description"}])
        tasks = parse_subtasks_json(raw)
        assert tasks[0].description == "Alias description"

    def test_deps_alias(self):
        raw = json.dumps([
            {"id": 1, "desc": "Root"},
            {"id": 2, "desc": "Child", "deps": [1]},
        ])
        tasks = parse_subtasks_json(raw)
        assert tasks[1].depends_on == [1]

    def test_weight_mapping(self):
        raw = json.dumps([{"id": 1, "desc": "Heavy", "weight": 3}])
        tasks = parse_subtasks_json(raw)
        assert tasks[0].estimated_weight == 3

    def test_tool_calls_mapping(self):
        raw = json.dumps([{"id": 1, "desc": "Explicit", "weight": 2, "tool_calls": 42}])
        tasks = parse_subtasks_json(raw)
        assert tasks[0].estimated_tool_calls == 42

    def test_default_weight_is_one(self):
        raw = json.dumps([{"id": 1, "desc": "Light"}])
        tasks = parse_subtasks_json(raw)
        assert tasks[0].estimated_weight == 1

    def test_category_routes_agent(self):
        raw = json.dumps([{"id": 1, "desc": "Research", "category": "research"}])
        tasks = parse_subtasks_json(raw)
        assert tasks[0].agent_type == "Explore"

    def test_default_category_is_general(self):
        raw = json.dumps([{"id": 1, "desc": "No category"}])
        tasks = parse_subtasks_json(raw)
        assert tasks[0].category == "general"

    def test_description_prefers_description_over_desc(self):
        raw = json.dumps([
            {"id": 1, "description": "Full name", "desc": "Alias"},
        ])
        tasks = parse_subtasks_json(raw)
        assert tasks[0].description == "Full name"

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_subtasks_json("not valid json")

    def test_empty_list(self):
        tasks = parse_subtasks_json("[]")
        assert tasks == []


# ===================================================================
# 7. Subtask dataclass — weight validation
# ===================================================================

class TestSubtaskValidation:
    """Tests for Subtask.__post_init__ weight validation."""

    def test_weight_one_is_valid(self):
        s = Subtask(id=1, description="ok", estimated_weight=1)
        assert s.estimated_weight == 1

    def test_weight_zero_raises(self):
        with pytest.raises(ValueError, match="estimated_weight must be >= 1"):
            Subtask(id=1, description="bad", estimated_weight=0)

    def test_negative_weight_raises(self):
        with pytest.raises(ValueError, match="estimated_weight must be >= 1"):
            Subtask(id=1, description="bad", estimated_weight=-5)

    def test_large_weight_is_valid(self):
        s = Subtask(id=1, description="heavy", estimated_weight=100)
        assert s.estimated_weight == 100


# ===================================================================
# 8. Wave dataclass properties
# ===================================================================

class TestBalanceWaves:
    """Tests for balance_waves()."""

    def test_outlier_splits_into_two_groups(self):
        wave = Wave(
            number=1,
            subtasks=[_st(1, weight=1), _st(2, weight=1), _st(3, weight=4)],
        )
        balance_waves([wave])
        assert len(wave.display_groups) == 2
        assert {s.id for s in wave.display_groups[0]} == {1, 2}
        assert {s.id for s in wave.display_groups[1]} == {3}

    def test_uniform_weights_single_group(self):
        wave = Wave(number=1, subtasks=[_st(1, weight=2), _st(2, weight=2)])
        balance_waves([wave])
        assert len(wave.display_groups) == 1


class TestWaveProperties:
    """Tests for Wave.parallelism and Wave.max_weight."""

    def test_parallelism(self):
        wave = Wave(number=1, subtasks=[_st(1), _st(2), _st(3)])
        assert wave.parallelism == 3

    def test_max_weight(self):
        wave = Wave(number=1, subtasks=[
            _st(1, weight=1), _st(2, weight=5), _st(3, weight=3)
        ])
        assert wave.max_weight == 5

    def test_max_weight_empty_subtasks(self):
        wave = Wave(number=1, subtasks=[])
        assert wave.max_weight == 0

    def test_parallelism_single(self):
        wave = Wave(number=1, subtasks=[_st(1)])
        assert wave.parallelism == 1


# ===================================================================
# 9. Edge cases and integration
# ===================================================================

class TestEdgeCases:
    """Edge cases and integration tests."""

    def test_self_dependency_rejected_by_compute_waves(self):
        with pytest.raises(ValueError):
            compute_waves([_st(1, [1])])

    def test_unknown_dep_rejected_by_compute_waves(self):
        with pytest.raises(ValueError, match="unknown subtask"):
            compute_waves([_st(1), _st(2, [99])])

    def test_large_parallel_graph(self):
        """100 independent tasks should form a single wave."""
        tasks = [_st(i) for i in range(1, 101)]
        plan = compute_waves(tasks)
        assert plan.total_waves == 1
        assert plan.max_parallelism == 100

    def test_long_chain(self):
        """20-step chain should produce 20 waves."""
        tasks = [_st(i, [i - 1] if i > 1 else []) for i in range(1, 21)]
        plan = compute_waves(tasks)
        assert plan.total_waves == 20

    def test_speedup_floored_at_one(self):
        """Speedup should never be less than 1.0, even with concurrency limits."""
        tasks = [_st(1), _st(2), _st(3)]
        plan = compute_waves(tasks, max_concurrency=1)
        assert plan.speedup_estimate >= 1.0

    def test_complex_dag(self):
        """
        Topology:
          1 ─┬─ 2 ──┐
              └─ 3 ──┤
          4 ─────────┴─ 5 ─── 6
        """
        tasks = [
            _st(1),
            _st(2, [1]),
            _st(3, [1]),
            _st(4),
            _st(5, [2, 3, 4]),
            _st(6, [5]),
        ]
        plan = compute_waves(tasks)
        assert plan.total_subtasks == 6
        # Wave 1: [1,4], Wave 2: [2,3], Wave 3: [5], Wave 4: [6]
        assert plan.total_waves == 4
        assert plan.waves[0].parallelism == 2
        assert plan.waves[1].parallelism == 2
        assert plan.waves[2].parallelism == 1
        assert plan.waves[3].parallelism == 1

    def test_max_concurrency_with_dependencies(self):
        """Concurrency limit should not violate dependency ordering."""
        # 1 -> 3, 2 -> 3; so 1 and 2 can be parallel, 3 must be after
        tasks = [_st(1), _st(2), _st(3, [1, 2])]
        plan = compute_waves(tasks, max_concurrency=1)
        # Wave 1: [1], Wave 2: [2], Wave 3: [3]
        assert plan.total_waves == 3
        # Task 3 must be in the last wave
        last_wave_ids = {s.id for s in plan.waves[-1].subtasks}
        assert 3 in last_wave_ids

    def test_json_round_trip_through_parse_and_waves(self):
        """End-to-end: parse JSON → compute waves → format JSON → re-parse."""
        raw = json.dumps([
            {"id": 1, "desc": "A", "deps": []},
            {"id": 2, "desc": "B", "deps": []},
            {"id": 3, "desc": "C", "deps": [1, 2]},
        ])
        tasks = parse_subtasks_json(raw)
        plan = compute_waves(tasks)
        json_output = format_wave_plan(plan, fmt="json")
        parsed = json.loads(json_output)
        assert parsed["total_subtasks"] == 3
        assert parsed["total_waves"] == 2


class TestCLI:
    """Tests for the main() CLI entry point."""

    SCRIPT = str(__import__("pathlib").Path(__file__).parent / "decompose.py")

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, self.SCRIPT, *args],
            capture_output=True, text=True, timeout=10,
        )

    def test_plan_markdown_output(self):
        plan_json = json.dumps([
            {"id": 1, "desc": "A", "deps": []},
            {"id": 2, "desc": "B", "deps": [1]},
        ])
        result = self._run("--plan", plan_json)
        assert result.returncode == 0
        assert "Wave 1" in result.stdout
        assert "Wave 2" in result.stdout

    def test_plan_json_output(self):
        plan_json = json.dumps([
            {"id": 1, "desc": "A", "deps": []},
            {"id": 2, "desc": "B", "deps": [1]},
        ])
        result = self._run("--plan", plan_json, "-o", "json")
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert parsed["total_subtasks"] == 2
        assert parsed["total_waves"] == 2

    def test_validate_valid_dag(self):
        plan_json = json.dumps([
            {"id": 1, "desc": "A", "deps": []},
            {"id": 2, "desc": "B", "deps": [1]},
        ])
        result = self._run("--validate", plan_json)
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert parsed["valid"] is True
        assert parsed["subtasks"] == 2

    def test_validate_cycle_exits_nonzero(self):
        plan_json = json.dumps([
            {"id": 1, "desc": "A", "deps": [2]},
            {"id": 2, "desc": "B", "deps": [1]},
        ])
        result = self._run("--validate", plan_json)
        assert result.returncode == 1
        parsed = json.loads(result.stdout)
        assert parsed["valid"] is False
        assert "cycle" in parsed["error"].lower()

    def test_validate_unknown_dep_exits_nonzero(self):
        plan_json = json.dumps([
            {"id": 1, "desc": "A", "deps": [99]},
        ])
        result = self._run("--validate", plan_json)
        assert result.returncode == 1
        parsed = json.loads(result.stdout)
        assert parsed["valid"] is False
        assert "unknown" in parsed["error"].lower()

    def test_no_args_shows_help(self):
        result = self._run()
        assert result.returncode == 0
        assert "Example" in result.stdout or "usage" in result.stdout.lower()

    def test_max_concurrency_flag(self):
        plan_json = json.dumps([
            {"id": 1, "desc": "A", "deps": []},
            {"id": 2, "desc": "B", "deps": []},
            {"id": 3, "desc": "C", "deps": []},
        ])
        result = self._run("--plan", plan_json, "--max-concurrency", "1")
        assert result.returncode == 0
        assert "Wave 3" in result.stdout

    def test_no_balance_flag(self):
        plan_json = json.dumps([
            {"id": 1, "desc": "A", "deps": [], "weight": 1},
            {"id": 2, "desc": "B", "deps": [], "weight": 1},
            {"id": 3, "desc": "C", "deps": [], "weight": 4},
        ])
        result = self._run("--plan", plan_json, "--no-balance")
        assert result.returncode == 0
        assert "Light tasks" not in result.stdout
