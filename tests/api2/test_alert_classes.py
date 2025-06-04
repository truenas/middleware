from unittest.mock import ANY

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.utils import call


def test__normal_alert_class():
    value = {
        "classes": {
            "UPSBatteryLow": {
                "level": "CRITICAL",
                "policy": "IMMEDIATELY",
                "proactive_support": False,
            },
        },
    }

    call("alertclasses.update", value)

    assert call("alertclasses.config") == {"id": ANY, **value}


def test__nonexisting_alert_class():
    with pytest.raises(ValidationErrors) as ve:
        call("alertclasses.update", {
            "classes": {
                "Invalid": {
                    "level": "WARNING",
                    "policy": "IMMEDIATELY",
                },
            },
        })

    assert ve.value.errors[0].attribute == "alert_class_update.classes.Invalid"


def test__enable_proactive_support_for_valid_alert_class(request):
    call("alertclasses.update", {
        "classes": {
            "ZpoolCapacityNotice": {
                "level": "WARNING",
                "policy": "IMMEDIATELY",
                "proactive_support": True,
            },
        },
    })


def test__enable_proactive_support_for_invalid_alert_class(request):
    with pytest.raises(ValidationErrors) as ve:
        call("alertclasses.update", {
            "classes": {
                "UPSBatteryLow": {
                    "level": "WARNING",
                    "policy": "IMMEDIATELY",
                    "proactive_support": True,
                },
            },
        })

    assert ve.value.errors[0].attribute == "alert_class_update.classes.UPSBatteryLow.proactive_support"
