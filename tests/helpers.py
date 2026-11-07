from __future__ import annotations

from pathlib import Path

from scripted_agent import number_batch
from slimconfig import build_output, plain_output

from contract import GridInput, NumberingOutput, NumbersInput, PinOutput
from plugin import get_grid, pin_numbering, save_numbers


def as_sandbox(value, cls):
    """A value as NanoAgent's verifier sandbox hands it over: rebuilt from its JSON."""
    return build_output(plain_output(value) if not isinstance(value, dict) else value, cls)


def task(seed: int = 7, size: str = "9x9", symmetric: bool = True) -> GridInput:
    return build_output({"seed": seed, "size": size, "symmetric": symmetric}, GridInput)


def save(given: GridInput, start: int, numbers: list[int], workspace: Path):
    return save_numbers(build_output({"task": plain_output(given), "start": start, "numbers": numbers}, NumbersInput), workspace)


def gold_run(given: GridInput, workspace: Path) -> tuple[NumberingOutput, PinOutput]:
    """A correct run through the real tools: get_grid, a save_numbers per batch, and the submitted output."""
    grid = plain_output(get_grid(given, workspace))
    runs, start, last, before = grid["runs"], 0, 0, None
    while True:
        numbers, last = number_batch(runs, last, before)
        saved = plain_output(save(given, start, numbers, workspace))
        if saved["complete"]:
            break
        before = (runs[-1], numbers[-1])
        runs, start = saved["next_runs"], saved["next_start"]
    output = as_sandbox({"numbers": saved["numbers"]}, NumberingOutput)
    reference = as_sandbox(pin_numbering(given, workspace), PinOutput)
    return output, reference
