"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    GET_GRID = "get_grid"
    SAVE_ENTRIES = "save_entries"
    PIN_NUMBERING = "pin_numbering"


class Task(Enum):
    NUMBER_GRID = "number-grid"


class GridSize(Enum):
    S5 = "5x5"
    S7 = "7x7"
    S9 = "9x9"
    S11 = "11x11"


class Direction(Enum):
    ACROSS = "across"
    DOWN = "down"


ROWS = "The grid's rows, top to bottom; in each, '.' is a white cell and '#' a black one, left to right"
COLUMNS = "The grid's columns, left to right; in each, '.' is a white cell and '#' a black one, top to bottom"
TASK = "The task input, copied exactly as given"


@dataclass
class GridInput(Output):
    seed: Annotated[int, "Which grid: any integer from 0 to 1000000000; the same seed always gives the same grid"]
    size: Annotated[GridSize, "The grid's size: 5x5, 7x7, 9x9 or 11x11"]
    symmetric: Annotated[bool, "true: black cells are placed with 180-degree rotational symmetry"]


@dataclass
class GridOutput(Output):
    size: Annotated[int, "The number of rows, which equals the number of columns"]
    rows: Annotated[list[str], ROWS]
    columns: Annotated[list[str], COLUMNS]
    black_cells: Annotated[int, "How many cells are black"]


@dataclass
class Entry(Output):
    number: Annotated[int, "The clue number of the entry's first cell"]
    direction: Annotated[Direction, "across (left to right) or down (top to bottom)"]
    row: Annotated[int, "The first cell's row, 0 for the top row"]
    col: Annotated[int, "The first cell's column, 0 for the leftmost column"]
    length: Annotated[int, "How many white cells the entry spans, at least 2"]


@dataclass
class SaveInput(Output):
    task: Annotated[GridInput, TASK]
    direction: Annotated[Direction, "Which direction's entries this call saves; it replaces any saved before for it"]
    entries: Annotated[list[Entry], "Every entry in that direction, each with that direction"]


@dataclass
class SaveOutput(Output):
    file: Annotated[str, "The saved numbering, relative to the workspace"]
    across: Annotated[int, "How many across entries are saved"]
    down: Annotated[int, "How many down entries are saved"]
    complete: Annotated[bool, "true once both directions are saved"]
    entries: Annotated[list[Entry], "Every saved entry, ordered by number, across before down"]


@dataclass
class NumberingOutput(Output):
    entries: Annotated[list[Entry], "Every entry of the grid, as the last save_entries call returned them"]


@dataclass
class PinOutput(Output):
    grid_sha256: Annotated[str, "sha256 of the grid's rows as canonical JSON"]
    rows: Annotated[list[str], ROWS]
    entries: Annotated[list[Entry], "The grid's correct numbering, ordered by number, across before down"]


TOOLS = {
    Tool.GET_GRID: (GridInput, GridOutput),
    Tool.SAVE_ENTRIES: (SaveInput, SaveOutput),
    Tool.PIN_NUMBERING: (GridInput, PinOutput),
}
TASKS = {Task.NUMBER_GRID: (GridInput, NumberingOutput)}
