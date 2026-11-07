"""The tools, the independent oracle, and the MCP server."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import anyio
import pytest
from helpers import task
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from plugin import get_grid, pin_numbering
from plugin.grid import grid_rows, number
from verifier.grid import rebuild_rows, true_entries

ROOT = Path(__file__).resolve().parents[1]


def test_a_grid_is_the_same_for_the_same_seed() -> None:
    assert grid_rows(task(seed=5)) == grid_rows(task(seed=5))
    assert grid_rows(task(seed=5)) != grid_rows(task(seed=6))


def test_symmetric_grids_are_symmetric() -> None:
    for seed in range(30):
        rows = grid_rows(task(seed=seed, size="11x11", symmetric=True))
        assert rows == ["".join(reversed(row)) for row in reversed(rows)]


def test_a_known_grid_is_numbered_by_hand() -> None:
    rows = ["..#..", ".....", "#...#", ".....", "..#.."]
    got = {(e.direction.value, e.row, e.col): (e.number, e.length) for e in number(rows)}
    assert got == {
        ("across", 0, 0): (1, 2), ("down", 0, 0): (1, 2),
        ("down", 0, 1): (2, 5),
        ("across", 0, 3): (3, 2), ("down", 0, 3): (3, 5),
        ("down", 0, 4): (4, 2),
        ("across", 1, 0): (5, 5),
        ("down", 1, 2): (6, 3),
        ("across", 2, 1): (7, 3),
        ("across", 3, 0): (8, 5), ("down", 3, 0): (8, 2),
        ("down", 3, 4): (9, 2),
        ("across", 4, 0): (10, 2),
        ("across", 4, 3): (11, 2),
    }


def test_a_grid_without_black_cells_has_one_entry_per_row_and_column() -> None:
    entries = number(["....."] * 5)
    assert len(entries) == 10 and max(e.number for e in entries) == 9


def test_the_tool_and_the_verifier_agree_on_2000_grids() -> None:
    for seed in range(500):
        for size in ("5x5", "7x7", "9x9", "11x11"):
            given = task(seed=seed, size=size, symmetric=seed % 3 == 0)
            rows = grid_rows(given)
            assert rows == rebuild_rows(given)
            ours = {(e.direction.value, e.row, e.col): (e.number, e.length) for e in number(rows)}
            assert ours == true_entries(rows), (seed, size)


def test_save_numbers_saves_batches_in_order(tmp_path: Path) -> None:
    from helpers import save

    given = task(seed=930, size="11x11", symmetric=True)
    pinned = pin_numbering(given, tmp_path).numbers
    first = save(given, 0, pinned[:25], tmp_path)
    assert (first.next_start, first.complete, len(first.next_runs)) == (25, False, 25)
    with pytest.raises(ValueError, match="next batch starts at 25"):
        save(given, 30, pinned[30:55], tmp_path)
    save(given, 25, pinned[25:50], tmp_path)
    last = save(given, 50, pinned[50:], tmp_path)
    assert last.complete and last.numbers == pinned and last.next_runs == []
    on_disk = json.loads((tmp_path / last.file).read_text())
    assert on_disk["numbers"] == pinned and len(on_disk["entries"]) == sum(1 for n in pinned if n)


def test_a_first_batch_restarts_the_numbering(tmp_path: Path) -> None:
    from helpers import save

    given = task()
    save(given, 0, [0] * len(get_grid(given, tmp_path).runs), tmp_path)
    again = save(given, 0, [1], tmp_path)
    assert again.numbers == [1]


def test_runs_list_every_white_run_in_reading_order() -> None:
    from plugin.grid import white_runs

    runs = white_runs(["..#", "...", "#.."])
    assert [(r.direction.value, r.row, r.col, r.length) for r in runs] == [
        ("across", 0, 0, 2), ("down", 0, 0, 2), ("down", 0, 1, 3),
        ("across", 1, 0, 3), ("down", 1, 2, 2), ("across", 2, 1, 2),
    ]


def test_get_grid_gives_rows_and_columns(tmp_path: Path) -> None:
    grid = get_grid(task(), tmp_path)
    assert all(grid.columns[c][r] == grid.rows[r][c] for r in range(grid.size) for c in range(grid.size))


def test_the_mcp_server_lists_and_runs_every_tool(tmp_path: Path) -> None:
    async def run() -> None:
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "plugin"], cwd=str(ROOT), env={**os.environ, "NANOAGENT_WORKSPACE": str(tmp_path)}
        )
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert names == {"get_grid", "save_numbers", "pin_numbering"}
            given = {"seed": 1, "size": "5x5", "symmetric": True}
            grid = await session.call_tool("get_grid", given)
            assert not grid.isError and len(grid.structuredContent["rows"]) == 5
            pinned = await session.call_tool("pin_numbering", given)
            assert not pinned.isError and pinned.structuredContent["entries"]
            bad = await session.call_tool("get_grid", {"seed": 1, "size": "6x6", "symmetric": True})
            assert bad.isError

    anyio.run(run)
