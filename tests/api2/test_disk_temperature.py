import time

import pytest

from middlewared.test.integration.utils import call, mock

from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


@pytest.fixture(autouse=True, scope="function")
def reset_temperature_cache():
    call("disk.reset_temperature_cache")


def test_disk_temperature():
    with mock("disk.temperature_uncached", return_value=50):
        assert call("disk.temperature", "sda") == 50


def test_disk_temperature_cache():
    with mock("disk.temperature_uncached", return_value=50):
        call("disk.temperature", "sda")

    with mock("disk.temperature_uncached", exception=True):
        assert call("disk.temperature", "sda", {"cache": 300}) == 50


def test_disk_temperature_cache_expires():
    with mock("disk.temperature_uncached", return_value=50):
        call("disk.temperature", "sda")

    time.sleep(3)

    with mock("disk.temperature_uncached", return_value=60):
        assert call("disk.temperature", "sda", {"cache": 2}) == 60


def test_disk_temperatures_only_cached():
    with mock("disk.temperature_uncached", return_value=50):
        call("disk.temperature", "sda")

    with mock("disk.temperature_uncached", exception=True):
        assert call("disk.temperatures", ["sda"], {"only_cached": True}) == {"sda": 50}
