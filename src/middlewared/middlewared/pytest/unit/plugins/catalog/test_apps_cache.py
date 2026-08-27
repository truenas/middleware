from unittest.mock import MagicMock, patch

from middlewared.api.current import CatalogApps
from middlewared.plugins.catalog.apps_details import apps
from middlewared.plugins.catalog.utils import get_cache_key

LOCATION = "/mnt/tank/ix-apps/catalogs/TRUENAS"
CACHE_KEY = get_cache_key("TRUENAS", LOCATION)

MISSING = object()


def catalog_app(name="actual-budget"):
    return {
        "app_readme": None,
        "categories": ["finance"],
        "description": "Personal finance manager",
        "healthy": True,
        "healthy_error": None,
        "home": "https://actualbudget.org",
        "location": f"{LOCATION}/trains/community/{name}",
        "latest_version": "1.1.13",
        "latest_app_version": "24.10.1",
        "latest_human_version": "24.10.1_1.1.13",
        "last_update": None,
        "name": name,
        "recommended": False,
        "title": name,
        "maintainers": [],
        "tags": [],
        "screenshots": [],
        "sources": [],
        "icon_url": None,
    }


def make_context(cached=MISSING):
    context = MagicMock()
    catalog = MagicMock()
    catalog.id = "TRUENAS"
    catalog.label = "TRUENAS"
    catalog.location = LOCATION
    context.call_sync2.return_value = catalog

    def call_sync(method, *args):
        if method == "cache.get":
            if cached is MISSING:
                raise KeyError(args[0])
            return cached
        return None

    context.middleware.call_sync.side_effect = call_sync
    return context


def called_methods(context):
    return [call.args[0] for call in context.middleware.call_sync.call_args_list]


@patch("middlewared.plugins.catalog.apps_details.get_trains")
@patch("middlewared.plugins.catalog.apps_details.os.path.exists", return_value=True)
def test_empty_cached_entry_is_treated_as_a_miss(exists, get_trains):
    # An empty mapping is the absence of an answer, so it must not short-circuit the disk read the
    # way a populated entry does
    get_trains.return_value = {"community": {"actual-budget": catalog_app()}}
    context = make_context(cached={})

    result = apps(context, CatalogApps(cache=True, retrieve_all_trains=True))

    assert list(result.root) == ["community"]
    assert ("cache.get", CACHE_KEY) in [call.args for call in context.middleware.call_sync.call_args_list]


def test_populated_cached_entry_is_a_hit():
    context = make_context(cached={"community": {"actual-budget": catalog_app()}})

    result = apps(context, CatalogApps(cache=True, cache_only=True))

    assert list(result.root) == ["community"]
    assert result.root["community"].root["actual-budget"].name == "actual-budget"
    assert "cache.put" not in called_methods(context)


@patch("middlewared.plugins.catalog.apps_details.get_trains", return_value={})
@patch("middlewared.plugins.catalog.apps_details.os.path.exists", return_value=True)
def test_empty_train_data_is_never_cached(exists, get_trains):
    context = make_context()

    assert apps(context, CatalogApps(cache=True, retrieve_all_trains=True)).root == {}

    assert "cache.put" not in called_methods(context)


@patch("middlewared.plugins.catalog.apps_details.get_trains")
@patch("middlewared.plugins.catalog.apps_details.os.path.exists", return_value=True)
def test_populated_train_data_is_cached_under_a_location_aware_key(exists, get_trains):
    trains = {"community": {"actual-budget": catalog_app()}}
    get_trains.return_value = trains
    context = make_context()

    apps(context, CatalogApps(cache=True, retrieve_all_trains=True))

    put = [call.args for call in context.middleware.call_sync.call_args_list if call.args[0] == "cache.put"]
    assert put == [("cache.put", CACHE_KEY, trains, 90000)]
