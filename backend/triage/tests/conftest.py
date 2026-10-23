import pytest


@pytest.fixture(autouse=True)
def _raw_dir_in_tmp(tmp_path, monkeypatch):
    # Los comandos de evaluacion escriben checkpoints en benchmark/resultados/crudos: en las pruebas, a tmp.
    raw = tmp_path / 'crudos'
    monkeypatch.setattr('triage.evaluation_runner.RAW_DIR', raw)
    monkeypatch.setattr('triage.management.commands.evaluate_extraction.RAW_DIR', raw)
    monkeypatch.setattr('triage.management.commands.evaluate_benchmark.RAW_DIR', raw)
    return raw
