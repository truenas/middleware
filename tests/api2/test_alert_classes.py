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
                },
            },
        })

    assert ve.value.errors[0].attribute == "alert_class_update.classes.Invalid"


def test__disable_proactive_support_for_valid_alert_class():
    call("alertclasses.update", {
        "classes": {
            "ZpoolCapacityNotice": {
                "proactive_support": False,
            },
        },
    })


def test__disable_proactive_support_for_invalid_alert_class():
    with pytest.raises(ValidationErrors) as ve:
        call("alertclasses.update", {
            "classes": {
                "UPSBatteryLow": {
                    "proactive_support": False,
                },
            },
        })

    assert ve.value.errors[0].attribute == "alert_class_update.classes.UPSBatteryLow.proactive_support"
