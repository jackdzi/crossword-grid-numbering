"""The crossword verifier. It rebuilds each grid from its seed and numbers it its own way: it splits
every row and column into runs of white cells, keeps the runs of 2 or more, and numbers their first
cells in reading order. The tools number cell by cell instead; the two must agree."""

import json
from pathlib import Path

from .checks import result
from .rng import Stream, canonical_sha256

MAX_SEED = 1_000_000_000


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
    """{(direction, row, col): (number, length)} for submitted entries, plus the keys given twice."""
    table, twice = {}, []
    for e in entries:
        key = (e.direction.value, e.row, e.col)
        if key in table:
            twice.append(key)
        table[key] = (e.number, e.length)
    return table, twice


def label(key):
    return f"{key[0]} at row {key[1]}, col {key[2]}"


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


def verify_save_input(value):
    problem = seed_problem(value.task)
    if problem:
        return result(False, problem)
    n = int(value.task.size.value.split("x")[0])
    for e in value.entries:
        if e.direction is not value.direction:
            return result(False, f"entry {e.number} is {e.direction.value}; this call saves {value.direction.value} entries")
        if not (0 <= e.row < n and 0 <= e.col < n):
            return result(False, f"entry {e.number} starts outside the {n}x{n} grid")
        if e.length < 2 or e.number < 1:
            return result(False, f"entry {e.number}: a number is at least 1 and a length at least 2")
    _, twice = keyed(value.entries)
    if twice:
        return result(False, f"{label(twice[0])} is given twice")
    return result(True, "input is valid")


def verify_get_output(task, output):
    rows = rebuild_rows(task)
    columns = ["".join(row[c] for row in rows) for c in range(len(rows))]
    if output.rows != rows or output.columns != columns or output.size != len(rows):
        return result(False, "the grid is not the one the seed gives")
    if output.black_cells != sum(row.count("#") for row in rows):
        return result(False, "black_cells does not count the black cells")
    return result(True, "the grid is the seed's")


def read_saved(task, workspace):
    """The saved numbering's (across, down) entries as plain dicts, or a problem."""
    path = Path(workspace) / save_path(task)
    if not path.is_file():
        return None, f"{save_path(task)} was never saved"
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None, f"{save_path(task)} is not valid JSON"
    if not isinstance(saved, dict) or "across" not in saved or "down" not in saved:
        return None, f"{save_path(task)} does not hold both the across and the down entries"
    return saved, None


def plain_keys(items):
    table = {}
    for item in items:
        table[(item["direction"], item["row"], item["col"])] = (item["number"], item["length"])
    return table


def verify_save_output(save, output, workspace):
    path = Path(workspace) / save_path(save.task)
    if output.file != save_path(save.task) or not path.is_file():
        return result(False, f"{save_path(save.task)} was not written")
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    if output.complete != ("across" in on_disk and "down" in on_disk):
        return result(False, "complete does not say whether both directions are saved")
    returned, _ = keyed(output.entries)
    if plain_keys(on_disk.get("across", []) + on_disk.get("down", [])) != returned:
        return result(False, "the returned entries are not the ones saved on disk")
    return result(True, "the entries are saved", across=output.across, down=output.down)


def verify_pin_output(task, output):
    rows = rebuild_rows(task)
    if output.rows != rows or output.grid_sha256 != canonical_sha256(rows):
        return result(False, "the pinned grid is not the seed's")
    pinned, _ = keyed(output.entries)
    if pinned != true_entries(rows):
        return result(False, "the pinned numbering disagrees with the verifier's own")
    return result(True, "the answer key is the grid's numbering", entries=len(pinned))


def verify_task(arguments, output, reference, workspace):
    rows = rebuild_rows(arguments)
    truth = true_entries(rows)
    if reference is None or reference.grid_sha256 != canonical_sha256(rows) or keyed(reference.entries)[0] != truth:
        return result(False, "the pinned answer key does not match the grid the seed gives")
    submitted, twice = keyed(output.entries)
    missing = sorted(key for key in truth if key not in submitted)
    extra = sorted(key for key in submitted if key not in truth)
    wrong_number = sorted(k for k in submitted if k in truth and submitted[k][0] != truth[k][0])
    wrong_length = sorted(k for k in submitted if k in truth and submitted[k][1] != truth[k][1])
    correct = sum(1 for k in submitted if submitted.get(k) == truth.get(k))
    score = correct / max(len(truth), len(output.entries), 1)
    saved, file_problem = read_saved(arguments, workspace)
    if saved is not None and plain_keys(saved["across"] + saved["down"]) != submitted:
        file_problem = f"{save_path(arguments)} does not hold the submitted entries"
    problems = []
    for name, keys in (("missing", missing), ("extra", extra), ("wrong number", wrong_number), ("wrong length", wrong_length), ("given twice", twice)):
        if keys:
            problems.append(f"{name}: " + "; ".join(label(k) for k in keys[:5]) + (" ..." if len(keys) > 5 else ""))
    if file_problem:
        problems.append(file_problem)
        # The saved file is the run's actual result: an answer that was not saved earns half at most.
        score = min(score, 0.5)
    details = {
        "entries_expected": len(truth),
        "entries_submitted": len(output.entries),
        "entries_correct": correct,
        "missing": [label(k) for k in missing],
        "extra": [label(k) for k in extra],
        "wrong_number": [f"{label(k)}: {submitted[k][0]}, expected {truth[k][0]}" for k in wrong_number],
        "wrong_length": [f"{label(k)}: {submitted[k][1]}, expected {truth[k][1]}" for k in wrong_length],
        "given_twice": [label(k) for k in twice],
        "saved_file": file_problem or "matches the submission",
    }
    if problems:
        return result(False, "; ".join(problems), score=score, **details)
    return result(True, f"all {len(truth)} entries are numbered correctly and saved", **details)

