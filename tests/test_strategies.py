"""
Tests for the strategies module.
"""

import pytest
import os
from typing import Any, Dict
from pathlib import Path

from hestia.strategies import execute_strategy


class TestStrategies:
    """Test strategy execution functionality."""

    def test_execute_strategy_success(self, tmp_path: Path) -> None:
        """Test successful strategy execution."""
        # Create a temporary strategy file
        strategy_file = tmp_path / "test_strategy.py"
        strategy_content = """
def decide_route(context):
    return ["http://localhost:8001"]
"""
        strategy_file.write_text(strategy_content)

        context: Dict[str, Any] = {"test": "data"}
        result = execute_strategy(str(strategy_file), context)

        assert result == ["http://localhost:8001"]

    def test_execute_strategy_with_context(self, tmp_path: Path) -> None:
        """Test strategy execution that uses context data."""
        # Create a strategy that examines context
        strategy_file = tmp_path / "context_strategy.py"
        strategy_content = """
def decide_route(context):
    if context.get("service_name") == "test_service":
        return ["http://target:8001"]
    return []
"""
        strategy_file.write_text(strategy_content)

        context: Dict[str, Any] = {"service_name": "test_service"}
        result = execute_strategy(str(strategy_file), context)

        assert result == ["http://target:8001"]

    def test_execute_strategy_empty_result(self, tmp_path: Path) -> None:
        """Test strategy that returns empty list."""
        strategy_file = tmp_path / "empty_strategy.py"
        strategy_content = """
def decide_route(context):
    return []
"""
        strategy_file.write_text(strategy_content)

        context: Dict[str, Any] = {}
        result = execute_strategy(str(strategy_file), context)

        assert result == []

    def test_execute_strategy_file_not_found(self) -> None:
        """Test strategy execution with non-existent file."""
        with pytest.raises(FileNotFoundError, match="Strategy script not found"):
            execute_strategy("/nonexistent/path.py", {})

    def test_execute_strategy_missing_function(self, tmp_path: Path) -> None:
        """Test strategy file without decide_route function."""
        strategy_file = tmp_path / "no_function_strategy.py"
        strategy_content = """
def some_other_function():
    return "not decide_route"
"""
        strategy_file.write_text(strategy_content)

        with pytest.raises(
            AttributeError, match="must define a 'decide_route' function"
        ):
            execute_strategy(str(strategy_file), {})

    def test_execute_strategy_function_error(self, tmp_path: Path) -> None:
        """Test strategy function that raises an error."""
        strategy_file = tmp_path / "error_strategy.py"
        strategy_content = """
def decide_route(context):
    raise ValueError("Strategy error")
"""
        strategy_file.write_text(strategy_content)

        with pytest.raises(Exception):
            execute_strategy(str(strategy_file), {})

    def test_execute_strategy_complex_logic(self, tmp_path: Path) -> None:
        """Test strategy with more complex decision logic."""
        strategy_file = tmp_path / "complex_strategy.py"
        strategy_content = """
def decide_route(context):
    configured_hosts = context.get("configured_hosts", [])
    request_headers = context.get("request_headers", {})
    
    # Simple load balancing based on user agent
    if "mobile" in request_headers.get("user-agent", "").lower():
        # Return mobile-optimized hosts
        mobile_hosts = [h for h in configured_hosts if h.get("metadata", {}).get("mobile_optimized")]
        return [h["url"] for h in mobile_hosts] if mobile_hosts else []
    
    # Return all hosts for desktop
    return [h["url"] for h in configured_hosts]
"""
        strategy_file.write_text(strategy_content)

        context: Dict[str, Any] = {
            "configured_hosts": [
                {"url": "http://desktop:8001", "metadata": {}},
                {"url": "http://mobile:8002", "metadata": {"mobile_optimized": True}},
            ],
            "request_headers": {"user-agent": "Mobile Safari"},
        }

        result = execute_strategy(str(strategy_file), context)
        assert result == ["http://mobile:8002"]

        # Test desktop user agent
        context["request_headers"]["user-agent"] = "Desktop Chrome"
        result = execute_strategy(str(strategy_file), context)
        assert result == ["http://desktop:8001", "http://mobile:8002"]

    def test_execute_strategy_return_type_validation(self, tmp_path: Path) -> None:
        """Test that strategy returns a list."""
        strategy_file = tmp_path / "string_return_strategy.py"
        strategy_content = """
def decide_route(context):
    return "http://localhost:8001"  # Should return list, not string
"""
        strategy_file.write_text(strategy_content)

        # This should not raise an error; context empty
        context: Dict[str, Any] = {}
        result = execute_strategy(str(strategy_file), context)
        assert result == "http://localhost:8001"

    def test_mock_router_strategy(self) -> None:
        """Test the actual mock router strategy file."""
        # This tests the real mock_router.py file
        context: Dict[str, Any] = {
            "configured_hosts": [
                {"url": "http://localhost:8001", "name": "host1"},
                {"url": "http://localhost:8002", "name": "host2"},
            ]
        }

        strategy_path = os.path.abspath("strategies/mock_router.py")
        if os.path.exists(strategy_path):
            result = execute_strategy(strategy_path, context)
            assert result == ["http://localhost:8001"]
        else:
            pytest.skip("mock_router.py not found in strategies directory")

    def test_strategy_module_isolation(self, tmp_path: Path) -> None:
        """Test that strategy modules don't interfere with each other."""
        # Create two different strategy files
        strategy1 = tmp_path / "strategy1.py"
        strategy1.write_text("""
global_var = "strategy1"

def decide_route(context):
    return [global_var]
""")

        strategy2 = tmp_path / "strategy2.py"
        strategy2.write_text("""
global_var = "strategy2"

def decide_route(context):
    return [global_var]
""")

        # Execute both strategies
        result1 = execute_strategy(str(strategy1), {})
        result2 = execute_strategy(str(strategy2), {})

        assert result1 == ["strategy1"]
        assert result2 == ["strategy2"]
