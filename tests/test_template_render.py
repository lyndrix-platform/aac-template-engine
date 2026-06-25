# tests/test_template_render.py
"""Render-level guard for the docker-compose template.

Regression for: an empty ``deployments.docker_compose.environment: {}`` used to
emit a bare ``environment:`` key (YAML null), which docker compose rejects with
``services.<svc>.environment must be a mapping``. The template must OMIT the key
when the env dict is empty, and emit it normally when populated.
"""
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "docker_compose"


def _render(env_block: dict) -> dict:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["to_yaml"] = lambda d, indent=2: yaml.dump(
        d, indent=indent, default_flow_style=False, sort_keys=False
    )
    ctx = {
        "config": {"schema_version": 2},
        "service": {"name": "aac-demo", "image_repo": "demo/img", "image_tag": "1.0"},
        "processed_specs": {},
        "processed_ports": [],
        "processed_volumes": [],
        "processed_networks": [],
        "processed_env": {},
        "processed_secrets": {},
        "deployments": {"docker_compose": {"environment": env_block}},
        "dependencies": {},
        "network_definitions": {},
    }
    out = env.get_template("docker-compose.yml.j2").render(ctx)
    return yaml.safe_load(out)  # also asserts the output is valid YAML


def test_empty_environment_is_omitted():
    parsed = _render({})
    svc = parsed["services"]["aac-demo"]
    # No bare `environment:` (which would parse to None and fail compose validation).
    assert "environment" not in svc


def test_populated_environment_is_a_mapping():
    parsed = _render({"PUID": "{{ vars.PUID }}", "TZ": "Europe/Berlin"})
    svc = parsed["services"]["aac-demo"]
    assert isinstance(svc["environment"], dict)
    assert svc["environment"]["TZ"] == "Europe/Berlin"
