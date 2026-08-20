import contextlib
from typing import Any
import unittest.mock

from middlewared.plugins.apps.ix_apps.query import list_apps, upgrade_available_for_app

QUERY = "middlewared.plugins.apps.ix_apps.query"
# The image every app in this module runs, and the key `list_apps` looks it up under once
# `normalize_reference` has expanded the implicit registry
IMAGE = "actualbudget/actual-server:24.10.1"
IMAGE_TAG = "registry-1.docker.io/actualbudget/actual-server:24.10.1"
VERSION_MAPPING: dict[str, dict[str, dict[str, str | None]]] = {
    "community": {
        "actual-budget": {"version": "1.1.13", "app_version": "24.10.1"},
        "ix-app": {"version": "1.2.0", "app_version": "1.0.0"},
    },
}


def app_metadata(name: str, version: str, custom_app: bool = False) -> dict[str, Any]:
    return {
        "custom_app": custom_app,
        "human_version": f"24.10.1_{version}",
        "metadata": {"name": name, "train": "community", "version": version},
        "migrated": False,
        "portals": {},
        "version": version,
    }


def workload(container_states: list[str]) -> dict[str, Any]:
    return {
        "containers": len(container_states),
        "container_details": [
            {"service_name": f"service-{i}", "image": IMAGE, "state": state, "id": f"container-{i}"}
            for i, state in enumerate(container_states)
        ],
        "images": [IMAGE],
        "used_ports": [],
        "used_host_ips": [],
        "volumes": [],
        "networks": [],
    }


def query_one_app(
    app_name: str,
    metadata: Any,
    container_states: list[str] | None = None,
    image_update_pending: bool = False,
    version_mapping: dict[str, dict[str, dict[str, str | None]]] | None = None,
) -> dict[str, Any]:
    """
    Run ``list_apps`` over a single app with a real ``upgrade_available_for_app``, so that the
    inline ix-app / custom-app override is exercised rather than stubbed out.
    """
    resources = workload(["running"] if container_states is None else container_states)
    with contextlib.ExitStack() as stack:
        stack.enter_context(unittest.mock.patch(f"{QUERY}.get_collective_metadata", return_value={app_name: metadata}))
        stack.enter_context(
            unittest.mock.patch(f"{QUERY}.list_resources_by_project", return_value={f"ix-{app_name}": {}})
        )
        stack.enter_context(
            unittest.mock.patch(f"{QUERY}.translate_resources_to_desired_workflow", return_value=resources)
        )
        scandir = stack.enter_context(unittest.mock.patch("os.scandir"))
        # The app already has docker resources, so there is nothing for the `app_configs` scan to add
        scandir.return_value.__enter__.return_value = []

        apps = list_apps(
            VERSION_MAPPING if version_mapping is None else version_mapping,
            host_ip=None,
            retrieve_config=False,
            image_update_cache={IMAGE_TAG: image_update_pending},
        )

    assert len(apps) == 1
    return apps[0]


def test_catalog_app_behind_the_catalog_reports_an_upgrade():
    app = query_one_app("actual-budget", app_metadata("actual-budget", "1.1.0"))

    assert app["upgrade_available"] is True
    assert app["latest_version"] == "1.1.13"
    assert app["latest_app_version"] == "24.10.1"
    assert app["image_updates_available"] is False


def test_catalog_app_on_the_current_version_reports_no_upgrade():
    app = query_one_app("actual-budget", app_metadata("actual-budget", "1.1.13"))

    assert app["upgrade_available"] is False
    assert app["latest_version"] == "1.1.13"
    assert app["latest_app_version"] == "24.10.1"
    assert app["image_updates_available"] is False


def test_catalog_app_with_no_catalog_data_reports_no_upgrade():
    # An empty version mapping means we do not know what the latest version is, not that the app is
    # current - the app is reported as it stands and nothing claims an upgrade either way
    app = query_one_app("actual-budget", app_metadata("actual-budget", "1.1.0"), version_mapping={})

    assert app["upgrade_available"] is False
    assert app["latest_version"] is None
    assert app["latest_app_version"] is None
    assert app["image_updates_available"] is False


def test_ix_app_with_a_pending_image_update_keeps_its_catalog_version():
    metadata = app_metadata("ix-app", "1.2.0")
    app = query_one_app("ix-app", metadata, image_update_pending=True)

    assert app["upgrade_available"] is True
    assert app["image_updates_available"] is True
    # An ix-app is a catalog app, so the version comparison answers first and answers `False`. The
    # upgrade has to be reported without discarding the catalog version alongside it.
    assert upgrade_available_for_app(VERSION_MAPPING, metadata) == (False, "1.2.0", "1.0.0")
    assert app["latest_version"] == "1.2.0"
    assert app["latest_app_version"] == "1.0.0"


def test_custom_app_with_a_pending_image_update_reports_an_upgrade():
    app = query_one_app("my-app", app_metadata("my-app", "1.0.0", custom_app=True), image_update_pending=True)

    assert app["upgrade_available"] is True
    assert app["image_updates_available"] is True
    assert app["latest_version"] is None
    assert app["latest_app_version"] is None


def test_custom_app_without_a_pending_image_update_reports_no_upgrade():
    app = query_one_app("my-app", app_metadata("my-app", "1.0.0", custom_app=True))

    assert app["upgrade_available"] is False
    assert app["image_updates_available"] is False
    assert app["latest_version"] is None
    assert app["latest_app_version"] is None


def test_stopped_app_reports_no_image_updates():
    # A stopped app has no active workloads to look images up for, so a pending update on an image it
    # used to run cannot flip it to upgradeable
    app = query_one_app(
        "my-app",
        app_metadata("my-app", "1.0.0", custom_app=True),
        container_states=["exited", "exited"],
        image_update_pending=True,
    )

    assert app["state"] == "STOPPED"
    assert app["image_updates_available"] is False
    assert app["upgrade_available"] is False


def test_corrupt_metadata_reports_an_error_state_rather_than_raising():
    app = query_one_app("actual-budget", app_metadata("actual-budget", "1.1.0") | {"metadata": "not a mapping"})

    assert app["state"] == "ERROR"
    assert app["error_reason"] == "METADATA_INCOMPLETE"
    assert app["upgrade_available"] is False
    assert app["latest_version"] is None
    assert app["latest_app_version"] is None
    assert app["image_updates_available"] is False
