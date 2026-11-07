"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    GET_GRID = "get_grid"
    SAVE_NUMBERS = "save_numbers"
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
RUNS = (
    "The first batch of runs (at most 25) of the grid's runs list: every maximal run of white cells, across and "
    "down, single cells included, ordered by first cell (row, then column), across before down"
)


@dataclass
class GridInput(Output):
    seed: Annotated[int, "Which grid: any integer from 0 to 1000000000; the same seed always gives the same grid"]
    size: Annotated[GridSize, "The grid's size: 5x5, 7x7, 9x9 or 11x11"]
    symmetric: Annotated[bool, "true: black cells are placed with 180-degree rotational symmetry"]


@dataclass
class Run(Output):
    direction: Annotated[Direction, "across (along a row) or down (along a column)"]
    row: Annotated[int, "The run's first cell's row, 0 for the top row"]
    col: Annotated[int, "The run's first cell's column, 0 for the leftmost column"]
    length: Annotated[int, "How many white cells the run spans, 1 or more"]


@dataclass
class GridOutput(Output):
    size: Annotated[int, "The number of rows, which equals the number of columns"]
    rows: Annotated[list[str], ROWS]
    columns: Annotated[list[str], COLUMNS]
    black_cells: Annotated[int, "How many cells are black"]
    total_runs: Annotated[int, "How many white runs the grid has, single cells included"]
    runs: Annotated[list[Run], RUNS]


@dataclass
class Entry(Output):
    number: Annotated[int, "The clue number of the entry's first cell"]
    direction: Annotated[Direction, "across (left to right) or down (top to bottom)"]
    row: Annotated[int, "The first cell's row, 0 for the top row"]
    col: Annotated[int, "The first cell's column, 0 for the leftmost column"]
    length: Annotated[int, "How many white cells the entry spans, at least 2"]


NUMBERS = (
    "One number per run of get_grid's runs list, in that order: the clue number of the entry the run is, or 0 for a "
    "run of a single cell, which is no entry"
)


@dataclass
class NumbersInput(Output):
    task: Annotated[GridInput, TASK]
    start: Annotated[int, "The index in the runs list of this batch's first run: 0 for the first batch, then the next_start the last call returned"]
    numbers: Annotated[list[int], "One number per run of this batch, in order (at most 25): the run's clue number, or 0 for a single cell"]


@dataclass
class NumbersOutput(Output):
    file: Annotated[str, "The saved numbering, relative to the workspace"]
    runs: Annotated[int, "How many runs the grid has"]
    next_start: Annotated[int, "The index of the first run not yet numbered: the next batch's start"]
    complete: Annotated[bool, "true once every run is numbered"]
    last_number: Annotated[int, "The highest number saved so far"]
    numbers: Annotated[list[int], "Every number saved so far, one per run from the first, in order"]
    next_runs: Annotated[list[Run], "The next batch of runs (at most 25), from next_start; empty once complete"]


@dataclass
class NumberingOutput(Output):
    numbers: Annotated[list[int], "The numbers save_numbers saved: one per run of get_grid's runs list, in order"]


@dataclass
class PinOutput(Output):
    grid_sha256: Annotated[str, "sha256 of the grid's rows as canonical JSON"]
    rows: Annotated[list[str], ROWS]
    numbers: Annotated[list[int], "The correct number of each run of the runs list, 0 for single cells"]
    entries: Annotated[list[Entry], "The grid's correct numbering as entries, ordered by number, across before down"]


TOOLS = {
    Tool.GET_GRID: (GridInput, GridOutput),
    Tool.SAVE_NUMBERS: (NumbersInput, NumbersOutput),
    Tool.PIN_NUMBERING: (GridInput, PinOutput),
}
TASKS = {Task.NUMBER_GRID: (GridInput, NumberingOutput)}
