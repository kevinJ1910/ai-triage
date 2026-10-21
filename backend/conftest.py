import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache():
    # La cache en memoria persiste entre tests: sin limpiarla, los contadores de throttling
    # (login 10/min, OTP 5/min) y la cache clinica se arrastrarian de un test a otro.
    cache.clear()
    yield
