from middlewared.alert.base import AlertCategory, alert_category_names


def test_alert_category_names():
    assert all([category in alert_category_names for category in AlertCategory])
