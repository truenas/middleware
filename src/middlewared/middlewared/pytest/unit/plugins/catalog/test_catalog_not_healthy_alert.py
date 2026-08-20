import json
from unittest.mock import MagicMock, mock_open, patch

import pytest

from middlewared.alert.source.catalogs import CatalogNotHealthyAlert
from middlewared.api.current import CatalogApps
from middlewared.plugins.catalog.apps_details import get_trains, retrieve_trains_data_from_json

LOCATION = "/mnt/tank/ix-apps/catalogs/TRUENAS"


def make_catalog():
    catalog = MagicMock()
    catalog.id = "CUSTOM"
    # Anything other than the official label keeps the recommended apps lookup out of the way
    catalog.label = "CUSTOM"
    catalog.location = LOCATION
    return catalog


def catalog_json(healthy=True):
    return json.dumps({"community": {"actual-budget": {"healthy": healthy, "last_update": None}}})


def alert_calls(context, method):
    return [
        call.args[1:]
        for call in context.middleware.call_sync2.call_args_list
        if call.args[0] is getattr(context.middleware.services.alert, method)
    ]


def read_trains(context, catalog, options, healthy=True):
    with (
        patch("middlewared.plugins.catalog.apps_details.retrieve_train_names", return_value=["community"]),
        patch("middlewared.plugins.catalog.apps_details.json_schema_validate"),
        patch("builtins.open", mock_open(read_data=catalog_json(healthy))),
    ):
        return retrieve_trains_data_from_json(context, catalog, options)


def test_healthy_all_trains_read_clears_the_alert():
    context = MagicMock()
    catalog = make_catalog()

    read_trains(context, catalog, CatalogApps(retrieve_all_trains=True))

    assert alert_calls(context, "oneshot_delete") == [("CatalogNotHealthy", catalog.label)]
    assert alert_calls(context, "oneshot_create") == []


def test_partial_train_read_leaves_the_alert_alone():
    context = MagicMock()

    read_trains(context, make_catalog(), CatalogApps(retrieve_all_trains=False, trains=["community"]))

    assert alert_calls(context, "oneshot_delete") == []
    assert alert_calls(context, "oneshot_create") == []


def test_unhealthy_app_raises_the_alert_instead_of_clearing_it():
    context = MagicMock()

    read_trains(context, make_catalog(), CatalogApps(retrieve_all_trains=True), healthy=False)

    assert alert_calls(context, "oneshot_delete") == []
    created = alert_calls(context, "oneshot_create")
    assert len(created) == 1
    assert isinstance(created[0][0], CatalogNotHealthyAlert)


@pytest.mark.parametrize("catalog_json_exists", [True, False])
def test_unreadable_catalog_never_touches_the_alert(catalog_json_exists):
    context = MagicMock()

    with (
        patch("middlewared.plugins.catalog.apps_details.os.path.exists", return_value=catalog_json_exists),
        patch(
            "middlewared.plugins.catalog.apps_details.retrieve_trains_data_from_json",
            side_effect=json.JSONDecodeError("Expecting value", "", 0),
        ),
    ):
        assert get_trains(context, make_catalog(), CatalogApps(retrieve_all_trains=True)) == {}

    context.middleware.call_sync2.assert_not_called()
