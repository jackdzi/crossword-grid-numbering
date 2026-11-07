"""The deterministic verifier: each tool's checks, and the task's, on contract instances."""

from contract import Task, Tool

from . import grid

# tool -> (verify_input(value), verify_output(input_value, output_value, workspace))
TOOLS = {
    Tool.GET_GRID: (grid.verify_grid_input, lambda given, made, workspace: grid.verify_get_output(given, made)),
    Tool.SAVE_NUMBERS: (grid.verify_numbers_input, grid.verify_numbers_output),
    Tool.PIN_NUMBERING: (grid.verify_grid_input, lambda given, made, workspace: grid.verify_pin_output(given, made)),
}
# task -> its output's check, verify_task(arguments, output, reference, workspace)
TASKS = {Task.NUMBER_GRID: grid.verify_task}


def verify_input(tool, value):
    return TOOLS[Tool(tool)][0](value)


def verify_output(tool, input_value, output_value, workspace):
    return TOOLS[Tool(tool)][1](input_value, output_value, workspace)


def verify_task(task, arguments, output, reference, workspace):
    return TASKS[Task(task)](arguments, output, reference, workspace)
