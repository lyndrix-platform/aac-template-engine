"""render_files: `.j2` sources are rendered, everything else is copied verbatim."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from manifest_generator.engine import ManifestEngine  # noqa: E402


def test_render_files_renders_j2_and_copies_raw_assets(tmp_path, monkeypatch):
    svc = tmp_path / "svc"
    files = svc / "custom_templates" / "files"
    (files / "config").mkdir(parents=True)
    (files / "icons").mkdir()
    (files / "provisioning" / "dashboards" / "Docker").mkdir(parents=True)
    (files / "config" / "settings.yaml.j2").write_text("name: {{ vars.NAME }}\n")
    (files / "icons" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00raw")
    # Grafana dashboards carry Jinja-looking syntax that must survive untouched
    (files / "provisioning" / "dashboards" / "Docker" / "all.json").write_text(
        '{"legendFormat": "{{name}} ({{host}})", "expr": "up{job=\\"$job\\"}"}'
    )

    monkeypatch.chdir(tmp_path)
    ManifestEngine(str(tmp_path / "tpl"), str(svc)).render_files({"vars": {"NAME": "x"}})

    out = tmp_path / "deployments" / "files"
    assert (out / "config" / "settings.yaml").read_text().strip() == "name: x"
    assert not (out / "config" / "settings.yaml.j2").exists()
    assert (out / "icons" / "logo.png").read_bytes() == b"\x89PNG\r\n\x1a\n\x00raw"
    dash = (out / "provisioning" / "dashboards" / "Docker" / "all.json").read_text()
    assert "{{name}} ({{host}})" in dash and '"$job"' in dash
