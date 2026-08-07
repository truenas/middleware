import unittest.mock

import pytest

from middlewared.api.current import AppEntry
from middlewared.plugins.apps.crud import to_app_entry
from middlewared.plugins.apps.ix_apps.query import error_app_data, list_apps, normalize_portal_uris

INCOMPLETE_METADATA = {"version": "1.1.13"}
COMPLETE_METADATA = {
    "custom_app": False,
    "human_version": "24.10.1_1.1.13",
    "metadata": {"name": "actual-budget", "train": "community", "version": "1.1.13"},
    "migrated": False,
    "notes": None,
    "portals": {},
    "version": "1.1.13",
}
METADATA_WITHOUT_DEFAULTS = {k: v for k, v in COMPLETE_METADATA.items() if k not in ("migrated", "notes")}
RESOURCES = {
    "ix-actual-budget": {
        "containers": [
            {
                "Config": {"Labels": {"com.docker.compose.service": "web"}, "Image": "nginx:latest"},
                "State": {"Status": "running"},
                "NetworkSettings": {"Ports": {"80/tcp": [{"HostPort": "8080", "HostIp": "0.0.0.0"}]}},
                "Mounts": [],
                "Id": "abc123",
            }
        ],
        "networks": [],
    }
}


class FakeDirEntry:
    def __init__(self, name):
        self.name = name

    def is_dir(self):
        return True


@pytest.fixture
def query(monkeypatch):
    """Drive `list_apps` with a given collective metadata, docker resources and app_configs listing."""

    def run(collective_metadata, resources=None, config_dirs=(), installing=None, collective_config=None, **kwargs):
        monkeypatch.setattr(
            "middlewared.plugins.apps.ix_apps.query.get_collective_metadata", lambda: collective_metadata
        )
        monkeypatch.setattr(
            "middlewared.plugins.apps.ix_apps.query.get_collective_config", lambda: collective_config or {}
        )
        monkeypatch.setattr(
            "middlewared.plugins.apps.ix_apps.query.list_resources_by_project", lambda **kw: resources or {}
        )
        scandir = unittest.mock.MagicMock()
        scandir.return_value.__enter__.return_value = [FakeDirEntry(name) for name in config_dirs]
        with unittest.mock.patch("os.scandir", scandir):
            return list_apps({}, installing=installing, **kwargs)

    return run


def test_app_with_resources_and_incomplete_metadata_is_reported(query):
    apps = query({"actual-budget": INCOMPLETE_METADATA}, resources=RESOURCES)

    assert len(apps) == 1
    assert apps[0]["state"] == "ERROR"
    assert apps[0]["error_reason"] == "METADATA_INCOMPLETE"
    assert apps[0]["version"] is None
    assert apps[0]["human_version"] is None


def test_app_with_resources_keeps_its_real_workloads(query):
    # Otherwise the ports it is still holding become invisible to conflict detection
    apps = query({"actual-budget": INCOMPLETE_METADATA}, resources=RESOURCES)

    workloads = apps[0]["active_workloads"]
    assert workloads["containers"] == 1
    assert workloads["used_ports"][0]["host_ports"][0]["host_port"] == 8080
    assert workloads["images"] == ["nginx:latest"]


def test_app_missing_from_collective_metadata_is_reported(query, monkeypatch):
    monkeypatch.setattr(
        "middlewared.plugins.apps.ix_apps.query.resolve_app_metadata",
        lambda *args: ({}, "METADATA_UNREADABLE", True),
    )
    apps = query({}, resources=RESOURCES)

    assert [(app["id"], app["state"], app["error_reason"]) for app in apps] == [
        ("actual-budget", "ERROR", "METADATA_UNREADABLE")
    ]


def test_app_whose_own_metadata_is_intact_is_ignored(query, monkeypatch):
    # An install or delete in flight, or a collective metadata file which is itself unreadable
    monkeypatch.setattr("middlewared.plugins.apps.ix_apps.query.resolve_app_metadata", lambda *args: ({}, None, False))

    assert query({}, resources=RESOURCES) == []


def test_stopped_app_with_incomplete_metadata_is_reported(query):
    apps = query({"actual-budget": INCOMPLETE_METADATA}, config_dirs=["actual-budget"])

    assert len(apps) == 1
    assert apps[0]["state"] == "ERROR"
    assert apps[0]["error_reason"] == "METADATA_INCOMPLETE"
    assert apps[0]["active_workloads"]["containers"] == 0
    assert apps[0]["active_workloads"]["used_ports"] == []


def test_stopped_app_without_metadata_is_reported(query, monkeypatch):
    monkeypatch.setattr(
        "middlewared.plugins.apps.ix_apps.metadata.get_app_metadata_checked",
        lambda app_name: ({}, "METADATA_MISSING"),
    )
    apps = query({}, config_dirs=["actual-budget"])

    assert [(app["id"], app["error_reason"]) for app in apps] == [("actual-budget", "METADATA_MISSING")]


def test_stopped_app_without_metadata_is_ignored_while_installing(query, monkeypatch):
    monkeypatch.setattr(
        "middlewared.plugins.apps.ix_apps.metadata.get_app_metadata_checked",
        lambda app_name: ({}, "METADATA_MISSING"),
    )

    assert query({}, config_dirs=["actual-budget"], installing=lambda: {"actual-budget"}) == []


def test_the_job_queue_is_not_walked_for_a_healthy_system(query):
    # Answering what is installing walks every job on the box, and app.query runs constantly
    def installing():
        raise AssertionError("the job queue was walked for an app which could not be mid-install")

    apps = query({"actual-budget": COMPLETE_METADATA}, resources=RESOURCES, installing=installing)

    assert apps[0]["error_reason"] is None


def test_the_job_queue_is_walked_once_for_apps_missing_their_metadata(query, monkeypatch):
    monkeypatch.setattr(
        "middlewared.plugins.apps.ix_apps.metadata.get_app_metadata_checked",
        lambda app_name: ({}, "METADATA_MISSING"),
    )
    asked = []

    def installing():
        asked.append(None)
        return {"app-a"}

    apps = query({}, config_dirs=["app-a", "app-b", "app-c"], installing=installing)

    assert [app["id"] for app in apps] == ["app-b", "app-c"]
    assert len(asked) == 1


def test_healthy_apps_are_unaffected(query):
    apps = query({"actual-budget": COMPLETE_METADATA}, resources=RESOURCES)

    assert apps[0]["state"] == "RUNNING"
    assert apps[0]["error_reason"] is None
    assert apps[0]["version"] == "1.1.13"


@pytest.mark.parametrize(
    "resources,config_dirs,state", [(RESOURCES, (), "RUNNING"), (None, ["actual-budget"], "STOPPED")]
)
def test_metadata_without_the_defaulted_keys_is_usable(query, resources, config_dirs, state):
    # Metadata written by an older release, or hand edited, can be missing these. Checked for a
    # running app and a stopped one, i.e. both loops in `list_apps`.
    apps = query({"actual-budget": METADATA_WITHOUT_DEFAULTS}, resources=resources, config_dirs=config_dirs)

    assert apps[0]["state"] == state
    assert apps[0]["error_reason"] is None
    assert (apps[0]["migrated"], apps[0]["notes"]) == (False, None)


@pytest.mark.parametrize(
    "resources,config_dirs,state", [(RESOURCES, (), "RUNNING"), (None, ["actual-budget"], "STOPPED")]
)
def test_an_app_without_the_defaulted_keys_survives_the_conversion(query, resources, config_dirs, state):
    # A query result makes every field optional, so a row missing these converts without complaint
    # and only the entry itself shows whether they were defaulted or left undefined
    apps = query({"actual-budget": METADATA_WITHOUT_DEFAULTS}, resources=resources, config_dirs=config_dirs)

    entry = to_app_entry(apps[0], False)

    assert (entry.state, entry.error_reason) == (state, None)
    assert (entry.migrated, entry.notes) == (False, None)


def test_metadata_which_carries_the_defaulted_keys_keeps_them(query):
    metadata = COMPLETE_METADATA | {"migrated": True, "notes": "Some notes"}

    apps = query({"actual-budget": metadata}, resources=RESOURCES)

    assert (apps[0]["migrated"], apps[0]["notes"]) == (True, "Some notes")


@pytest.mark.parametrize(
    "overrides,key,expected",
    [
        ({"name": 1}, "name", "actual-budget"),
        ({"id": 1}, "id", "actual-budget"),
        ({"state": "SOMETHING"}, "state", "RUNNING"),
        ({"error_reason": "METADATA_MISSING"}, "error_reason", None),
        ({"upgrade_available": "yes"}, "upgrade_available", False),
        ({"version_details": "none"}, "version_details", None),
    ],
)
def test_metadata_does_not_override_what_we_determined_ourselves(query, overrides, key, expected):
    # A metadata supplied `id` would leave the app undeletable, since `get_instance` looks it up by
    # the name it was asked for, and the rest blind the checks which act on the state we reported
    apps = query({"actual-budget": COMPLETE_METADATA | overrides}, resources=RESOURCES)

    assert apps[0][key] == expected


def test_metadata_does_not_override_the_workloads(query):
    # These are what keeps the ports and volumes the app is holding visible to conflict detection
    apps = query({"actual-budget": COMPLETE_METADATA | {"active_workloads": "none"}}, resources=RESOURCES)

    assert apps[0]["active_workloads"]["containers"] == 1


def test_metadata_the_api_model_cannot_describe_reaches_the_conversion(query):
    # The row stays everything the metadata file holds, so that `to_app_entry` is the one which
    # decides an app cannot be described rather than this silently dropping what it would reject
    apps = query({"actual-budget": COMPLETE_METADATA | {"some_new_key": "value"}}, resources=RESOURCES)

    assert apps[0]["some_new_key"] == "value"


@pytest.mark.parametrize("app_metadata", ["actual-budget", 1, 1.13, ["actual-budget"]])
def test_metadata_entry_which_is_not_a_mapping_is_reported(query, app_metadata):
    # An entry of the collective metadata file is whatever yaml parsed it as, and testing a
    # non-mapping for the keys we need raises rather than answering
    apps = query({"actual-budget": app_metadata}, resources=RESOURCES)

    assert [(app["id"], app["state"], app["error_reason"]) for app in apps] == [
        ("actual-budget", "ERROR", "METADATA_INCOMPLETE")
    ]


@pytest.mark.parametrize("resources,config_dirs", [(RESOURCES, ()), (None, ["actual-budget"])])
def test_config_which_cannot_be_read_does_not_break_the_query(query, monkeypatch, resources, config_dirs):
    """
    An app whose config could not be read now survives into the collective metadata, so the query
    reaches this file again - and letting the second failure escape would take `app.query` down for
    every app on the box. Checked for a running app and a stopped one, i.e. both loops in `list_apps`.
    """

    def unreadable_config(app_name, version):
        raise FileNotFoundError(2, "No such file or directory")

    monkeypatch.setattr("middlewared.plugins.apps.ix_apps.query.get_current_app_config", unreadable_config)
    apps = query(
        {"actual-budget": COMPLETE_METADATA}, resources=resources, config_dirs=config_dirs, retrieve_config=True
    )

    assert [(app["id"], app["error_reason"], app["config"]) for app in apps] == [("actual-budget", None, {})]


@pytest.mark.parametrize("project_name", ["webserver", "portainer", "ix-"])
def test_a_compose_project_which_is_not_ours_is_not_an_app(query, monkeypatch, project_name):
    # Docker reports every compose project on the box, and taking the prefix off a name which does
    # not carry one invents an app the UI then offers to delete - against a name which is not ours
    monkeypatch.setattr(
        "middlewared.plugins.apps.ix_apps.metadata.get_app_metadata_checked",
        lambda app_name: ({}, "METADATA_MISSING"),
    )

    assert query({}, resources={project_name: RESOURCES["ix-actual-budget"]}) == []


def test_a_compose_project_which_is_not_ours_does_not_hide_a_real_app(query):
    # `webserver` reads as an app named `server`, which filters the real one out of the stopped loop
    # and lends it containers it does not own
    apps = query(
        {"server": COMPLETE_METADATA},
        resources={"webserver": RESOURCES["ix-actual-budget"]},
        config_dirs=["server"],
    )

    assert [(app["id"], app["state"], app["active_workloads"]["containers"]) for app in apps] == [
        ("server", "STOPPED", 0)
    ]


@pytest.mark.parametrize("collective_config", ["some-config", 1, ["key"], True])
def test_collective_config_which_is_not_a_mapping_does_not_break_the_app(query, monkeypatch, collective_config):
    # An entry of the collective config file is whatever yaml parsed it as, and reporting a value
    # the API model cannot describe turned a healthy running app into a broken one
    monkeypatch.setattr(
        "middlewared.plugins.apps.ix_apps.query.get_current_app_config", lambda app_name, version: {"own": True}
    )
    apps = query(
        {"actual-budget": COMPLETE_METADATA},
        resources=RESOURCES,
        collective_config={"actual-budget": collective_config},
        retrieve_config=True,
    )

    assert [(app["id"], app["state"], app["error_reason"], app["config"]) for app in apps] == [
        ("actual-budget", "RUNNING", None, {"own": True})
    ]


@pytest.mark.parametrize("collective_config", ["some-config", 1, ["key"], True])
def test_an_app_whose_collective_config_is_not_a_mapping_still_converts(query, monkeypatch, collective_config):
    # Where the harm lands: the row reaches the API model, which describes `config` as a mapping
    monkeypatch.setattr(
        "middlewared.plugins.apps.ix_apps.query.get_current_app_config", lambda app_name, version: {"own": True}
    )
    apps = query(
        {"actual-budget": COMPLETE_METADATA},
        resources=RESOURCES,
        collective_config={"actual-budget": collective_config},
        retrieve_config=True,
    )

    entry = to_app_entry(apps[0], True)

    assert (entry.state, entry.error_reason, entry.config) == ("RUNNING", None, {"own": True})


def test_a_collective_config_which_is_a_mapping_is_still_used(query, monkeypatch):
    def unread_config(app_name, version):
        raise AssertionError("the app's own config file was read instead of the collective one")

    monkeypatch.setattr("middlewared.plugins.apps.ix_apps.query.get_current_app_config", unread_config)
    apps = query(
        {"actual-budget": COMPLETE_METADATA},
        resources=RESOURCES,
        collective_config={"actual-budget": {"key": "value"}},
        retrieve_config=True,
    )

    assert apps[0]["config"] == {"key": "value"}


@pytest.mark.parametrize("portals", ["http://0.0.0.0:8080", 1, ["http://0.0.0.0:8080"]])
def test_portals_which_cannot_be_normalized_are_returned_untouched(portals):
    # `to_app_entry` is what reports such an app as broken, and it can only do so if what it is
    # handed still carries the value the model will reject
    assert normalize_portal_uris(portals, "10.0.0.1") == portals


def test_portal_uris_which_are_not_strings_are_left_alone():
    portals = {"web": 8080, "ui": "http://0.0.0.0:8081"}

    assert normalize_portal_uris(portals, "10.0.0.1") == {"web": 8080, "ui": "http://10.0.0.1:8081"}


@pytest.mark.parametrize("retrieve_config,expected_config", [(True, {}), (False, None)])
def test_error_entry_is_accepted_by_the_api_model(retrieve_config, expected_config):
    entry = error_app_data(
        "actual-budget",
        "METADATA_MISSING",
        {
            "containers": 0,
            "used_ports": [],
            "used_host_ips": [],
            "container_details": [],
            "volumes": [],
            "images": [],
            "networks": [],
        },
        retrieve_config,
    )

    assert entry["config"] == expected_config
    # Constructing this is what `app.query` does with every row it returns
    AppEntry.__query_result_item__(**entry)
