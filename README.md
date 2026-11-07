# Crossword Grid Numbering

A `nanoagent.plugin/v0001` plugin. Its task, `number-grid`, gives an agent a
crossword grid (5x5 to 11x11, black cells free or with rotational symmetry)
and asks for its numbering: every across and down entry with its clue number,
first cell and length, by the standard rule. The grid comes from a seed, so
every task can be rebuilt exactly, and a deterministic verifier numbers the
grid again with its own algorithm and checks every entry.

## Tools

| Tool | Does | Code |
|---|---|---|
| `get_grid` | The task's grid as rows and as columns (`.` white, `#` black), its size, its number of black cells and white runs, and the first batch of runs (at most 25): every maximal run of white cells, across and down, single cells included, in reading order | `src/plugin/grid.py` |
| `save_numbers` | Saves the numbers of one batch of runs (each run's clue number, or 0 for a single cell) into `crossword/<size>-<shape>-<seed>.json` in the workspace, and returns every number saved so far, where the next batch starts and the next batch of runs | `src/plugin/grid.py` |
| `pin_numbering` | The answer key: the grid, its sha256 and its correct numbering | `src/plugin/grid.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `number-grid` | Numbers the grid's across and down entries, saves them, and submits them | `agent`, with `get_grid` and `save_numbers`; reference `pin_numbering` |

## The task

Input: `seed` (0 to 1,000,000,000), `size` (`5x5`, `7x7`, `9x9` or `11x11`)
and `symmetric`. The agent calls `get_grid`, then `save_numbers` once per
batch of at most 25 runs (one to three batches), then `submit` with every
number saved. The answer is one number per white run: the run's clue number,
or 0 for a single cell, which is no entry.

The tool finds the runs; the agent applies the numbering rule to them. This
split keeps each step within RUSH Lab's default limits (replies of at most
2,048 tokens, reasoning included, and 6 steps): asked to scan a 9x9 grid
itself, DeepSeek V4 Flash spent the whole reply reasoning and never answered.
A grid has at most 74 runs, so at most three batches, and `submit` comes by
the fifth step.

The rule: reading row by row, a white cell that starts an across or a down
run of 2 or more white cells gets the next number, from 1. A cell starting
both entries has one number. A lone white cell is no entry.

## Ground truth and verification

The grid is drawn by a sha256-based generator (`src/plugin/rng.py`), never
`random`, so a seed gives the same grid on every machine. One seed in ten has
no black cell, one an all-black row and one an all-black column.

`verify_task` (in `verifier/grid.py`):

1. Rebuilds the grid from the seed with its own copy of the generator, and
   checks that the pinned answer key holds that grid (by sha256) and its
   numbering.
2. Numbers the grid its own way, by splitting each row and column on black
   cells, rather than the tool's cell-by-cell scan.
3. Compares the number of every run, and names each run numbered wrong
   (a single cell given a number, an entry given 0, a number off by one) and
   any run missing or extra.
4. Checks that the saved file in the workspace holds exactly the submitted
   numbers.

The verdict is valid only when every run is right and saved; its score is
the share of runs that are right (at most 0.5 when the saved file does not
match). `verify_input` refuses a batch that does not start where the last
ended, has more than 25 numbers, runs past the grid, or has a negative
number.

## Layout

```text
.
├── nanoagent.yaml   # manifest: id, runtime, permissions (no network), tools, task
├── contract.py      # each tool's and task's typed input and output
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # environment variable names needed (none)
├── src/plugin/      # the MCP server (__main__.py), the generator (rng.py) and the tools (grid.py)
├── tests/           # the verifier's tests, tool tests, a 2,000-grid agreement test, an MCP smoke
│                    #   test, and a scripted no-model agent (scripted_agent.py)
├── ui/              # renderers.js and renderers.css: outputs drawn from their JSON Schema
├── product/         # the product page: product.yaml and icon.svg
└── verifier/        # the deterministic verifier: grid.py, its generator copy rng.py, checks.py
```

## Develop and run

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

No network and no data files: every grid comes from its seed. NanoAgent
passes the folder the plugin may write to as `NANOAGENT_WORKSPACE`.
