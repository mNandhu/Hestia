import threading
from typing import Dict, Callable, List
import importlib.util
import os
import sys


class StrategyRegistry:
    """Thread-safe singleton registry for strategy plugins."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_registry()
        return cls._instance

    def _init_registry(self):
        """Initialize the registry data structures."""
        self._strategies: Dict[str, Callable] = {}
        self._registry_lock = threading.RLock()

    def register(self, name: str, strategy: Callable) -> None:
        """Register a strategy with the given name."""
        with self._registry_lock:
            if name in self._strategies:
                raise ValueError(f"Strategy '{name}' already registered")
            self._strategies[name] = strategy

    def get_strategy(self, name: str) -> Callable:
        """Get a strategy by name."""
        with self._registry_lock:
            if name not in self._strategies:
                raise KeyError(f"Strategy '{name}' not found")
            return self._strategies[name]

    def list_strategies(self) -> List[str]:
        """List all registered strategy names."""
        with self._registry_lock:
            return list(self._strategies.keys())

    def clear(self) -> None:
        """Clear all registered strategies (mainly for testing)."""
        with self._registry_lock:
            self._strategies.clear()


def load_strategies(strategies_dir: str) -> None:
    """Load strategy plugins from a directory."""
    registry = StrategyRegistry()

    if not os.path.exists(strategies_dir):
        return

    if not os.path.isdir(strategies_dir):
        return

    # Add the parent directory to sys.path temporarily
    parent_dir = os.path.dirname(strategies_dir)
    strategies_package_name = os.path.basename(strategies_dir)

    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
        path_added = True
    else:
        path_added = False

    try:
        # Scan for Python files in the strategies directory
        for filename in os.listdir(strategies_dir):
            if not filename.endswith(".py") or filename.startswith("__"):
                continue

            module_name = filename[:-3]  # Remove .py extension
            full_module_name = f"{strategies_package_name}.{module_name}"
            module_path = os.path.join(strategies_dir, filename)

            try:
                # Load the module
                spec = importlib.util.spec_from_file_location(full_module_name, module_path)
                if spec is None or spec.loader is None:
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Check if the module has a register_strategy function
                if hasattr(module, "register_strategy"):
                    try:
                        module.register_strategy(registry)
                    except Exception as e:
                        print(f"Warning: Failed to register strategies from {filename}: {e}")

            except Exception as e:
                print(f"Warning: Failed to load strategy module {filename}: {e}")
                continue

    finally:
        # Remove the parent directory from sys.path if we added it
        if path_added:
            sys.path.remove(parent_dir)
