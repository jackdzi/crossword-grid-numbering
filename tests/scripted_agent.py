"""A scripted stand-in for the agent: it follows the task's instructions with no model, so a whole
run can be replayed offline. It sees only the batch of runs each tool call returns."""

from __future__ import annotations


def number_batch(runs: list[dict], last: int, before: tuple[dict, int] | None = None) -> tuple[list[int], int]:
    """The numbers of one batch of runs, and the last number used. ``before`` is the run just before
    the batch, with its number (the end of the previous batch)."""
    numbers = []
    previous = before
    for run in runs:
        if run["length"] == 1:
            number = 0
        elif previous and (previous[0]["row"], previous[0]["col"]) == (run["row"], run["col"]) and previous[1] > 0:
            number = previous[1]
        else:
            last += 1
            number = last
        numbers.append(number)
        previous = (run, number)
    return numbers, last
