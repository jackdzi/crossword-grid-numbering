"""The verifier on correct, wrong, missing, malformed and boundary results."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from helpers import as_sandbox, gold_run, task
from slimconfig import build_output, plain_output

import verifier
from contract import NumberingOutput, SaveInput
from plugin.grid import grid_rows, save_path

TASK = "number-grid"


def entries_of(output: NumberingOutput) -> list[dict]:
    return [plain_output(e) for e in output.entries]


def resubmit(given, entries: list[dict], workspace: Path, *, save: bool = True) -> dict:
    """Submit ``entries`` (saving them first, as the agent would) and return the verdict."""
    if save:
        path = workspace / save_path(given)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "task": plain_output(given),
            "across": [e for e in entries if e["direction"] == "across"],
            "down": [e for e in entries if e["direction"] == "down"],
        }
        path.write_text(json.dumps(data))
    _, reference = gold_run(given, workspace / "scratch")
    return verifier.verify_task(TASK, given, as_sandbox({"entries": entries}, NumberingOutput), reference, str(workspace))


def test_accepts_a_correct_numbering(tmp_path: Path) -> None:
    given = task()
    output, reference = gold_run(given, tmp_path)
    verdict = verifier.verify_task(TASK, given, output, reference, str(tmp_path))
    assert verdict["valid"] is True and verdict["score"] == 1.0, verdict["message"]


def test_rejects_a_wrong_number(tmp_path: Path) -> None:
    given = task()
    output, _ = gold_run(given, tmp_path / "gold")
    entries = entries_of(output)
    entries[-1]["number"] += 1
    verdict = resubmit(given, entries, tmp_path)
    assert verdict["valid"] is False and verdict["details"]["wrong_number"]
    assert 0 < verdict["score"] < 1


def test_rejects_a_wrong_length(tmp_path: Path) -> None:
    given = task()
    output, _ = gold_run(given, tmp_path / "gold")
    entries = entries_of(output)
    entries[0]["length"] += 1
    verdict = resubmit(given, entries, tmp_path)
    assert verdict["valid"] is False and verdict["details"]["wrong_length"]


def test_rejects_a_missing_entry(tmp_path: Path) -> None:
    given = task()
    output, _ = gold_run(given, tmp_path / "gold")
    verdict = resubmit(given, entries_of(output)[1:], tmp_path)
    assert verdict["valid"] is False and verdict["details"]["missing"]


def test_rejects_a_length_one_run_counted_as_an_entry(tmp_path: Path) -> None:
    # This grid has a lone white cell between black cells; claim it as a length-1 entry.
    given = task(seed=11, size="7x7", symmetric=False)
    rows = grid_rows(given)
    output, _ = gold_run(given, tmp_path / "gold")
    entries = entries_of(output)
    lone = next(
        (r, c)
        for r in range(len(rows))
        for c in range(len(rows))
        if rows[r][c] == "." and (c == 0 or rows[r][c - 1] == "#") and (c == len(rows) - 1 or rows[r][c + 1] == "#")
    )
    entries.append({"number": 99, "direction": "across", "row": lone[0], "col": lone[1], "length": 1})
    verdict = resubmit(given, entries, tmp_path)
    assert verdict["valid"] is False and verdict["details"]["extra"]


def test_rejects_an_entry_given_twice(tmp_path: Path) -> None:
    given = task()
    output, _ = gold_run(given, tmp_path / "gold")
    entries = entries_of(output)
    verdict = resubmit(given, entries + entries[:1], tmp_path)
    assert verdict["valid"] is False and verdict["details"]["given_twice"]


def test_rejects_an_empty_submission(tmp_path: Path) -> None:
    given = task()
    verdict = resubmit(given, [], tmp_path)
    assert verdict["valid"] is False and verdict["score"] == 0.0


def test_rejects_a_correct_answer_that_was_never_saved(tmp_path: Path) -> None:
    given = task()
    output, _ = gold_run(given, tmp_path / "gold")
    verdict = resubmit(given, entries_of(output), tmp_path, save=False)
    assert verdict["valid"] is False and "never saved" in verdict["details"]["saved_file"]
    assert verdict["score"] == 0.5


def test_rejects_a_submission_that_differs_from_the_saved_file(tmp_path: Path) -> None:
    given = task()
    output, reference = gold_run(given, tmp_path)
    entries = entries_of(output)
    entries[0]["number"] += 5
    verdict = verifier.verify_task(TASK, given, as_sandbox({"entries": entries}, NumberingOutput), reference, str(tmp_path))
    assert verdict["valid"] is False and "does not hold the submitted entries" in verdict["details"]["saved_file"]


def test_rejects_a_tampered_answer_key(tmp_path: Path) -> None:
    given = task()
    output, reference = gold_run(given, tmp_path)
    reference.entries = reference.entries[1:]
    assert verifier.verify_task(TASK, given, output, reference, str(tmp_path))["valid"] is False


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize("size", ["5x5", "11x11"])
def test_boundary_grids_are_numbered(tmp_path: Path, seed: int, size: str) -> None:
    # Over 40 seeds these include grids with no black cell, an all-black row and an all-black column.
    given = task(seed=seed, size=size, symmetric=seed % 2 == 0)
    output, reference = gold_run(given, tmp_path)
    assert verifier.verify_task(TASK, given, output, reference, str(tmp_path))["valid"] is True


def test_the_seeds_cover_the_boundary_grids() -> None:
    grids = [grid_rows(task(seed=seed, size="7x7", symmetric=False)) for seed in range(40)]
    assert any("#" not in "".join(rows) for rows in grids), "no grid without black cells"
    assert any("." * 7 not in rows and "#" * 7 in rows for rows in grids), "no all-black row"


def test_input_checks_refuse_malformed_saves() -> None:
    given = plain_output(task())
    wrong_direction = build_output(
        {"task": given, "direction": "across", "entries": [{"number": 1, "direction": "down", "row": 0, "col": 0, "length": 3}]},
        SaveInput,
    )
    outside = build_output(
        {"task": given, "direction": "across", "entries": [{"number": 1, "direction": "across", "row": 9, "col": 0, "length": 3}]},
        SaveInput,
    )
    too_short = build_output(
        {"task": given, "direction": "across", "entries": [{"number": 1, "direction": "across", "row": 0, "col": 0, "length": 1}]},
        SaveInput,
    )
    for value in (wrong_direction, outside, too_short):
        assert verifier.verify_input("save_entries", value)["valid"] is False
    assert verifier.verify_input("get_grid", task(seed=-1))["valid"] is False


def test_tool_outputs_are_checked(tmp_path: Path) -> None:
    from plugin import get_grid

    given = task()
    made = as_sandbox(get_grid(given, tmp_path), type(get_grid(given, tmp_path)))
    assert verifier.verify_output("get_grid", given, made, str(tmp_path))["valid"] is True
    made.rows = made.rows[::-1]
    assert verifier.verify_output("get_grid", given, made, str(tmp_path))["valid"] is False
