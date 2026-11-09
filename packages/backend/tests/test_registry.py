import pytest

from hestia.services.registry import Registry, RegistryError


def test_loads_services_with_defaults(tmp_path):
    f = tmp_path / "hestia.yml"
    f.write_text(
        "services:\n  ollama:\n    upstream: http://h:11434/\n    health_path: api/tags\n"
    )
    s = Registry.load(f).get("ollama")
    assert s.upstream_base == "http://h:11434"
    assert s.health_path == "/api/tags"
    assert s.timeouts.connect_s == 10 and s.timeouts.read_s == 600


def test_empty_file_is_empty_registry(tmp_path):
    f = tmp_path / "hestia.yml"
    f.write_text("")
    assert Registry.load(f).all() == []


@pytest.mark.parametrize(
    "data, match",
    [
        ({"services": {"Bad_ID": {"upstream": "http://h"}}}, "invalid service id"),
        ({"services": {"a": {"upstream": "http://h", "typo_field": 1}}}, "service 'a'"),
        ({"services": {"a": {"upstream": "not a url"}}}, "service 'a'"),
        ({"services": {"a": {}}}, "service 'a'"),
        ({"services": ["a"]}, "must be a mapping"),
    ],
)
def test_rejects_invalid(data, match):
    with pytest.raises(RegistryError, match=match):
        Registry.from_dict(data)


def test_missing_file(tmp_path):
    with pytest.raises(RegistryError, match="not found"):
        Registry.load(tmp_path / "nope.yml")


def test_non_mapping_top_level(tmp_path):
    f = tmp_path / "hestia.yml"
    f.write_text("- a\n")
    with pytest.raises(RegistryError, match="top level"):
        Registry.load(f)
