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
| `get_grid` | The task's grid as rows and as columns (`.` white, `#` black), its size and its number of black cells | `src/plugin/grid.py` |
| `save_entries` | Saves every across or every down entry into `crossword/<size>-<shape>-<seed>.json` in the workspace, replacing that direction's earlier save, and returns all entries saved so far | `src/plugin/grid.py` |
| `pin_numbering` | The answer key: the grid, its sha256 and its correct numbering | `src/plugin/grid.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `number-grid` | Numbers the grid's across and down entries, saves them, and submits them | `agent`, with `get_grid` and `save_entries`; reference `pin_numbering` |

## The task

Input: `seed` (0 to 1,000,000,000), `size` (`5x5`, `7x7`, `9x9` or `11x11`)
and `symmetric`. The agent makes four tool calls: `get_grid`, `save_entries`
for the across entries, `save_entries` for the down entries, and `submit`
with the entries the last save returned.

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
3. Compares every submitted entry by its direction and first cell, and lists
   each one missing, extra, given twice, or with a wrong number or length.
4. Checks that the saved file in the workspace holds exactly the submitted
   entries.

The verdict is valid only when every entry is right and saved; its score is
the share of entries that are right. `verify_input` refuses a save with an
entry of the other direction, outside the grid, of length below 2, or given
twice.

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
