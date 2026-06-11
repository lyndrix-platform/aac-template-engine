# tests/test_processors.py
import pytest
import os
import yaml
from manifest_generator.processors.imports import ImportProcessor
from manifest_generator.processors.networks import NetworkProcessor
from manifest_generator.processors.volumes import VolumeProcessor
from manifest_generator.processors.ports import PortProcessor
from manifest_generator.processors.environment import EnvironmentProcessor

@pytest.fixture
def temp_engine_dir(tmp_path):
    """Creates a mock template engine structure with a catalog."""
    catalog_dir = tmp_path / "catalog"
    catalog_dir.mkdir()
    
    # Create a mock MariaDB blueprint
    mariadb_blueprint = {
        "image_repo": "mariadb",
        "restart_policy": "always",
        "volumes": {
            "db": {
                "type": "bind",
                "target": "/var/lib/mysql"
            }
        }
    }
    
    blueprint_file = catalog_dir / "mariadb.yml"
    blueprint_file.write_text(yaml.dump(mariadb_blueprint))
    
    return str(tmp_path)

def test_import_processor_merges_correctly(temp_engine_dir):
    """Verifies that the ImportProcessor correctly merges SSoT overrides onto Catalog DNA."""
    # 1. Setup Mock Context mimicking a downstream service.yml
    mock_context = {
        "service": {"name": "aac-test-app"},
        "dependencies": {
            "database": {
                "import": "catalog/mariadb.yml",
                "overrides": {
                    "image_tag": "10.11",
                    "environment": {
                        "MARIADB_DATABASE": "test_db"
                    }
                }
            }
        }
    }
    
    # 2. Execute Processor
    processor = ImportProcessor(temp_engine_dir)
    result = processor.process(mock_context)
    
    # 3. Assertions (The Unvarnished Truth Checks)
    db_dep = result["dependencies"]["database"]
    
    # Did it pull the repo from the catalog?
    assert db_dep["image_repo"] == "mariadb"
    # Did it apply the tag from the overrides?
    assert db_dep["image_tag"] == "10.11"
    # Did it pull the volume shape from the catalog?
    assert "db" in db_dep["volumes"]
    # Did it apply the environment from the overrides?
    assert db_dep["environment"]["MARIADB_DATABASE"] == "test_db"

def test_volume_processor_prevents_hijack():
    """Verifies that dependency volumes correctly nest under the main application's root directory."""
    # 1. Setup Mock Context post-import
    mock_context = {
        "service": {"name": "aac-nextcloud"},
        "deployments": {
            "docker_compose": {
                "host_base_path": "/export/docker",
                "volumes": ["html:/var/www/html"] # Main explicitly requests only HTML
            }
        },
        "volumes": { # Global definition
            "html": {"type": "bind", "target": "/var/www/html"}
        },
        "dependencies": {
            "database": {
                "name": "aac-nextcloud-db",
                "volumes": { # Dependency explicitly requests DB
                    "db": {"type": "bind", "target": "/var/lib/mysql"}
                }
            }
        }
    }

    # 2. Execute Processor
    processor = VolumeProcessor()
    result = processor.process(mock_context)

    # 3. Assertions
    main_vols = result["processed_volumes"]
    dep_vols = result["dependencies"]["database"]["processed_volumes"]

    # Ensure the main service volume path is correct
    assert len(main_vols) == 1
    assert "/export/docker/aac-nextcloud/html:/var/www/html" in main_vols
    
    # Ensure Database volume correctly nests under the MAIN application folder
    assert len(dep_vols) == 1
    assert "/export/docker/aac-nextcloud/db:/var/lib/mysql" in dep_vols


def test_network_processor_merges_dependency_networks_to_join():
    """Verifies dependency networks_to_join are merged into processed_networks."""
    mock_context = {
        "service": {"name": "aac-test-app"},
        "deployments": {
            "docker_compose": {}
        },
        "dependencies": {
            "database": {
                "networks_to_join": ["secured", "stack_internal"]
            }
        }
    }

    processor = NetworkProcessor()
    result = processor.process(mock_context)

    dep_networks = result["dependencies"]["database"]["processed_networks"]

    assert dep_networks == ["secured", "stack_internal"]


def test_import_processor_normalizes_compose_style_dependency(temp_engine_dir):
    """Compose-style dependency keys should be normalized into engine schema."""
    mock_context = {
        "service": {"name": "aac-openweb-ui"},
        "dependencies": {
            "kokoro-tts": {
                "image": "ghcr.io/remsky/kokoro-fastapi-gpu:latest",
                "container_name": "kokoro-tts",
                "ports": ["8880:8880"],
                "environment": ["USE_GPU=true"],
                "restart": "unless-stopped"
            }
        }
    }

    importer = ImportProcessor(temp_engine_dir)
    result = importer.process(mock_context)
    dep = result["dependencies"]["kokoro-tts"]

    assert dep["name"] == "kokoro-tts"
    assert dep["image_repo"] == "ghcr.io/remsky/kokoro-fastapi-gpu"
    assert dep["image_tag"] == "latest"
    assert dep["restart_policy"] == "unless-stopped"
    assert dep["environment"]["USE_GPU"] == "true"

    ports_result = PortProcessor().process(result)
    assert ports_result["dependencies"]["kokoro-tts"]["processed_ports"] == ["8880:8880/tcp"]


def test_environment_processor_keeps_dependency_env_out_of_global_files():
    """Dependency env vars must not spill into global .env/stack.env outputs."""
    mock_context = {
        "environment": {
            "MAIN_ONLY": "ok",
            "OPENAI_API_KEY": "main-secret"
        },
        "dependencies": {
            "sidecar": {
                "environment": {
                    "DB_CONNECTION_URI": "postgres://sidecar-only"
                }
            }
        },
        "deployments": {
            "docker_compose": {}
        }
    }

    result = EnvironmentProcessor().process(mock_context)

    assert result["processed_env"]["MAIN_ONLY"] == "ok"
    assert result["processed_secrets"]["OPENAI_API_KEY"] == "main-secret"
    assert "DB_CONNECTION_URI" not in result["processed_env"]
    assert "DB_CONNECTION_URI" not in result["processed_secrets"]