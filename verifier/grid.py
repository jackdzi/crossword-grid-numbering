"""The crossword verifier. It rebuilds each grid from its seed and numbers it its own way: it splits
every row and column into runs of white cells, keeps the runs of 2 or more, and numbers their first
cells in reading order. The tools number cell by cell instead; the two must agree."""

import json
from pathlib import Path

from .checks import result
from .rng import Stream, canonical_sha256

MAX_SEED = 1_000_000_000
BATCH = 25


def rebuild_rows(task):
    """The task's grid, drawn exactly as the get_grid tool draws it (the same seeded stream)."""
    n = int(task.size.value.split("x")[0])
    stream = Stream("crossword", f"{task.seed}|{task.size.value}|{int(task.symmetric)}")
    black = [[False] * n for _ in range(n)]

    def paint(r, c):
        black[r][c] = True
        if task.symmetric:
            black[n - 1 - r][n - 1 - c] = True

    style = stream.below(10)
    if style != 0:
        percent = stream.between(10, 28)
        for r in range(n):
            for c in range(n):
                if task.symmetric and r * n + c > (n - 1 - r) * n + (n - 1 - c):
                    continue
                if stream.chance(percent, 100):
                    paint(r, c)
        if style in (1, 2):
            line = stream.below(n)
            for i in range(n):
                if style == 1:
                    paint(line, i)
                else:
                    paint(i, line)
    return ["".join("#" if cell else "." for cell in row) for row in black]


def runs(line):
    """(start, length) of every run of 2 or more white cells in one row or column."""
    found, start = [], 0
    for piece in line.split("#"):
        if len(piece) >= 2:
            found.append((start, len(piece)))
        start += len(piece) + 1
    return found


def true_entries(rows):
    """{(direction, row, col): (number, length)} for the grid."""
    n = len(rows)
    starts = {}
    for r, row in enumerate(rows):
        for c, length in runs(row):
            starts[("across", r, c)] = length
    for c in range(n):
        column = "".join(row[c] for row in rows)
        for r, length in runs(column):
            starts[("down", r, c)] = length
    cells = sorted({(r, c) for _, r, c in starts})
    numbers = {cell: index + 1 for index, cell in enumerate(cells)}
    return {key: (numbers[(key[1], key[2])], length) for key, length in starts.items()}


def keyed(entries):
    """{(direction, row, col): (number, length)} for entries, plus the keys given twice."""
    table, twice = {}, []
    for e in entries:
        key = (e.direction.value, e.row, e.col)
        if key in table:
            twice.append(key)
        table[key] = (e.number, e.length)
    return table, twice


def all_runs(rows):
    """Every maximal white run, single cells included, as (direction, row, col, length), in the order
    get_grid lists them: by first cell, across before down."""
    columns = ["".join(row[c] for row in rows) for c in range(len(rows))]
    found = []
    for direction, lines in (("across", rows), ("down", columns)):
        for i, line in enumerate(lines):
            start = 0
            for piece in line.split("#"):
                if piece:
                    found.append((i, start, direction, len(piece)) if direction == "across" else (start, i, direction, len(piece)))
                start += len(piece) + 1
    found.sort(key=lambda run: (run[0], run[1], run[2] == "down"))
    return [(direction, r, c, length) for r, c, direction, length in found]


def true_numbers(rows):
    """The correct number of each run: its entry's clue number, 0 for a single cell."""
    truth = true_entries(rows)
    return [truth[(d, r, c)][0] if length >= 2 else 0 for d, r, c, length in all_runs(rows)]


def label(run):
    direction, r, c, length = run
    return f"{direction} run at row {r}, col {c} (length {length})"


def save_path(task):
    shape = "symmetric" if task.symmetric else "free"
    return f"crossword/{task.size.value}-{shape}-{task.seed}.json"


def seed_problem(task):
    if not 0 <= task.seed <= MAX_SEED:
        return f"seed must be from 0 to {MAX_SEED}"
    return None


def verify_grid_input(value):
    problem = seed_problem(value)
    return result(False, problem) if problem else result(True, "input is valid")


def verify_numbers_input(value):
    problem = seed_problem(value.task)
    if problem:
        return result(False, problem)
    count = len(all_runs(rebuild_rows(value.task)))
    if value.start < 0 or not 1 <= len(value.numbers) <= BATCH or value.start + len(value.numbers) > count:
        return result(False, f"a batch numbers 1 to {BATCH} runs, from start, within the grid's {count} runs")
    if any(n < 0 for n in value.numbers):
        return result(False, "a number is 0 (no entry) or a clue number from 1")
    return result(True, "input is valid")


def verify_get_output(task, output):
    rows = rebuild_rows(task)
    columns = ["".join(row[c] for row in rows) for c in range(len(rows))]
    if output.rows != rows or output.columns != columns or output.size != len(rows):
        return result(False, "the grid is not the one the seed gives")
    if output.black_cells != sum(row.count("#") for row in rows):
        return result(False, "black_cells does not count the black cells")
    given = [(run.direction.value, run.row, run.col, run.length) for run in output.runs]
    expected = all_runs(rows)
    if given != expected[:BATCH] or output.total_runs != len(expected):
        return result(False, "runs is not the first batch of the grid's white runs, in reading order")
    return result(True, "the grid is the seed's")


def read_saved(task, workspace):
    """The saved numbers, or a problem."""
    path = Path(workspace) / save_path(task)
    if not path.is_file():
        return None, f"{save_path(task)} was never saved"
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None, f"{save_path(task)} is not valid JSON"
    if not isinstance(saved, dict) or not isinstance(saved.get("numbers"), list):
        return None, f"{save_path(task)} holds no numbers"
    return saved["numbers"], None


def verify_numbers_output(given, output, workspace):
    saved, problem = read_saved(given.task, workspace)
    if problem:
        return result(False, problem)
    count = len(all_runs(rebuild_rows(given.task)))
    if output.file != save_path(given.task) or saved != output.numbers or saved[given.start :] != list(given.numbers):
        return result(False, "the saved numbers are not the ones given")
    if (output.runs, output.next_start, output.complete, output.last_number) != (count, len(saved), len(saved) == count, max(saved, default=0)):
        return result(False, "runs, next_start, complete or last_number does not describe the saved numbers")
    following = [(run.direction.value, run.row, run.col, run.length) for run in output.next_runs]
    if following != all_runs(rebuild_rows(given.task))[len(saved) : len(saved) + BATCH]:
        return result(False, "next_runs is not the next batch of runs")
    return result(True, "the numbers are saved", saved=len(saved))


def verify_pin_output(task, output):
    rows = rebuild_rows(task)
    if output.rows != rows or output.grid_sha256 != canonical_sha256(rows):
        return result(False, "the pinned grid is not the seed's")
    if output.numbers != true_numbers(rows) or keyed(output.entries)[0] != true_entries(rows):
        return result(False, "the pinned numbering disagrees with the verifier's own")
    return result(True, "the answer key is the grid's numbering", entries=len(output.entries))


def verify_task(arguments, output, reference, workspace):
    rows = rebuild_rows(arguments)
    if reference is None or verify_pin_output(arguments, reference)["valid"] is not True:
        return result(False, "the pinned answer key does not match the grid the seed gives")
    runs_list = all_runs(rows)
    truth = true_numbers(rows)
    given = list(output.numbers)
    problems, wrong = [], []
    if len(given) != len(truth):
        problems.append(f"{len(given)} numbers for {len(truth)} runs")
    for index, (run, expected) in enumerate(zip(runs_list, truth)):
        got = given[index] if index < len(given) else None
        if got != expected:
            wrong.append(f"{label(run)}: {got if got is not None else 'missing'}, expected {expected}")
    correct = sum(1 for index, expected in enumerate(truth) if index < len(given) and given[index] == expected)
    score = correct / max(len(truth), len(given), 1)
    saved, file_problem = read_saved(arguments, workspace)
    if saved is not None and saved != given:
        file_problem = f"{save_path(arguments)} does not hold the submitted numbers"
    if wrong:
        problems.append(f"{len(wrong)} run(s) numbered wrong: " + "; ".join(wrong[:4]) + (" ..." if len(wrong) > 4 else ""))
    if file_problem:
        problems.append(file_problem)
        # The saved file is the run's actual result: an answer that was not saved earns half at most.
        score = min(score, 0.5)
    details = {
        "runs": len(truth),
        "entries_expected": sum(1 for n in truth if n),
        "runs_correct": correct,
        "wrong": wrong,
        "saved_file": file_problem or "matches the submission",
    }
    if problems:
        return result(False, "; ".join(problems), score=score, **details)
    return result(True, f"all {len(truth)} runs are numbered correctly ({details['entries_expected']} entries) and saved", **details)
