import contextlib
import types
from unittest.mock import MagicMock, patch

from pydantic import ValidationError
import pytest

from middlewared.api.current import AppCreate
from middlewared.job import State
from middlewared.plugins.apps.crud import apps_being_installed, create_app, to_app_entries, to_app_entry
from middlewared.plugins.apps.ix_apps.query import get_default_workload_values
from middlewared.service import ValidationErrors


def app_row(**overrides):
    """A query row as `list_apps` builds it for a healthy app."""
    return {
        "name": "actual-budget",
        "id": "actual-budget",
        "state": "RUNNING",
        "error_reason": None,
        "upgrade_available": False,
        "latest_version": None,
        "latest_app_version": None,
        "image_updates_available": False,
        "custom_app": False,
        "migrated": False,
        "human_version": "24.10.1_1.1.13",
        "version": "1.1.13",
        "metadata": {"name": "actual-budget", "train": "community", "version": "1.1.13"},
        "active_workloads": get_default_workload_values(),
        "notes": None,
        "action_required": False,
        "portals": {},
        "version_details": None,
        "config": None,
    } | overrides


def test_valid_row_is_converted():
    entry = to_app_entry(app_row(), False)

    assert (entry.id, entry.state, entry.version) == ("actual-budget", "RUNNING", "1.1.13")


@pytest.mark.parametrize(
    "overrides",
    [
        # yaml parses an unquoted 1.13 as a float, and 1.1.13 as a string
        {"version": 1.13},
        {"version": ""},
        {"human_version": []},
        {"custom_app": "maybe"},
        {"notes": ["a", "b"]},
        {"portals": "http://0.0.0.0:8080"},
        {"metadata": "actual-budget"},
        {"action_required": "yes"},
        # A key the model knows nothing about, which it reports as an extra input
        {"some_new_key": "value"},
    ],
)
def test_row_the_model_rejects_is_reported_as_broken(overrides):
    entry = to_app_entry(app_row(**overrides), False)

    assert entry.state == "ERROR"
    assert entry.error_reason == "METADATA_INCOMPLETE"
    assert entry.version is None
    assert entry.human_version is None


@pytest.mark.parametrize("key", [True, 5, None])
def test_row_with_a_non_string_key_is_reported_as_broken(key):
    # `on:` parses as the bool True and `5:` as an int, and splatting such a row would raise
    # TypeError rather than anything a validation handler could catch
    entry = to_app_entry(app_row() | {key: "value"}, False)

    assert (entry.id, entry.state, entry.error_reason) == ("actual-budget", "ERROR", "METADATA_INCOMPLETE")


def test_row_we_cannot_even_name_is_not_swallowed():
    # Only a query which selected neither `name` nor `id` produces a row of this shape, and there is
    # no entry we could report such an app as
    with pytest.raises(ValidationError):
        to_app_entry({"version": 1.13}, False)


def test_real_workloads_are_kept_when_they_are_usable():
    # They are what keeps the ports and volumes a broken app is still holding on to visible
    workloads = get_default_workload_values() | {"containers": 2, "used_host_ips": ["10.0.0.1"]}

    entry = to_app_entry(app_row(version=1.13, active_workloads=workloads), False)

    assert entry.state == "ERROR"
    assert entry.active_workloads.containers == 2
    assert entry.active_workloads.used_host_ips == ["10.0.0.1"]


def test_unusable_workloads_are_dropped():
    entry = to_app_entry(app_row(active_workloads={"containers": "two"}), False)

    assert entry.state == "ERROR"
    assert entry.active_workloads.containers == 0
    assert entry.active_workloads.used_ports == []


@pytest.mark.parametrize("retrieve_config,expected_config", [(True, {}), (False, None)])
def test_broken_entry_reports_config_as_asked(retrieve_config, expected_config):
    entry = to_app_entry(app_row(version=1.13), retrieve_config)

    assert entry.config == expected_config


def test_one_broken_app_does_not_fail_the_rest():
    rows = [
        app_row(),
        app_row(id="broken", name="broken", version=1.13),
        app_row(id="other", name="other"),
    ]

    entries = to_app_entries(rows, False)

    assert [(entry.id, entry.state) for entry in entries] == [
        ("actual-budget", "RUNNING"),
        ("broken", "ERROR"),
        ("other", "RUNNING"),
    ]


def test_count_is_passed_through():
    assert to_app_entries(3, False) == 3


def test_single_row_is_converted():
    # `app.query` with `get: true` hands us the row on its own rather than in a list
    assert to_app_entries(app_row(), False).id == "actual-budget"


APP_DETAILS = types.SimpleNamespace(
    versions={"1.1.13": {"app_metadata": {"annotations": {"disallow_multiple_instances": True}}}},
)
INSTALLED_METADATA = {"metadata": {"name": "actual-budget", "train": "community", "version": "1.1.13"}}


@contextlib.contextmanager
def install(collective_metadata):
    """Run `create_app` for an app which does not allow multiple instances, yielding the install."""
    context = MagicMock()
    context.call_sync2.return_value = APP_DETAILS
    with (
        patch("middlewared.plugins.apps.crud.query_apps", return_value=[]),
        patch("middlewared.plugins.apps.crud.get_collective_metadata", return_value=collective_metadata),
        patch("middlewared.plugins.apps.crud.create_internal") as create_internal,
    ):
        create_app(
            context,
            MagicMock(),
            AppCreate(app_name="budget-two", catalog_app="actual-budget", train="community", version="1.1.13"),
        )
        yield create_internal


@pytest.mark.parametrize("installed_app", ["actual-budget", 1, ["actual-budget"], {"metadata": "actual-budget"}])
def test_broken_app_does_not_block_installing_an_unrelated_one(installed_app):
    # An entry of the collective metadata is whatever yaml parsed it as, and reading into it blindly
    # made an install fail because of an app which has nothing to do with it
    with install({"broken": installed_app}) as create_internal:
        assert create_internal.call_count == 1


def test_an_instance_which_is_already_installed_is_still_refused():
    with pytest.raises(ValidationErrors) as exc_info:
        with install({"broken": "actual-budget", "actual-budget": INSTALLED_METADATA}):
            pass

    assert "does not allow multiple instances" in str(exc_info.value)


def installing_apps(*jobs):
    """Run `apps_being_installed` against a job queue holding `jobs`."""
    context = MagicMock()
    context.middleware.jobs.all.return_value = dict(enumerate(jobs))
    return apps_being_installed(context)


def fake_job(method_name, args, state=State.RUNNING):
    return types.SimpleNamespace(method_name=method_name, args=args, state=state)


@pytest.mark.parametrize("state", [State.WAITING, State.RUNNING])
def test_an_install_queued_with_a_raw_payload_is_reported(state):
    job = fake_job("app.create", [{"app_name": "actual-budget"}], state)

    assert installing_apps(job) == {"actual-budget"}


def test_an_install_queued_with_a_validated_payload_is_reported():
    payload = AppCreate(app_name="actual-budget", catalog_app="actual-budget", train="community", version="1.1.13")

    assert installing_apps(fake_job("app.create", [payload])) == {"actual-budget"}


def test_a_conversion_is_reported():
    # Converting an app deletes and recreates it in place, and the job is handed the name itself
    assert installing_apps(fake_job("app.convert_to_custom", ["actual-budget"])) == {"actual-budget"}


@pytest.mark.parametrize("state", [State.SUCCESS, State.FAILED, State.ABORTED])
def test_a_job_which_is_no_longer_running_is_ignored(state):
    job = fake_job("app.create", [{"app_name": "actual-budget"}], state)

    assert installing_apps(job) == set()


def test_a_job_of_another_method_is_ignored():
    assert installing_apps(fake_job("app.delete", ["actual-budget"])) == set()


@pytest.mark.parametrize("args", [[], [{}], [None]])
def test_a_job_we_cannot_name_an_app_from_is_ignored(args):
    assert installing_apps(fake_job("app.create", args)) == set()


def test_every_app_in_flight_is_reported():
    assert installing_apps(
        fake_job("app.create", [{"app_name": "actual-budget"}]),
        fake_job("app.convert_to_custom", ["plex"]),
        fake_job("app.create", [{"app_name": "syncthing"}], State.SUCCESS),
    ) == {"actual-budget", "plex"}
