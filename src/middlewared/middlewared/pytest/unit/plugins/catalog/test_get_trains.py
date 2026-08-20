import json
from unittest.mock import MagicMock, patch

from jsonschema import ValidationError as JsonValidationError
import pytest

from middlewared.api.current import CatalogApps
from middlewared.plugins.catalog.apps_details import get_trains


def make_catalog():
    catalog = MagicMock()
    catalog.id = "TRUENAS"
    catalog.label = "TRUENAS"
    catalog.location = "/mnt/tank/ix-apps/catalogs/TRUENAS"
    return catalog


@patch("middlewared.plugins.catalog.apps_details.os.path.exists", return_value=False)
def test_missing_catalog_json_is_logged_and_returns_no_trains(exists):
    context = MagicMock()
    catalog = make_catalog()

    assert get_trains(context, catalog, CatalogApps()) == {}

    context.logger.error.assert_called_once()
    assert catalog.id in context.logger.error.call_args.args


@pytest.mark.parametrize(
    "error",
    [
        json.JSONDecodeError("Expecting value", "", 0),
        JsonValidationError("does not match the catalog schema"),
    ],
)
@patch("middlewared.plugins.catalog.apps_details.retrieve_trains_data_from_json")
@patch("middlewared.plugins.catalog.apps_details.os.path.exists", return_value=True)
def test_unreadable_catalog_json_is_logged_and_returns_no_trains(exists, retrieve, error):
    context = MagicMock()
    catalog = make_catalog()
    retrieve.side_effect = error

    assert get_trains(context, catalog, CatalogApps()) == {}

    context.logger.error.assert_called_once()
    assert catalog.id in context.logger.error.call_args.args


@patch("middlewared.plugins.catalog.apps_details.retrieve_trains_data_from_json")
@patch("middlewared.plugins.catalog.apps_details.os.path.exists", return_value=True)
def test_readable_catalog_json_returns_its_trains(exists, retrieve):
    context = MagicMock()
    retrieve.return_value = {"community": {"actual-budget": {}}}

    assert get_trains(context, make_catalog(), CatalogApps()) == {"community": {"actual-budget": {}}}

    context.logger.error.assert_not_called()
