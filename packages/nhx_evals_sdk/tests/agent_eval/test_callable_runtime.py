# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
from typing import Any

import pytest
from nhx_evals_sdk.agent_eval.runtimes.callable_runtime import (
    CallableAgentTaskRunner,
    TrialDraft,
)
from nhx_evals_sdk.agent_eval.tasks import AgentEvalRunConfig, AgentEvalTask
from nhx_evals_sdk.agent_eval.trials import AgentEvalTrialStatus, AgentOutput, TrialMeasurements


def _task(task_id: str) -> AgentEvalTask:
    return AgentEvalTask(id=task_id, intent="Answer.", inputs={"instruction": f"q-{task_id}"})


@pytest.mark.asyncio
async def test_callable_runtime_wraps_str_output_and_trialdraft_in_order() -> None:
    async def agent_fn(task: AgentEvalTask) -> TrialDraft | str:
        if task.id == "t2":
            return TrialDraft(
                output=AgentOutput(output_text="drafted"),
                metadata={"k": "v"},
                measurements=TrialMeasurements(prompt_tokens=4, completion_tokens=1),
            )
        return f"answer-{task.id}"

    runtime = CallableAgentTaskRunner(agent_fn, parallelism=2)
    trials = await runtime.run_tasks([_task("t1"), _task("t2")], config=AgentEvalRunConfig())

    assert [trial.task_id for trial in trials] == ["t1", "t2"]
    assert trials[0].id == "t1:trial"
    assert trials[0].status == AgentEvalTrialStatus.COMPLETED
    assert trials[0].output is not None and trials[0].output.output_text == "answer-t1"
    assert trials[1].output is not None and trials[1].output.output_text == "drafted"
    assert trials[1].metadata == {"k": "v"}
    assert trials[1].measurements.total_tokens == 5
    assert trials[0].measurements == TrialMeasurements()


@pytest.mark.asyncio
async def test_callable_runtime_captures_exception_as_failed_trial_but_rejects_bad_return() -> None:
    async def failing_fn(task: AgentEvalTask) -> str:
        raise RuntimeError("nope")

    failed = (await CallableAgentTaskRunner(failing_fn).run_tasks([_task("boom")]))[0]
    assert failed.status == AgentEvalTrialStatus.FAILED
    assert failed.output is None
    assert "RuntimeError: nope" in failed.metadata["error"]

    # Invalid agent output is a programming error, not a failed trial. ``Any`` lets the test
    # break the callable's contract on purpose.
    async def bad_return_fn(task: AgentEvalTask) -> Any:
        return 123

    with pytest.raises(TypeError, match="TrialDraft, AgentOutput, or str"):
        await CallableAgentTaskRunner(bad_return_fn).run_tasks([_task("bad")])


@pytest.mark.asyncio
async def test_callable_runtime_bounds_pending_tasks_and_preserves_order() -> None:
    parallelism = 3
    task_ids = [f"t{i}" for i in range(32)]
    started = asyncio.Event()
    release = asyncio.Event()
    active = 0
    peak_active = 0

    async def agent_fn(task: AgentEvalTask) -> str:
        nonlocal active, peak_active
        active += 1
        peak_active = max(peak_active, active)
        if active == parallelism:
            started.set()
        try:
            await release.wait()
            return f"answer-{task.id}"
        finally:
            active -= 1

    baseline_tasks = asyncio.all_tasks()
    runner = CallableAgentTaskRunner(agent_fn, parallelism=parallelism)
    running = asyncio.create_task(runner.run_tasks([_task(task_id) for task_id in task_ids]))
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        pending_children = asyncio.all_tasks() - baseline_tasks - {running}
    finally:
        release.set()
        trials = await running

    assert len(pending_children) <= parallelism
    assert peak_active == parallelism
    assert [trial.task_id for trial in trials] == task_ids
    assert all(trial.status == AgentEvalTrialStatus.COMPLETED for trial in trials)
