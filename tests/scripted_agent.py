"""A scripted stand-in for the agent: it follows the task's instructions with no model, so a whole
run can be replayed offline. It reads only what get_grid returns."""

from __future__ import annotations


def numbering_from_grid(rows: list[str], columns: list[str]) -> tuple[list[dict], list[dict]]:
    """The across and down entries, found the way the instructions describe."""
    n = len(rows)

    def white(r: int, c: int) -> bool:
        return 0 <= r < n and 0 <= c < n and rows[r][c] == "."

    across, down, number = [], [], 0
    for r in range(n):
        for c in range(n):
            starts_across = white(r, c) and not white(r, c - 1) and white(r, c + 1)
            starts_down = white(r, c) and not white(r - 1, c) and white(r + 1, c)
            if not (starts_across or starts_down):
                continue
            number += 1
            if starts_across:
                length = len(rows[r][c:].split("#")[0])
                across.append({"number": number, "direction": "across", "row": r, "col": c, "length": length})
            if starts_down:
                length = len(columns[c][r:].split("#")[0])
                down.append({"number": number, "direction": "down", "row": r, "col": c, "length": length})
    return across, down
