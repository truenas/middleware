import time
from unittest.mock import ANY

import pytest

from middlewared.test.integration.utils import call, mock

pytestmark = pytest.mark.disk


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


def test_disk_temperature_alerts():
    sda_temperature_alert = {
        "uuid": "a11a16a9-a28b-4005-b11a-bce6af008d86",
        "source": "",
        "klass": "SMART",
        "args": {
            "device": "/dev/sda",
            "message": "Device: /dev/sda, Temperature 60 Celsius reached critical limit of 50 Celsius (Min/Max 25/63)"
        },
        "node": "Controller A",
        "key": "{\"device\": \"/dev/sda\", \"message\": \"Device: /dev/sda, Temperature 60 Celsius reached critical limit of 50 Celsius (Min/Max 25/63)\"}",
        "datetime": {
            "$date": 1657098825510
        },
        "last_occurrence": {
            "$date": 1657185226656
        },
        "dismissed": False,
        "mail": None,
        "text": "%(message)s.",
        "id": "a11a16a9-a28b-4005-b11a-bce6af008d86",
        "level": "CRITICAL",
        "formatted": "Device: /dev/sda, Temperature 60 Celsius reached critical limit of 50 Celsius (Min/Max 25/63).",
        "one_shot": True,
    }
    sdb_temperature_alert = {
        "uuid": "66e29e1c-2948-4473-928a-3ccf0c0aefa9",
        "source": "",
        "klass": "SMART",
        "args": {
            "device": "/dev/sdb",
            "message": "Device: /dev/sdb, Temperature 60 Celsius reached critical limit of 50 Celsius (Min/Max 25/63)"
        },
        "node": "Controller A",
        "key": "{\"device\": \"/dev/sdb\", \"message\": \"Device: /dev/sdb, Temperature 60 Celsius reached critical limit of 50 Celsius (Min/Max 25/63)\"}",
        "datetime": {
            "$date": 1657098825510
        },
        "last_occurrence": {
            "$date": 1657185226656
        },
        "dismissed": False,
        "mail": None,
        "text": "%(message)s.",
        "id": "a11a16a9-a28b-4005-b11a-bce6af008d86",
        "level": "CRITICAL",
        "formatted": "Device: /dev/sdb, Temperature 60 Celsius reached critical limit of 50 Celsius (Min/Max 25/63).",
        "one_shot": True,
    }
    unrelated_alert = {
        "uuid": "c371834a-5168-474d-a6d0-9eac02ad29a7",
        "source": "",
        "klass": "ScrubStarted",
        "args": "temp",
        "node": "Controller A",
        "key": "\"temp\"",
        "datetime": {
            "$date": 1657713495028
        },
        "last_occurrence": {
            "$date": 1657713495028
        },
        "dismissed": False,
        "mail": None,
        "text": "Scrub of pool %r started.",
        "id": "c371834a-5168-474d-a6d0-9eac02ad29a7",
        "level": "INFO",
        "formatted": "Scrub of pool 'temp' started.",
        "one_shot": True,
    }

    with mock("alert.list", return_value=[sda_temperature_alert, sdb_temperature_alert, unrelated_alert]):
        assert call("disk.temperature_alerts", ["sda"]) == [dict(sda_temperature_alert,
                                                                 datetime=ANY,
                                                                 last_occurrence=ANY)]
