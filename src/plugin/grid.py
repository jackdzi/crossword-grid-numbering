"""The crossword grids, their numbering, and the three tools."""

from __future__ import annotations

import json
from pathlib import Path

from slimconfig import plain_output

from contract import Direction, Entry, GridInput, GridOutput, NumbersInput, NumbersOutput, PinOutput, Run
from plugin.rng import Stream, canonical_sha256

BLACK, WHITE = "#", "."
MAX_SEED = 1_000_000_000
BATCH = 25  # runs per batch: one batch's reasoning fits a 2,048-token reply; 74 runs (the most) take 3 batches


def grid_rows(task: GridInput) -> list[str]:
    """The task's grid. A tenth of seeds have no black cell, a tenth a black row, a tenth a black column."""
    if not 0 <= task.seed <= MAX_SEED:
        raise ValueError(f"seed must be from 0 to {MAX_SEED}")
    n = int(task.size.value.split("x")[0])
    stream = Stream("crossword", f"{task.seed}|{task.size.value}|{int(task.symmetric)}")
    black = [[False] * n for _ in range(n)]

    def paint(r: int, c: int) -> None:
        black[r][c] = True
        if task.symmetric:
            black[n - 1 - r][n - 1 - c] = True

    style = stream.below(10)
    if style != 0:
        percent = stream.between(10, 28)
        for r in range(n):
            for c in range(n):
                # With symmetry, only the first half (and the centre) is drawn; paint() mirrors it.
                if task.symmetric and r * n + c > (n - 1 - r) * n + (n - 1 - c):
                    continue
                if stream.chance(percent, 100):
                    paint(r, c)
        if style == 1:
            line = stream.below(n)
            for c in range(n):
                paint(line, c)
        elif style == 2:
            line = stream.below(n)
            for r in range(n):
                paint(r, line)
    return ["".join(BLACK if cell else WHITE for cell in row) for row in black]


def number(rows: list[str]) -> list[Entry]:
    """The standard numbering: reading row by row, a white cell that starts an across or down run of
    2 or more white cells gets the next number."""
    n = len(rows)

    def white(r: int, c: int) -> bool:
        return 0 <= r < n and 0 <= c < n and rows[r][c] == WHITE

    def run(r: int, c: int, dr: int, dc: int) -> int:
        length = 0
        while white(r + dr * length, c + dc * length):
            length += 1
        return length

    entries: list[Entry] = []
    next_number = 1
    for r in range(n):
        for c in range(n):
            if not white(r, c):
                continue
            across = run(r, c, 0, 1) if not white(r, c - 1) else 0
            down = run(r, c, 1, 0) if not white(r - 1, c) else 0
            if across < 2 and down < 2:
                continue
            if across >= 2:
                entries.append(Entry(number=next_number, direction=Direction.ACROSS, row=r, col=c, length=across))
            if down >= 2:
                entries.append(Entry(number=next_number, direction=Direction.DOWN, row=r, col=c, length=down))
            next_number += 1
    return entries


def ordered(entries: list[Entry]) -> list[Entry]:
    return sorted(entries, key=lambda e: (e.number, e.direction is Direction.DOWN, e.row, e.col))


def save_path(task: GridInput) -> str:
    shape = "symmetric" if task.symmetric else "free"
    return f"crossword/{task.size.value}-{shape}-{task.seed}.json"


def white_runs(rows: list[str]) -> list[Run]:
    """Every maximal run of white cells, across and down, single cells included, by first cell."""
    n = len(rows)
    found = []
    for r in range(n):
        for c in range(n):
            if rows[r][c] != WHITE:
                continue
            for direction, dr, dc in ((Direction.ACROSS, 0, 1), (Direction.DOWN, 1, 0)):
                if 0 <= r - dr and 0 <= c - dc and rows[r - dr][c - dc] == WHITE:
                    continue
                length = 0
                while r + dr * length < n and c + dc * length < n and rows[r + dr * length][c + dc * length] == WHITE:
                    length += 1
                found.append(Run(direction=direction, row=r, col=c, length=length))
    return found


def get_grid(task: GridInput, workspace: Path) -> GridOutput:
    rows = grid_rows(task)
    runs = white_runs(rows)
    columns = ["".join(row[c] for row in rows) for c in range(len(rows))]
    return GridOutput(
        size=len(rows), rows=rows, columns=columns, black_cells=sum(row.count(BLACK) for row in rows), total_runs=len(runs), runs=runs[:BATCH]
    )


def save_numbers(given: NumbersInput, workspace: Path) -> NumbersOutput:
    """Save one batch of numbers, one per run from ``start``: the run's clue number, or 0 for a single cell."""
    runs = white_runs(grid_rows(given.task))
    path = workspace / save_path(given.task)
    saved = json.loads(path.read_text(encoding="utf-8"))["numbers"] if path.is_file() and given.start > 0 else []
    if given.start != len(saved):
        raise ValueError(f"start is {given.start}, but {len(saved)} runs are numbered: the next batch starts at {len(saved)}")
    if not 1 <= len(given.numbers) <= BATCH:
        raise ValueError(f"a batch numbers 1 to {BATCH} runs")
    if given.start + len(given.numbers) > len(runs):
        raise ValueError(f"the grid has {len(runs)} runs; this batch would end at run {given.start + len(given.numbers)}")
    if any(n < 0 for n in given.numbers):
        raise ValueError("a number is 0 (no entry) or a clue number from 1")
    numbers = saved + list(given.numbers)
    entries = [
        Entry(number=n, direction=run.direction, row=run.row, col=run.col, length=run.length)
        for run, n in zip(runs, numbers)
        if n > 0
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"task": plain_output(given.task), "numbers": numbers, "entries": [plain_output(e) for e in ordered(entries)]}
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return NumbersOutput(
        file=save_path(given.task),
        runs=len(runs),
        next_start=len(numbers),
        complete=len(numbers) == len(runs),
        last_number=max(numbers, default=0),
        numbers=numbers,
        next_runs=runs[len(numbers) : len(numbers) + BATCH],
    )


def pin_numbering(task: GridInput, workspace: Path) -> PinOutput:
    rows = grid_rows(task)
    entries = number(rows)
    by_start = {(e.direction, e.row, e.col): e.number for e in entries}
    numbers = [by_start.get((run.direction, run.row, run.col), 0) for run in white_runs(rows)]
    return PinOutput(grid_sha256=canonical_sha256(rows), rows=rows, numbers=numbers, entries=ordered(entries))

