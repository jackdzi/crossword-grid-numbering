"""The crossword grids, their numbering, and the three tools."""

from __future__ import annotations

import json
from pathlib import Path

from slimconfig import build_output, plain_output

from contract import Direction, Entry, GridInput, GridOutput, PinOutput, SaveInput, SaveOutput
from plugin.rng import Stream, canonical_sha256

BLACK, WHITE = "#", "."
MAX_SEED = 1_000_000_000


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


def get_grid(task: GridInput, workspace: Path) -> GridOutput:
    rows = grid_rows(task)
    columns = ["".join(row[c] for row in rows) for c in range(len(rows))]
    return GridOutput(size=len(rows), rows=rows, columns=columns, black_cells=sum(row.count(BLACK) for row in rows))


def save_entries(save: SaveInput, workspace: Path) -> SaveOutput:
    rows = grid_rows(save.task)
    n = len(rows)
    for entry in save.entries:
        if entry.direction is not save.direction:
            raise ValueError(f"entry {entry.number} is {entry.direction.value}, but this call saves {save.direction.value} entries")
        if not (0 <= entry.row < n and 0 <= entry.col < n):
            raise ValueError(f"entry {entry.number} starts at ({entry.row}, {entry.col}), outside the {n}x{n} grid")
    path = workspace / save_path(save.task)
    saved = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"task": plain_output(save.task)}
    if saved["task"] != plain_output(save.task):
        raise ValueError(f"{save_path(save.task)} belongs to another task")
    saved[save.direction.value] = [plain_output(entry) for entry in save.entries]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(saved, indent=1), encoding="utf-8")
    across = [build_output(entry, Entry) for entry in saved.get("across", [])]
    down = [build_output(entry, Entry) for entry in saved.get("down", [])]
    return SaveOutput(
        file=save_path(save.task),
        across=len(across),
        down=len(down),
        complete="across" in saved and "down" in saved,
        entries=ordered(across + down),
    )


def pin_numbering(task: GridInput, workspace: Path) -> PinOutput:
    rows = grid_rows(task)
    return PinOutput(grid_sha256=canonical_sha256(rows), rows=rows, entries=ordered(number(rows)))

