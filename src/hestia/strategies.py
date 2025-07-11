"""
Strategy execution module for Hestia.

This module is responsible for dynamically loading and executing
user-defined routing strategies.
"""

import importlib.util
import sys
from typing import Any, Dict, List


def execute_strategy(script_path: str, context: Dict[str, Any]) -> List[str]:
    """
    Dynamically loads a Python module and executes its 'decide_route' function.

    Args:
        script_path: The absolute path to the Python strategy script.
        context: A dictionary containing request and state data to be passed
                 to the strategy function.

    Returns:
        A list of URLs as determined by the strategy.

    Raises:
        FileNotFoundError: If the script_path does not exist.
        AttributeError: If the script does not have a 'decide_route' function.
        Exception: For any errors during the execution of the strategy.
    """
    try:
        spec = importlib.util.spec_from_file_location("strategy_module", script_path)
        if spec is None:
            raise FileNotFoundError(f"Strategy script not found at: {script_path}")

        strategy_module = importlib.util.module_from_spec(spec)
        if spec.loader is None:
            raise ImportError(f"Could not get loader for strategy {script_path}")

        sys.modules["strategy_module"] = strategy_module
        spec.loader.exec_module(strategy_module)
    except FileNotFoundError:
        raise FileNotFoundError(f"Strategy script not found at: {script_path}")

    if not hasattr(strategy_module, "decide_route"):
        raise AttributeError(
            f"Strategy script '{script_path}' must define a 'decide_route' function."
        )

    try:
        return strategy_module.decide_route(context)
    except Exception as e:
        # TODO: Add more specific error handling and logging
        print(f"Error executing strategy '{script_path}': {e}")
        raise
