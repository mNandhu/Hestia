import pytest
from pydantic import ValidationError

from hestia.config import HestiaConfig, load_config


def test_load_config_from_yaml_file(tmp_path):
    config_file = tmp_path / "hestia_config.yml"
    config_file.write_text("""
services:
  ollama:
    base_url: "http://yaml-configured:11434"
    retry_count: 3
    retry_delay_ms: 100
    health_url: "http://yaml-configured:11434/health"
    warmup_ms: 500
    idle_timeout_ms: 30000
    fallback_url: "http://yaml-fallback:11434"
""")

    config = load_config(str(config_file))

    assert config.services["ollama"].base_url == "http://yaml-configured:11434"
    assert config.services["ollama"].retry_count == 3
    assert config.services["ollama"].retry_delay_ms == 100
    assert config.services["ollama"].health_url == "http://yaml-configured:11434/health"
    assert config.services["ollama"].warmup_ms == 500
    assert config.services["ollama"].idle_timeout_ms == 30000
    assert config.services["ollama"].fallback_url == "http://yaml-fallback:11434"


def test_env_overrides_yaml_config(tmp_path, monkeypatch):
    config_file = tmp_path / "hestia_config.yml"
    config_file.write_text("""
services:
  ollama:
    base_url: "http://yaml-configured:11434"
    retry_count: 3
""")

    # Environment variables should override YAML
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://env-override:11434")
    monkeypatch.setenv("OLLAMA_RETRY_COUNT", "5")

    config = load_config(str(config_file))

    assert config.services["ollama"].base_url == "http://env-override:11434"
    assert config.services["ollama"].retry_count == 5


def test_config_validation_errors():
    # Test with invalid retry_count (negative)
    with pytest.raises(ValidationError):
        HestiaConfig(services={"ollama": {"retry_count": -1}})

    # Test with invalid idle_timeout_ms (negative)
    with pytest.raises(ValidationError):
        HestiaConfig(services={"ollama": {"idle_timeout_ms": -100}})


def test_missing_config_file_uses_defaults(monkeypatch):
    # Point to non-existent file
    config = load_config("/non/existent/config.yml")

    # Should use defaults
    assert config.services["ollama"].base_url == "http://localhost:11434"
    assert config.services["ollama"].retry_count == 1
    assert config.services["ollama"].retry_delay_ms == 0
    assert config.services["ollama"].health_url is None
    assert config.services["ollama"].warmup_ms == 0
    assert config.services["ollama"].idle_timeout_ms == 0
    assert config.services["ollama"].fallback_url is None


def test_env_vars_only_no_yaml(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://env-only:11434")
    monkeypatch.setenv("OLLAMA_HEALTH_URL", "http://env-only:11434/health")
    monkeypatch.setenv("OLLAMA_IDLE_TIMEOUT_MS", "15000")

    config = load_config("/non/existent/config.yml")

    assert config.services["ollama"].base_url == "http://env-only:11434"
    assert config.services["ollama"].health_url == "http://env-only:11434/health"
    assert config.services["ollama"].idle_timeout_ms == 15000
