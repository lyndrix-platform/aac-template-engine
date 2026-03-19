# tests/test_processors.py
import pytest
import os
import yaml
from manifest_generator.processors.imports import ImportProcessor
from manifest_generator.processors.volumes import VolumeProcessor

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
    """Verifies that main services and dependencies get strictly isolated volume paths."""
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

    # Ensure Nextcloud did NOT hijack the database volume
    assert len(main_vols) == 1
    assert "/export/docker/aac-nextcloud/html:/var/www/html" in main_vols
    
    # Ensure Database got its own isolated path
    assert len(dep_vols) == 1
    assert "/export/docker/aac-nextcloud-db/db:/var/lib/mysql" in dep_vols