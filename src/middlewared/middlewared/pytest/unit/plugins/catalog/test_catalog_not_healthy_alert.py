import json
from unittest.mock import MagicMock, mock_open, patch

from middlewared.alert.source.catalogs import CatalogNotHealthyAlert
from middlewared.api.current import CatalogApps
from middlewared.plugins.catalog.apps_details import retrieve_trains_data_from_json

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


def read_trains(context, catalog, options, healthy=True, train_names=("community",), catalog_data=None):
    with (
        patch("middlewared.plugins.catalog.apps_details.retrieve_train_names", return_value=list(train_names)),
        patch("middlewared.plugins.catalog.apps_details.json_schema_validate"),
        patch("builtins.open", mock_open(read_data=catalog_data or catalog_json(healthy))),
    ):
        return retrieve_trains_data_from_json(context, catalog, options)


def test_a_read_that_yields_nothing_leaves_the_alert_alone():
    context = MagicMock()

    assert read_trains(context, make_catalog(), CatalogApps(retrieve_all_trains=True), train_names=()) == {}

    assert alert_calls(context, "oneshot_delete") == []
    assert alert_calls(context, "oneshot_create") == []


def test_a_train_carrying_no_apps_still_clears_the_alert():
    context = MagicMock()
    catalog = make_catalog()

    data = read_trains(
        context,
        catalog,
        CatalogApps(retrieve_all_trains=True),
        catalog_data=json.dumps({"community": {}}),
    )

    # An empty train is the catalog telling us it ships no apps there, not a failed read
    assert data == {"community": {}}
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
