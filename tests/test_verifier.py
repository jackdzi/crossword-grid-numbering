"""The verifier on correct, wrong, missing, malformed and boundary results."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from helpers import as_sandbox, gold_run, save, task
from slimconfig import build_output, plain_output

import verifier
from contract import GridOutput, NumberingOutput, NumbersInput, NumbersOutput
from plugin import get_grid
from plugin.grid import grid_rows, save_path, white_runs

TASK = "number-grid"


def resubmit(given, numbers: list[int], workspace: Path, *, saved: list[int] | None = None) -> dict:
    """Submit ``numbers`` after writing ``saved`` (by default the same numbers) as the saved file."""
    stored = numbers if saved is None else saved
    path = workspace / save_path(given)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"task": plain_output(given), "numbers": stored, "entries": []}))
    _, reference = gold_run(given, workspace / "scratch")
    return verifier.verify_task(TASK, given, as_sandbox({"numbers": numbers}, NumberingOutput), reference, str(workspace))


def gold_numbers(given, workspace: Path) -> list[int]:
    return list(gold_run(given, workspace / "gold")[0].numbers)


def test_accepts_a_correct_numbering(tmp_path: Path) -> None:
    given = task()
    output, reference = gold_run(given, tmp_path)
    verdict = verifier.verify_task(TASK, given, output, reference, str(tmp_path))
    assert verdict["valid"] is True and verdict["score"] == 1.0, verdict["message"]


def test_rejects_a_wrong_number(tmp_path: Path) -> None:
    given = task()
    numbers = gold_numbers(given, tmp_path)
    last = max(range(len(numbers)), key=lambda i: numbers[i])
    numbers[last] += 1
    verdict = resubmit(given, numbers, tmp_path)
    assert verdict["valid"] is False and verdict["details"]["wrong"] and 0 < verdict["score"] < 1


def test_rejects_a_numbering_that_slips_by_one(tmp_path: Path) -> None:
    # Missing one entry shifts every later number: the verifier names each run it shifts.
    given = task(seed=2026, size="11x11", symmetric=False)
    numbers = gold_numbers(given, tmp_path)
    first = next(i for i, n in enumerate(numbers) if n > 1)
    shifted = numbers[:first] + [n - 1 if n else 0 for n in numbers[first:]]
    verdict = resubmit(given, shifted, tmp_path)
    assert verdict["valid"] is False and len(verdict["details"]["wrong"]) > 5


def test_rejects_a_single_cell_numbered_as_an_entry(tmp_path: Path) -> None:
    given = task(seed=11, size="7x7", symmetric=False)
    numbers = gold_numbers(given, tmp_path)
    runs = white_runs(grid_rows(given))
    single = next(i for i, run in enumerate(runs) if run.length == 1)
    numbers[single] = 99
    verdict = resubmit(given, numbers, tmp_path)
    assert verdict["valid"] is False and "expected 0" in verdict["message"]


def test_rejects_an_entry_numbered_as_a_single_cell(tmp_path: Path) -> None:
    given = task()
    numbers = gold_numbers(given, tmp_path)
    numbers[numbers.index(1)] = 0
    assert resubmit(given, numbers, tmp_path)["valid"] is False


def test_rejects_too_few_or_too_many_numbers(tmp_path: Path) -> None:
    given = task()
    numbers = gold_numbers(given, tmp_path)
    for wrong in (numbers[:-1], numbers + [0]):
        verdict = resubmit(given, wrong, tmp_path)
        assert verdict["valid"] is False and "runs" in verdict["message"]


def test_rejects_an_empty_submission(tmp_path: Path) -> None:
    verdict = resubmit(task(), [], tmp_path)
    assert verdict["valid"] is False and verdict["score"] == 0.0


def test_rejects_a_correct_answer_that_was_never_saved(tmp_path: Path) -> None:
    given = task()
    numbers = gold_numbers(given, tmp_path)
    _, reference = gold_run(given, tmp_path / "scratch")
    verdict = verifier.verify_task(TASK, given, as_sandbox({"numbers": numbers}, NumberingOutput), reference, str(tmp_path / "empty"))
    assert verdict["valid"] is False and "never saved" in verdict["details"]["saved_file"] and verdict["score"] == 0.5


def test_rejects_a_submission_that_differs_from_the_saved_file(tmp_path: Path) -> None:
    given = task()
    numbers = gold_numbers(given, tmp_path)
    changed = list(numbers)
    changed[0] = 0 if changed[0] else 1
    verdict = resubmit(given, numbers, tmp_path, saved=changed)
    assert verdict["valid"] is False and "does not hold the submitted numbers" in verdict["details"]["saved_file"]


def test_rejects_a_tampered_answer_key(tmp_path: Path) -> None:
    given = task()
    output, reference = gold_run(given, tmp_path)
    reference.numbers = reference.numbers[1:]
    assert verifier.verify_task(TASK, given, output, reference, str(tmp_path))["valid"] is False
    assert verifier.verify_task(TASK, given, output, None, str(tmp_path))["valid"] is False


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize("size", ["5x5", "11x11"])
def test_boundary_grids_are_numbered(tmp_path: Path, seed: int, size: str) -> None:
    # Over 40 seeds these include grids with no black cell, an all-black row and an all-black column,
    # and 11x11 grids that need three batches.
    given = task(seed=seed, size=size, symmetric=seed % 2 == 0)
    output, reference = gold_run(given, tmp_path)
    assert verifier.verify_task(TASK, given, output, reference, str(tmp_path))["valid"] is True


def test_the_largest_grid_takes_three_batches(tmp_path: Path) -> None:
    given = task(seed=930, size="11x11", symmetric=True)
    assert len(white_runs(grid_rows(given))) == 74
    output, reference = gold_run(given, tmp_path)
    assert verifier.verify_task(TASK, given, output, reference, str(tmp_path))["valid"] is True


def test_the_seeds_cover_the_boundary_grids() -> None:
    grids = [grid_rows(task(seed=seed, size="7x7", symmetric=False)) for seed in range(40)]
    assert any("#" not in "".join(rows) for rows in grids), "no grid without black cells"
    assert any("#" * 7 in rows for rows in grids), "no all-black row"


def test_input_checks_refuse_malformed_batches() -> None:
    given = plain_output(task())
    count = len(white_runs(grid_rows(task())))
    for bad in ({"start": 0, "numbers": [-1]}, {"start": 0, "numbers": [0] * 26}, {"start": count, "numbers": [0]}, {"start": 0, "numbers": []}):
        value = build_output({"task": given, **bad}, NumbersInput)
        assert verifier.verify_input("save_numbers", value)["valid"] is False, bad
    assert verifier.verify_input("get_grid", task(seed=-1))["valid"] is False


def test_tool_outputs_are_checked(tmp_path: Path) -> None:
    given = task()
    made = as_sandbox(get_grid(given, tmp_path), GridOutput)
    assert verifier.verify_output("get_grid", given, made, str(tmp_path))["valid"] is True
    made.runs = made.runs[1:]
    assert verifier.verify_output("get_grid", given, made, str(tmp_path))["valid"] is False
    batch = [0] * len(get_grid(given, tmp_path).runs)
    saved = as_sandbox(save(given, 0, batch, tmp_path), NumbersOutput)
    value = build_output({"task": plain_output(given), "start": 0, "numbers": batch}, NumbersInput)
    assert verifier.verify_output("save_numbers", value, saved, str(tmp_path))["valid"] is True
    saved.next_start += 1
    assert verifier.verify_output("save_numbers", value, saved, str(tmp_path))["valid"] is False
