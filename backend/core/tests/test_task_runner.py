from types import SimpleNamespace

import pytest
from celery.exceptions import TimeoutError as CeleryTimeoutError
from kombu.exceptions import OperationalError

from config.celery import app
from core.task_runner import TaskUnavailable, run_task


@app.task
def _sum_task(a, b):
    return a + b


@app.task
def _failing_task():
    raise ValueError("fallo clinico de la tarea")


class TestRunTask:
    def test_eager_mode_returns_task_result(self):
        assert run_task(_sum_task, 2, 3, timeout=5) == 5

    def test_task_exceptions_propagate(self):
        with pytest.raises(ValueError):
            run_task(_failing_task, timeout=5)

    def test_broker_down_raises_task_unavailable(self, mocker):
        mocker.patch.object(_sum_task, "apply_async", side_effect=OperationalError("Connection refused"))
        with pytest.raises(TaskUnavailable):
            run_task(_sum_task, 1, 1, timeout=5)

    def test_worker_timeout_raises_task_unavailable(self, mocker):
        def _get(timeout):
            raise CeleryTimeoutError()
        mocker.patch.object(_sum_task, "apply_async", return_value=SimpleNamespace(get=_get))
        with pytest.raises(TaskUnavailable):
            run_task(_sum_task, 1, 1, timeout=1)

    def test_task_expires_with_the_wait_timeout(self, mocker):
        apply_async = mocker.patch.object(
            _sum_task, "apply_async", return_value=SimpleNamespace(get=lambda timeout: 7)
        )
        assert run_task(_sum_task, 3, 4, timeout=42) == 7
        assert apply_async.call_args.kwargs["expires"] == 42
