import yaml
from fastapi.testclient import TestClient

from hestia.app import app


def test_get_config_endpoint_reads_yaml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "hestia_config.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "semaphore_base_url": "http://localhost:3000",
                "services": {
                    "ollama": {
                        "base_url": "http://localhost:11434",
                        "warmup_ms": 0,
                        "idle_timeout_ms": 0,
                    }
                },
            },
            sort_keys=False,
        )
    )

    client = TestClient(app)
    response = client.get("/api/v1/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configPath"] == "hestia_config.yml"
    assert payload["config"]["services"]["ollama"]["base_url"] == "http://localhost:11434"


def test_put_config_endpoint_persists_valid_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "hestia_config.yml"
    config_path.write_text("services:\n  ollama:\n    base_url: http://localhost:11434\n")

    client = TestClient(app)
    new_config = {
        "config": {
            "semaphore_base_url": "http://semaphore.local:3000",
            "services": {
                "ollama": {
                    "base_url": "http://127.0.0.1:11434",
                    "retry_count": 2,
                    "retry_delay_ms": 250,
                    "warmup_ms": 10,
                    "idle_timeout_ms": 5000,
                    "queue_size": 50,
                    "request_timeout_seconds": 45,
                    "semaphore_enabled": False,
                },
                "simple-fastapi": {
                    "base_url": "http://localhost:7123",
                    "retry_count": 1,
                    "retry_delay_ms": 500,
                    "warmup_ms": 0,
                    "idle_timeout_ms": 60000,
                    "queue_size": 10,
                    "request_timeout_seconds": 60,
                    "semaphore_enabled": True,
                    "semaphore_machine_id": "homelab",
                    "semaphore_start_template_id": 2,
                    "semaphore_stop_template_id": 3,
                    "semaphore_task_timeout": 60,
                    "semaphore_poll_interval": 5.0,
                },
            },
        }
    }

    response = client.put("/api/v1/config", json=new_config)
    assert response.status_code == 200
    assert response.json()["message"] == "Configuration updated"

    persisted = yaml.safe_load(config_path.read_text())
    assert persisted["services"]["simple-fastapi"]["base_url"] == "http://localhost:7123"
    assert persisted["semaphore_base_url"] == "http://semaphore.local:3000"


def test_put_config_endpoint_rejects_invalid_payload(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hestia_config.yml").write_text(
        "services:\n  ollama:\n    base_url: http://localhost:11434\n"
    )

    client = TestClient(app)
    invalid_config = {
        "config": {
            "services": {
                "ollama": {
                    "base_url": "http://localhost:11434",
                    "retry_count": -1,
                }
            }
        }
    }

    response = client.put("/api/v1/config", json=invalid_config)
    assert response.status_code == 422
    assert "Invalid configuration" in response.json()["message"]
