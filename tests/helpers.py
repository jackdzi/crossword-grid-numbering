from __future__ import annotations

from pathlib import Path

from scripted_agent import numbering_from_grid
from slimconfig import build_output, plain_output

from contract import GridInput, NumberingOutput, PinOutput, SaveInput
from plugin import get_grid, pin_numbering, save_entries


def as_sandbox(value, cls):
    """A value as NanoAgent's verifier sandbox hands it over: rebuilt from its JSON."""
    return build_output(plain_output(value) if not isinstance(value, dict) else value, cls)


def task(seed: int = 7, size: str = "9x9", symmetric: bool = True) -> GridInput:
    return build_output({"seed": seed, "size": size, "symmetric": symmetric}, GridInput)


def gold_run(given: GridInput, workspace: Path) -> tuple[NumberingOutput, PinOutput]:
    """A correct run through the real tools: get_grid, two save_entries, and the submitted output."""
    grid = get_grid(given, workspace)
    across, down = numbering_from_grid(grid.rows, grid.columns)
    save_entries(build_output({"task": plain_output(given), "direction": "across", "entries": across}, SaveInput), workspace)
    saved = save_entries(build_output({"task": plain_output(given), "direction": "down", "entries": down}, SaveInput), workspace)
    output = as_sandbox({"entries": [plain_output(e) for e in saved.entries]}, NumberingOutput)
    reference = as_sandbox(pin_numbering(given, workspace), PinOutput)
    return output, reference
