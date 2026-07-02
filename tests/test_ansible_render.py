# tests/test_ansible_render.py
"""Render-level guards for the 'ansible' (native) deployment type.

The engine renders a GLOBAL `entrypoint.yml` (from templates/ansible/) and
copies the service role tree VERBATIM: nested dirs preserved, the role's own
runtime `.j2` templates NOT engine-rendered, and service `custom_templates/
ansible/` overriding the engine defaults.
"""
import sys
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "scripts"))

from manifest_generator.engine import ManifestEngine  # noqa: E402


def _context():
    return {
        "config": {"schema_version": 2},
        "service": {"name": "aac-demo"},
        "vars": {},
        "secrets": {},
        "deployments": {"ansible": {}},
    }


def test_ansible_render_emits_entrypoint_and_role(tmp_path, monkeypatch):
    service_dir = tmp_path / "svc"
    service_dir.mkdir()
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.chdir(out_dir)

    ManifestEngine(str(_REPO), str(service_dir)).render_ansible(_context())

    base = out_dir / "deployments" / "ansible"

    # Global entrypoint: engine-rendered (.j2 stripped) and mentions the service.
    entry = base / "entrypoint.yml"
    assert entry.is_file()
    entry_text = entry.read_text()
    assert "aac-demo" in entry_text
    assert "{{" not in entry_text  # no unrendered engine jinja left behind
    yaml.safe_load(entry_text)  # valid YAML

    # Role skeleton copied verbatim, nested dirs preserved.
    role = base / "roles" / "service"
    main = role / "tasks" / "main.yml"
    assert main.is_file()
    assert (role / "tasks" / "install.yml").is_file()
    assert (role / "tasks" / "uninstall.yml").is_file()
    assert (role / "defaults" / "main.yml").is_file()

    # Role tasks are VERBATIM => Ansible runtime jinja survives unrendered.
    assert "{{ service.name }}" in main.read_text()
    yaml.safe_load(main.read_text())  # still valid YAML


def test_ansible_service_overrides_and_runtime_templates_verbatim(tmp_path, monkeypatch):
    service_dir = tmp_path / "svc"

    # Service overrides install.yml with real steps ...
    tasks_dir = service_dir / "custom_templates" / "ansible" / "roles" / "service" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "install.yml").write_text(
        "---\n- name: real install\n  ansible.builtin.debug:\n    msg: hi\n"
    )
    # ... and ships an Ansible runtime template (must stay a .j2 with live jinja).
    tmpl_dir = service_dir / "custom_templates" / "ansible" / "roles" / "service" / "templates"
    tmpl_dir.mkdir(parents=True)
    (tmpl_dir / "app.conf.j2").write_text("host = {{ vars.DB_HOST }}\n")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.chdir(out_dir)

    ManifestEngine(str(_REPO), str(service_dir)).render_ansible(_context())

    base = out_dir / "deployments" / "ansible"

    # Service override wins over the engine default skeleton.
    assert "real install" in (base / "roles" / "service" / "tasks" / "install.yml").read_text()

    # Runtime template copied verbatim: extension AND jinja intact (NOT rendered).
    runtime_tmpl = base / "roles" / "service" / "templates" / "app.conf.j2"
    assert runtime_tmpl.is_file()
    assert runtime_tmpl.read_text() == "host = {{ vars.DB_HOST }}\n"

    # Engine defaults not overridden by the service are still present.
    assert (base / "roles" / "service" / "tasks" / "uninstall.yml").is_file()
    assert (base / "entrypoint.yml").is_file()
