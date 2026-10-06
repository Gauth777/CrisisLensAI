from __future__ import annotations

import json

from crisislens import doctor
from crisislens.schemas import CrisisInput
from test_api import StubProvider


def sample():
    return CrisisInput(location="Velachery", report="Synthetic demo: waterlogging has stopped traffic near the MRTS.")


def test_doctor_runs_validated_pipeline(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "private-key")
    monkeypatch.setattr(doctor, "build_provider", lambda name: StubProvider())
    result = doctor.probe("gemini", sample())
    assert result["status"] == "ready"
    assert result["schema_validated"] is True
    assert result["location"] == "Velachery"
    assert "private-key" not in json.dumps(result)


def test_doctor_rejects_location_mismatch(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "private-key")
    monkeypatch.setattr(doctor, "build_provider", lambda name: StubProvider())
    result = doctor.probe("gemini", CrisisInput(location="Tambaram", report="Synthetic demo: road waterlogging."))
    assert result["status"] == "failed"


def test_doctor_reports_conflicts_without_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=file-private-key\nOPENAI_MODEL=file-model\n")
    monkeypatch.setenv("OPENAI_API_KEY", "shell-private-key")
    monkeypatch.setenv("OPENAI_MODEL", "shell-model")
    report = doctor.environment_report(env_file)
    assert report["shell_overrides_env_file"] == ["OPENAI_API_KEY", "OPENAI_MODEL"]
    assert "private-key" not in json.dumps(report)


def test_doctor_hides_raw_exception(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "private-key")
    def fail(name):
        raise RuntimeError("private-key private report")
    monkeypatch.setattr(doctor, "build_provider", fail)
    result = doctor.probe("openai", sample())
    assert result["category"] == "unexpected"
    assert "private-key" not in json.dumps(result)
    assert "private report" not in json.dumps(result)


def test_doctor_missing_key_does_not_call_provider(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(doctor, "build_provider", lambda name: (_ for _ in ()).throw(AssertionError()))
    assert doctor.probe("openai", sample())["status"] == "missing_key"


def test_doctor_exit_requires_real_success(monkeypatch, capsys):
    monkeypatch.setattr(doctor, "load_environment", lambda: None)
    monkeypatch.setattr(doctor, "probe", lambda name, data: {"status": "failed"})
    assert doctor.main([]) == 1
    assert "NO LIVE PROVIDER VERIFIED" in capsys.readouterr().out


def test_explicit_env_file_option_only_changes_this_process(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=file-private-key\n")
    (tmp_path / "sample_data").mkdir()
    (tmp_path / "sample_data/crisis_examples.json").write_text(json.dumps({"demo": sample().model_dump()}))
    monkeypatch.setattr(doctor, "ENV_FILE", env_file)
    monkeypatch.setattr(doctor, "environment_report", lambda: {"shell_overrides_env_file": []})
    monkeypatch.setattr(doctor, "load_environment", lambda: None)
    monkeypatch.setenv("OPENAI_API_KEY", "shell-private-key")
    def probe(name, data):
        assert name == "openai"
        assert doctor.os.environ["OPENAI_API_KEY"] == "file-private-key"
        return {"status": "ready"}
    monkeypatch.setattr(doctor, "probe", probe)
    assert doctor.main(["--provider", "openai", "--env-file-only"]) == 0
    assert env_file.read_text() == "OPENAI_API_KEY=file-private-key\n"
