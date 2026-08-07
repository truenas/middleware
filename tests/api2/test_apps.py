import threading

import pytest

from middlewared.test.integration.utils import call, client, ssh
from middlewared.test.integration.assets.apps import app
from middlewared.test.integration.assets.docker import docker
from middlewared.test.integration.assets.pool import another_pool
from truenas_api_client import ValidationErrors


CUSTOM_CONFIG = {
    "services": {
        "actual_budget": {
            "user": "568:568",
            "image": "actualbudget/actual-server:24.10.1",
            "restart": "unless-stopped",
            "deploy": {"resources": {"limits": {"cpus": "2", "memory": "4096M"}}},
            "devices": [],
            "depends_on": {
                "permissions": {"condition": "service_completed_successfully"}
            },
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges"],
            "healthcheck": {
                "interval": "10s",
                "retries": 30,
                "start_period": "10s",
                "test": (
                    "/bin/bash -c 'exec {health_check_fd}< /dev/tcp/127.0.0.1/31012 "
                    "&& echo -e 'GET /health HTTP/1.1\\r\\nHost: 127.0.0.1\\r\\n"
                    "Connection: close\\r\\n\\r\\n' >&$$health_check_fd && "
                    "cat <&$$health_check_fd'"
                ),
                "timeout": "5s",
            },
            "environment": {
                "ACTUAL_HOSTNAME": "0.0.0.0",
                "ACTUAL_PORT": "31012",
                "ACTUAL_SERVER_FILES": "/data/server-files",
                "ACTUAL_USER_FILES": "/data/user-files",
                "GID": "568",
                "GROUP_ID": "568",
                "NODE_ENV": "production",
                "PGID": "568",
                "PUID": "568",
                "TZ": "Etc/UTC",
                "UID": "568",
                "USER_ID": "568",
            },
            "ports": [
                {
                    "host_ip": "0.0.0.0",
                    "mode": "ingress",
                    "protocol": "tcp",
                    "published": 31012,
                    "target": 31012,
                }
            ],
        },
        "permissions": {
            "command": [
                """
                function process_dir() {
                    local dir=$$1
                    local mode=$$2
                    local uid=$$3
                    local gid=$$4
                    local chmod=$$5
                    local is_temporary=$$6
                    # Process directory logic here...
                }
                process_dir /mnt/actual_budget/config check 568 568 false false
                """
            ],
            "deploy": {"resources": {"limits": {"cpus": "1.0", "memory": "512m"}}},
            "entrypoint": ["bash", "-c"],
            "image": "bash",
            "user": "root",
        },
    },
    "x-portals": [
        {
            "host": "0.0.0.0",
            "name": "Web UI",
            "path": "/",
            "port": 31012,
            "scheme": "http",
        }
    ],
    "x-notes": """# Welcome to TrueNAS SCALE

    Thank you for installing Actual Budget!

    ## Documentation
    Documentation for Actual Budget can be found at https://www.truenas.com/docs.

    ## Bug reports
    If you find a bug in this app, please file an issue at
    https://ixsystems.atlassian.net or https://github.com/truenas/apps.

    ## Feature requests or improvements
    If you find a feature request for this app, please file an issue at
    https://ixsystems.atlassian.net or https://github.com/truenas/apps.
    """,
}

INVALID_YAML = """
services:
  actual_budget
    user: 568:568
    image: actualbudget/actual-server:24.10.1
    restart: unless-stopped
    deploy:
      resources: {'limits': {'cpus': '2', 'memory': '4096M'}}
    devices: []
    depends_on:
      permissions:
        condition: service_completed_successfully
    cap_drop: ['ALL']
    security_opt: ['no-new-privileges']
"""


@pytest.fixture(scope="module")
def docker_pool():
    with another_pool() as pool:
        with docker(pool) as docker_config:
            yield docker_config


def test_create_catalog_app(docker_pool):
    with app(
        "actual-budget",
        {
            "train": "community",
            "catalog_app": "actual-budget",
        },
        {"remove_images": False},
    ) as app_info:
        assert app_info["name"] == "actual-budget", app_info
        assert app_info["state"] == "DEPLOYING", app_info
        volume_ds = call("app.get_app_volume_ds", "actual-budget")
        assert volume_ds is not None, volume_ds


def test_create_custom_app(docker_pool):
    with app(
        "custom-budget",
        {
            "custom_app": True,
            "custom_compose_config": CUSTOM_CONFIG,
        },
        {"remove_images": False},
    ) as app_info:
        assert app_info["name"] == "custom-budget"
        assert app_info["state"] == "DEPLOYING"


def test_create_custom_app_compose_progress(docker_pool):
    """
    App installation streams fine-grained progress parsed from `docker compose
    --progress=json` events (image pulls, container creation) instead of jumping
    between fixed milestones. If a docker compose upgrade ever changes the JSON
    event format, the progress tracker goes silent and this test fails loudly
    instead of app job progress silently freezing mid-operation.
    """
    def install_capturing_progress(c):
        progress = []
        progress_lock = threading.Lock()

        def callback(job):
            # api_client dispatches each job event to this callback in its own daemon thread,
            # all sharing one mutable job dict. Serialize read+append so concurrent threads
            # cannot interleave into an out-of-order capture; since progress only advances, the
            # captured percents stay sorted under the lock.
            with progress_lock:
                item = (job["progress"]["percent"], job["progress"]["description"])
                if not progress or progress[-1] != item:
                    progress.append(item)

        c.call(
            "app.create",
            {
                "app_name": "progress-probe",
                "custom_app": True,
                "custom_compose_config": {"services": {"nginx": {"image": "nginx:1.27-alpine"}}},
            },
            job=True,
            callback=callback,
        )
        percents = [percent for percent, _ in progress if percent is not None]
        assert percents == sorted(percents), progress
        # Compose resource events are emitted whether or not images needed pulling
        assert any(
            "Container" in description for _, description in progress if description
        ), progress
        return progress

    with client(py_exceptions=False) as c:
        try:
            install_capturing_progress(c)
            # Reinstalling with the image kept must reuse it: byte-level pull progress
            # (only reported while layers actually download) must not appear
            call("app.delete", "progress-probe", {"remove_images": False}, job=True)
            progress = install_capturing_progress(c)
            assert not any(
                description.startswith("Pulling app images (") for _, description in progress if description
            ), progress
        finally:
            call("app.delete", "progress-probe", {"remove_images": True}, job=True)


def test_create_custom_app_validation_error(docker_pool):
    with pytest.raises(ValidationErrors):
        with app(
            "custom-budget",
            {
                "custom_app": False,
                "custom_compose_config": CUSTOM_CONFIG,
            },
            {"remove_images": False},
        ):
            pass


def test_create_custom_app_invalid_yaml(docker_pool):
    with pytest.raises(ValidationErrors):
        with app(
            "custom-budget",
            {
                "custom_app": True,
                "custom_compose_config": INVALID_YAML,
            },
            {"remove_images": False},
        ):
            pass


def test_delete_app_validation_error_for_non_existent_app(docker_pool):
    with pytest.raises(ValidationErrors):
        call(
            "app.delete",
            "actual-budget",
            {"remove_ix_volumes": True, "remove_images": True},
            job=True,
        )


def test_update_app(docker_pool):
    values = {
        "values": {
            "network": {
                "web_port": {
                    "bind_mode": "published",
                    "host_ips": [],
                    "port_number": 32000,
                }
            },
            "resources": {"limits": {"memory": 8192}},
        }
    }
    with app(
        "actual-budget",
        {
            "train": "community",
            "catalog_app": "actual-budget",
        },
        {"remove_images": False},
    ) as app_info:
        app_info = call("app.update", app_info["name"], values, job=True)
        assert (
            app_info["active_workloads"]["used_ports"][0]["host_ports"][0]["host_port"]
            == 32000
        )


def test_stop_start_app(docker_pool):
    with app(
        "actual-budget",
        {"train": "community", "catalog_app": "actual-budget"},
        {"remove_images": False},
    ):
        # stop running app
        call("app.stop", "actual-budget", job=True)
        states = call("app.query", [], {"select": ["state"]})[0]
        assert states["state"] == "STOPPED"

        # start stopped app
        call("app.start", "actual-budget", job=True)
        states = call("app.query", [], {"select": ["state"]})[0]
        assert states["state"] in ["RUNNING", "DEPLOYING"]


def test_event_subscribe(docker_pool):
    with client(py_exceptions=False) as c:
        expected_event_type_order = ["ADDED", "CHANGED"]
        expected_event_order = ["STOPPING", "STOPPED", "DEPLOYING"]
        events = []
        event_types = []
        track_states = False

        def callback(event_type, **message):
            nonlocal events, event_types, track_states
            state = message["fields"]["state"]
            # Always track event types (for the outer assertion)
            if not event_types or event_types[-1] != event_type:
                event_types.append(event_type)

            # Start tracking states when we see STOPPING.
            # This is deterministic because STOPPING only comes from app.stop,
            # avoiding the race condition of clearing events at the right time.
            if state == "STOPPING":
                track_states = True

            if not track_states:
                return

            if not events or events[-1] != state:
                events.append(state)

        c.subscribe("app.query", callback, sync=True)

        with app("ipfs", {"train": "community", "catalog_app": "ipfs"}):
            call("app.stop", "ipfs", job=True)
            call("app.start", "ipfs", job=True)
            assert expected_event_order == events

        assert expected_event_type_order == event_types


def test_delete_app_options(docker_pool):
    with app(
        "custom-budget",
        {
            "custom_app": True,
            "custom_compose_config": CUSTOM_CONFIG,
        },
        {"remove_ix_volumes": True, "remove_images": True},
    ) as app_info:
        assert app_info["name"] == "custom-budget"
        assert app_info["state"] == "DEPLOYING"

    app_images = call(
        "app.image.query", [["repo_tags", "=", ["actualbudget/actual-server:24.10.1"]]]
    )
    assert len(app_images) == 0
    volume_ds = call("app.get_app_volume_ds", "custom-budget")
    assert volume_ds is None


# Chokepoint lockdown — non-root host users (apps UID 568) must not be able
# to traverse /mnt/.ix-apps. Docker overlay layers and ix_volume datasets
# contain files owned by colliding UIDs.

IX_APPS_CHOKEPOINT = "/mnt/.ix-apps"


def _chokepoint_perms(path):
    st = call("filesystem.stat", path)
    return st["mode"] & 0o7777, st["uid"], st["gid"]


def test_ix_apps_chokepoint_locked(docker_pool):
    assert _chokepoint_perms(IX_APPS_CHOKEPOINT) == (0o700, 0, 0)


@pytest.mark.parametrize("child", ["", "docker", "app_mounts"])
def test_apps_user_cannot_traverse_ix_apps(docker_pool, child):
    target = f"{IX_APPS_CHOKEPOINT}/{child}".rstrip("/")
    result = ssh(
        f"runuser -u apps -- ls {target}/",
        check=False,
        complete_response=True,
    )
    assert result["returncode"] != 0
    assert "Permission denied" in result["stderr"]


def test_root_retains_access_ix_apps(docker_pool):
    listing = set(ssh(f"ls {IX_APPS_CHOKEPOINT}/").split())
    assert {"docker", "app_mounts", "app_configs", "truenas_catalog"} <= listing


def test_drift_repair_ix_apps(docker_pool):
    ssh(f"chmod 0755 {IX_APPS_CHOKEPOINT}")
    # start_service is idempotent if docker is already running, but still
    # runs the drift-repair enforce_mountpoint_perms call.
    call("docker.start_service")
    assert _chokepoint_perms(IX_APPS_CHOKEPOINT) == (0o700, 0, 0)


@pytest.mark.parametrize("corrupt,expected_reason", [
    # Keeps `version`, so the incomplete metadata still lands in the collective metadata file and
    # the app is classified from it without any extra read
    (
        "python3 -c \"import yaml,sys;p=sys.argv[1];d=yaml.safe_load(open(p));d.pop('metadata');"
        "open(p,'w').write(yaml.safe_dump(d))\" {path}",
        "METADATA_INCOMPLETE",
    ),
    # Unparseable, so the app is dropped from the collective metadata entirely and has to be
    # classified by reading its own metadata file
    ("printf '{{' > {path}", "METADATA_UNREADABLE"),
])
def test_app_with_unusable_metadata_is_reported_and_deletable(docker_pool, corrupt, expected_reason):
    """
    An app we cannot read the metadata of used to be invisible to `app.query`, which left no way to
    remove it. It must now be reported, refused for everything but deletion, and actually deletable.
    """
    app_name = "actual-budget"
    metadata_path = f"/mnt/.ix-apps/app_configs/{app_name}/metadata.yaml"
    call(
        "app.create",
        {"app_name": app_name, "train": "community", "catalog_app": app_name},
        job=True,
    )
    deleted = False
    try:
        ssh(f"cp {metadata_path} /tmp/{app_name}.metadata.bak")
        ssh(corrupt.format(path=metadata_path))
        call("app.metadata_generate", job=True)

        app_info = call("app.query", [["id", "=", app_name]], {"get": True})
        assert app_info["state"] == "ERROR", app_info
        assert app_info["error_reason"] == expected_reason, app_info
        assert app_info["version"] is None, app_info
        assert app_info["human_version"] is None, app_info
        assert app_info["metadata"] == {}, app_info

        # Its containers are still running, so the ports they hold must stay accounted for
        used_ports = app_info["active_workloads"]["used_ports"]
        assert used_ports, app_info
        assert used_ports[0]["host_ports"][0]["host_port"] in call("app.used_ports")

        # One broken app must not take the rest of the apps subsystem down with it
        assert call("app.query")
        assert call("app.available", [["name", "=", app_name]])

        for method, args, is_job in (
            ("app.start", [app_name], True),
            ("app.stop", [app_name], True),
            ("app.redeploy", [app_name], True),
            ("app.config", [app_name], False),
            ("app.rollback_versions", [app_name], False),
            ("app.outdated_docker_images", [app_name], False),
            ("app.container_console_choices", [app_name], False),
            ("app.convert_to_custom", [app_name], True),
        ):
            with pytest.raises(Exception) as exc_info:
                call(method, *args, job=is_job)
            assert "metadata is unusable" in str(exc_info.value), (method, exc_info.value)

        call("app.delete", app_name, {"remove_images": True, "remove_ix_volumes": True}, job=True)
        deleted = True

        assert call("app.query", [["id", "=", app_name]]) == []
        assert ssh(f"test -e /mnt/.ix-apps/app_configs/{app_name}; echo $?").strip() == "1"
        assert call("app.get_app_volume_ds", app_name) is None
    finally:
        if not deleted:
            # Later tests in this module reuse this app name, so it must not be left poisoned
            ssh(f"cp /tmp/{app_name}.metadata.bak {metadata_path} || true")
            try:
                call("app.delete", app_name, {"remove_images": True, "remove_ix_volumes": True}, job=True)
            except Exception:
                ssh(f"rm -rf /mnt/.ix-apps/app_configs/{app_name}")
            call("app.metadata_generate", job=True)
        ssh(f"rm -f /tmp/{app_name}.metadata.bak")
