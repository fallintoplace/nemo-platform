# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import run_all_tests


@pytest.mark.parametrize(
    ("flags", "expected_filter"),
    [
        ((), "not slow and not e2e and not integration"),
        (("--integration",), "integration"),
        (("--e2e",), "e2e"),
        (("--regression",), "regression"),
        (("--integration", "--e2e"), "integration and e2e"),
        (("--all",), None),
        (("--all", "--integration", "--e2e"), None),
    ],
)
def test_cli_respects_marker_selection(monkeypatch, flags: tuple[str, ...], expected_filter: str | None) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], capture_output: bool) -> SimpleNamespace:
        assert capture_output is False
        commands.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_all_tests, "find_test_directories", lambda _root: [("package", Path("tools/tests"))])
    monkeypatch.setattr(run_all_tests, "print_summary", lambda _dirs: None)
    monkeypatch.setattr(run_all_tests.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["run_all_tests.py", *flags])

    assert run_all_tests.main() == 0
    assert len(commands) == 1
    command = commands[0]
    if expected_filter is None:
        assert "-m" not in command
    else:
        assert command[command.index("-m") + 1] == expected_filter
