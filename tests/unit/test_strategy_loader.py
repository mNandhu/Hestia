import pytest

from hestia.strategy_loader import StrategyRegistry, load_strategies


def test_strategy_registry_singleton():
    """Test that StrategyRegistry is a singleton."""
    reg1 = StrategyRegistry()
    reg2 = StrategyRegistry()
    assert reg1 is reg2


def test_register_strategy():
    """Test registering a strategy."""
    registry = StrategyRegistry()
    registry.clear()  # Clear any existing strategies

    def dummy_strategy():
        return "dummy"

    registry.register("dummy", dummy_strategy)
    assert "dummy" in registry.list_strategies()
    assert registry.get_strategy("dummy") is dummy_strategy


def test_prevent_duplicate_registration():
    """Test that duplicate strategy names are prevented."""
    registry = StrategyRegistry()
    registry.clear()

    def strategy1():
        return "strategy1"

    def strategy2():
        return "strategy2"

    registry.register("test", strategy1)

    with pytest.raises(ValueError, match="Strategy 'test' already registered"):
        registry.register("test", strategy2)


def test_get_nonexistent_strategy():
    """Test getting a strategy that doesn't exist."""
    registry = StrategyRegistry()
    registry.clear()

    with pytest.raises(KeyError, match="Strategy 'nonexistent' not found"):
        registry.get_strategy("nonexistent")


def test_load_strategies_from_directory(tmp_path):
    """Test loading strategies from a directory."""
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir()

    # Create a valid strategy module
    strategy_file = strategies_dir / "test_strategy.py"
    strategy_file.write_text("""
def register_strategy(registry):
    def test_strategy_func():
        return "test_strategy_result"
    
    registry.register("test_strategy", test_strategy_func)
""")

    # Create an __init__.py to make it a package
    (strategies_dir / "__init__.py").write_text("")

    registry = StrategyRegistry()
    registry.clear()

    load_strategies(str(strategies_dir))

    assert "test_strategy" in registry.list_strategies()
    strategy = registry.get_strategy("test_strategy")
    assert strategy() == "test_strategy_result"


def test_load_strategies_ignores_invalid_modules(tmp_path):
    """Test that invalid modules are ignored gracefully."""
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir()

    # Create a valid strategy module
    valid_strategy = strategies_dir / "valid_strategy.py"
    valid_strategy.write_text("""
def register_strategy(registry):
    registry.register("valid", lambda: "valid")
""")

    # Create an invalid strategy module (syntax error)
    invalid_strategy = strategies_dir / "invalid_strategy.py"
    invalid_strategy.write_text("""
def register_strategy(registry):
    this is not valid python syntax!!!
""")

    # Create a module without register_strategy function
    no_register = strategies_dir / "no_register.py"
    no_register.write_text("""
def some_other_function():
    pass
""")

    (strategies_dir / "__init__.py").write_text("")

    registry = StrategyRegistry()
    registry.clear()

    # Should not raise an exception, just skip invalid modules
    load_strategies(str(strategies_dir))

    # Only valid strategy should be loaded
    assert "valid" in registry.list_strategies()
    assert len(registry.list_strategies()) == 1


def test_load_strategies_nonexistent_directory():
    """Test loading from a non-existent directory."""
    registry = StrategyRegistry()
    registry.clear()

    # Should not raise an exception
    load_strategies("/nonexistent/directory")

    # No strategies should be loaded
    assert len(registry.list_strategies()) == 0
