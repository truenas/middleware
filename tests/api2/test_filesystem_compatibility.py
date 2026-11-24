import pytest
from truenas_api_client import ValidationErrors

from middlewared.service_exception import ValidationErrors as ServiceValidationErrors
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.apps import app, rewind_installed_version
from middlewared.test.integration.assets.cloud_sync import local_ftp_credential, task
from middlewared.test.integration.assets.container import (
    UBUNTU_IMAGE_NAME,
    configure_bridge,
    container,
    filesystem_device,
    resolve_image,
)
from middlewared.test.integration.assets.docker import docker
from middlewared.test.integration.assets.entitlements import entitled
from middlewared.test.integration.assets.nfs import nfs_share
from middlewared.test.integration.assets.pool import another_pool, dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.alert import get_alerts_by_class, run_alerts

RISK = (
    "Exposing the same data to another operating-system environment can cause inconsistent data, application "
    "failures, permission changes, or data corruption. Set `force_path_conflicts` to proceed anyway."
)
ALERT_CLASS = "PathUsedByMultipleServices"
FORCE = {"force_path_conflicts": True}

COMPOSE = """\
services:
  nginx:
    image: nginx:1.27-alpine
    volumes:
      - {path}:/data
      - {path}:/data-again:ro
      - {private}:/private
      - named:/named
volumes:
  named: {{}}
"""

LONG_SYNTAX_COMPOSE = """\
services:
  nginx:
    image: nginx:1.27-alpine
    volumes:
      - type: bind
        source: {path}
        target: /data
"""

BOUND_VOLUME_COMPOSE = """\
services:
  nginx:
    image: nginx:1.27-alpine
    volumes:
      - bound:/data
volumes:
  bound:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: {path}
"""


def warnings(path, service):
    return call("filesystem.compatibility.compatibility_warnings", path, service)


def consumer(service, id_, name, path):
    return {"service": service, "id": id_, "name": name, "path": path}


def alert_args():
    return [alert["args"] for alert in call("alert.run_source", ALERT_CLASS)]


def listed_alert_args():
    # A consumer change clears the checker's last run, so the next alert run reports it without waiting a day
    run_alerts()
    return [alert["args"] for alert in get_alerts_by_class(ALERT_CLASS)]


def host_path_values(path):
    return {"storage": {"data": {"type": "host_path", "host_path_config": {"acl_enable": False, "path": path}}}}


@pytest.fixture(scope="module")
def ubuntu_image():
    configure_bridge()
    return resolve_image(UBUNTU_IMAGE_NAME)


@pytest.fixture(scope="module")
def workload(ubuntu_image):
    with container(ubuntu_image) as c:
        yield c


def test_shares_on_a_workload_path_require_force(workload):
    with dataset("compat") as parent, dataset("compat/shared") as ds:
        path = f"/mnt/{ds}"
        with filesystem_device(workload["id"], path, "/shared"):
            container_consumer = consumer("container", workload["id"], workload["name"], path)
            with pytest.raises(ServiceValidationErrors) as ve:
                call("sharing.smb.create", {"path": path, "name": "compat_shared"})
            assert ve.value.errors[0].attribute == "options.force_path_conflicts"
            assert ve.value.errors[0].errmsg == f"{path} is also used by Container {workload['name']!r}. {RISK}"

            smb = call("sharing.smb.create", {"path": path, "name": "compat_shared"}, FORCE)
            try:
                smb_consumer = consumer("sharing.smb", smb["id"], "compat_shared", path)
                # A read-only share is a sharer like any other, and the SMB share is not its conflict
                with pytest.raises(ServiceValidationErrors) as ve:
                    call("sharing.nfs.create", {"path": path, "ro": True})
                assert ve.value.errors[0].errmsg == f"{path} is also used by Container {workload['name']!r}. {RISK}"
                nfs = call("sharing.nfs.create", {"path": path, "ro": True}, FORCE)
                try:
                    nfs_consumer = consumer("sharing.nfs", nfs["id"], path, path)
                    assert warnings(path, "container") == [smb_consumer, nfs_consumer]
                    # An app would conflict with the container too
                    assert warnings(path, "app") == [smb_consumer, nfs_consumer, container_consumer]
                    assert warnings(path, "sharing.smb") == [container_consumer]
                    assert warnings(path, "sharing.nfs") == [container_consumer]
                    # A child of the path and a parent of it overlap it too
                    assert warnings(f"{path}/sub", "sharing.webshare") == [container_consumer]
                    assert warnings(f"/mnt/{parent}", "cloudsync") == [container_consumer]
                    assert warnings(f"/mnt/{parent}/other", "sharing.smb") == []
                    assert listed_alert_args() == [
                        {
                            "path": path,
                            "consumers": f"Container {workload['name']!r}, NFS share {path!r}, SMB share 'compat_shared'",
                        }
                    ]

                    # Editing a share needs the acknowledgment again while the workload remains
                    with pytest.raises(ServiceValidationErrors) as ve:
                        call("sharing.smb.update", smb["id"], {"comment": "edited"})
                    assert ve.value.errors[0].attribute == "options.force_path_conflicts"
                    call("sharing.smb.update", smb["id"], {"comment": "edited"}, FORCE)
                    with pytest.raises(ServiceValidationErrors) as ve:
                        call("sharing.nfs.update", nfs["id"], {"comment": "edited"})
                    assert ve.value.errors[0].attribute == "options.force_path_conflicts"
                    call("sharing.nfs.update", nfs["id"], {"comment": "edited"}, FORCE)

                    # Disabling a share needs none, and a disabled share is no sharer
                    call("sharing.nfs.update", nfs["id"], {"enabled": False})
                    assert warnings(path, "container") == [smb_consumer]
                    assert alert_args() == [
                        {
                            "path": path,
                            "consumers": f"Container {workload['name']!r}, SMB share 'compat_shared'",
                        }
                    ]
                finally:
                    call("sharing.nfs.delete", nfs["id"])
            finally:
                call("sharing.smb.delete", smb["id"])
            assert listed_alert_args() == []

            # An external SMB share has no path
            external = {"purpose": "EXTERNAL_SHARE", "options": {"remote_path": ["SERVER\\share"]}}
            with smb_share("EXTERNAL", "compat_external", external):
                assert warnings(path, "container") == []


def test_webshare_on_a_workload_path_requires_force(workload):
    with entitled("WEBSHARE"), dataset("compat_webshare") as ds:
        path = f"/mnt/{ds}"
        with filesystem_device(workload["id"], path, "/webshare"):
            with pytest.raises(ServiceValidationErrors) as ve:
                call("sharing.webshare.create", {"name": "compat", "path": path})
            assert ve.value.errors[0].attribute == "options.force_path_conflicts"
            assert ve.value.errors[0].errmsg == f"{path} is also used by Container {workload['name']!r}. {RISK}"

            share = call("sharing.webshare.create", {"name": "compat", "path": path}, FORCE)
            try:
                assert warnings(path, "container") == [consumer("sharing.webshare", share["id"], "compat", path)]
                with pytest.raises(ServiceValidationErrors) as ve:
                    call("sharing.webshare.update", share["id"], {"readonly": True})
                assert ve.value.errors[0].attribute == "options.force_path_conflicts"
                call("sharing.webshare.update", share["id"], {"readonly": True}, FORCE)
            finally:
                call("sharing.webshare.delete", share["id"])


def test_s3_bucket_on_a_workload_path_requires_force(workload):
    with user({"username": "compat_s3", "full_name": "compat", "group_create": True, "password": "test1234"}):
        with dataset("compat_s3") as ds:
            path = f"/mnt/{ds}"
            with filesystem_device(workload["id"], path, "/s3"):
                payload = {"name": "compat-bucket", "dataset": ds, "layout": "DATASET", "owner": "compat_s3"}
                with pytest.raises(ServiceValidationErrors) as ve:
                    call("sharing.s3.create", payload)
                assert ve.value.errors[0].attribute == "options.force_path_conflicts"
                assert ve.value.errors[0].errmsg == f"{path} is also used by Container {workload['name']!r}. {RISK}"

                bucket = call("sharing.s3.create", payload, FORCE)
                try:
                    assert warnings(path, "container") == [consumer("sharing.s3", bucket["id"], "compat-bucket", path)]
                    with pytest.raises(ServiceValidationErrors) as ve:
                        call("sharing.s3.update", bucket["id"], {"enabled": True})
                    assert ve.value.errors[0].attribute == "options.force_path_conflicts"
                    call("sharing.s3.update", bucket["id"], {"enabled": True}, FORCE)
                finally:
                    call("sharing.s3.delete", bucket["id"])


def test_cloud_sync_pull_task_on_a_workload_path_requires_force(workload):
    with dataset("compat_cloudsync") as ds, local_ftp_credential() as credential:
        path = f"/mnt/{ds}"
        payload = {
            "path": path,
            "credentials": credential["id"],
            "direction": "PULL",
            "transfer_mode": "COPY",
            "attributes": {"folder": ""},
        }
        with filesystem_device(workload["id"], path, "/cloudsync"):
            # A task that only reads the path is no sharer and needs no acknowledgment
            with task(payload | {"direction": "PUSH"}):
                assert warnings(path, "container") == []

            with pytest.raises(ServiceValidationErrors) as ve:
                with task(payload):
                    pass
            assert ve.value.errors[0].attribute == "options.force_path_conflicts"
            assert ve.value.errors[0].errmsg == f"{path} is also used by Container {workload['name']!r}. {RISK}"

            with task(payload, FORCE) as pull:
                assert warnings(path, "container") == [consumer("cloudsync", pull["id"], "Test", path)]
                with pytest.raises(ServiceValidationErrors) as ve:
                    call("cloudsync.update", pull["id"], {"description": "edited"})
                assert ve.value.errors[0].attribute == "options.force_path_conflicts"
                call("cloudsync.update", pull["id"], {"description": "edited"}, FORCE)

            # Its description names the task, however many lines it has
            with task(payload | {"description": "line one\nline two"}, FORCE) as pull:
                assert warnings(path, "container") == [consumer("cloudsync", pull["id"], "line one\nline two", path)]


def test_rsync_pull_task_on_a_workload_path_requires_force(workload):
    with dataset("compat_rsync") as ds:
        path = f"/mnt/{ds}"
        payload = {
            "path": path,
            "user": "root",
            "mode": "MODULE",
            "remotehost": "127.0.0.1",
            "remotemodule": "test",
            "direction": "PULL",
        }
        with filesystem_device(workload["id"], path, "/rsync"):
            push = call("rsynctask.create", payload | {"direction": "PUSH"})
            try:
                assert warnings(path, "container") == []
            finally:
                call("rsynctask.delete", push["id"])

            with pytest.raises(ServiceValidationErrors) as ve:
                call("rsynctask.create", payload)
            assert ve.value.errors[0].attribute == "options.force_path_conflicts"
            assert ve.value.errors[0].errmsg == f"{path} is also used by Container {workload['name']!r}. {RISK}"

            pull = call("rsynctask.create", payload, FORCE)
            try:
                # A task without a description is named by its path
                assert warnings(path, "container") == [consumer("rsynctask", pull["id"], path, path)]
                with pytest.raises(ServiceValidationErrors) as ve:
                    call("rsynctask.update", pull["id"], {"desc": "edited"})
                assert ve.value.errors[0].attribute == "options.force_path_conflicts"
                call("rsynctask.update", pull["id"], {"desc": "edited"}, FORCE)
            finally:
                call("rsynctask.delete", pull["id"])


def test_container_filesystem_device_on_a_shared_path_requires_force(workload):
    with dataset("compat_container") as ds:
        path = f"/mnt/{ds}"
        source = f"{path}/sub"
        call("filesystem.mkdir", {"path": source})
        with smb_share(path, "compat_container") as share:
            device = {
                "container": workload["id"],
                "attributes": {"dtype": "FILESYSTEM", "source": source, "target": "/sub"},
            }
            # A plain call raises the server's exception class, a job the client's. The share's own path is named
            # because it differs from the source
            with pytest.raises(ServiceValidationErrors) as ve:
                call("container.device.create", device)
            assert ve.value.errors[0].attribute == "options.force_path_conflicts"
            assert (
                ve.value.errors[0].errmsg == f"{source} is also used by SMB share 'compat_container' ({path}). {RISK}"
            )

            device_id = call("container.device.create", device, FORCE)["id"]
            try:
                smb_consumer = consumer("sharing.smb", share["id"], "compat_container", path)
                # Another container on the path would not be its conflict: only the share is
                assert warnings(source, "container") == [smb_consumer]
                assert warnings(path, "sharing.smb") == [
                    consumer("container", workload["id"], workload["name"], source)
                ]
                with pytest.raises(ServiceValidationErrors) as ve:
                    call("container.device.update", device_id, {"attributes": {"target": "/other"}})
                assert ve.value.errors[0].errmsg == (
                    f"{source} is also used by SMB share 'compat_container' ({path}). {RISK}"
                )
                call("container.device.update", device_id, {"attributes": {"target": "/other"}}, FORCE)

                assert listed_alert_args() == [
                    {
                        "path": source,
                        "consumers": f"Container {workload['name']!r}, SMB share 'compat_container' ({path})",
                    }
                ]
            finally:
                call("container.device.delete", device_id)

            assert listed_alert_args() == []


def test_deleting_a_container_clears_the_alert(ubuntu_image):
    with dataset("compat_deleted") as ds:
        path = f"/mnt/{ds}"
        with smb_share(path, "compat_deleted"):
            with container(ubuntu_image, name="compat-deleted") as c:
                attributes = {"dtype": "FILESYSTEM", "source": path, "target": "/shared"}
                call("container.device.create", {"container": c["id"], "attributes": attributes}, FORCE)
                assert listed_alert_args() == [
                    {"path": path, "consumers": "Container 'compat-deleted', SMB share 'compat_deleted'"}
                ]

                # Deleting the container takes its devices with it, without a device deletion of its own
                call("container.delete", c["id"], job=True)
                assert listed_alert_args() == []


@pytest.fixture(scope="module")
def docker_pool():
    with another_pool() as pool:
        with docker(pool):
            yield pool


def test_custom_app_on_a_shared_path_requires_force(docker_pool, workload):
    with dataset("compat_custom_app") as ds, dataset("compat_private") as private:
        path = f"/mnt/{ds}"
        with nfs_share(ds) as share:
            # Only the shared bind is a conflict, once however many times the compose mounts it: the private bind
            # and the named volume are not
            compose = {"custom_compose_config_string": COMPOSE.format(path=path, private=f"/mnt/{private}")}
            payload = compose | {"custom_app": True}
            with pytest.raises(ValidationErrors) as ve:
                with app("compat-nginx", payload, {"remove_images": False}):
                    pass
            assert [e.attribute for e in ve.value.errors] == ["options.force_path_conflicts"]
            assert ve.value.errors[0].errmsg == f"{path} is also used by NFS share {path!r}. {RISK}"

            with app("compat-nginx", payload, {"remove_images": False}, FORCE):
                app_consumer = consumer("app", "compat-nginx", "compat-nginx", path)
                nfs_consumer = consumer("sharing.nfs", share["id"], path, path)
                assert warnings(path, "sharing.nfs") == [app_consumer]
                assert warnings(path, "app") == [nfs_consumer]
                assert alert_args() == [{"path": path, "consumers": f"App 'compat-nginx', NFS share {path!r}"}]

                # A container is another environment, so it conflicts with the app as well as with the share
                device = {
                    "container": workload["id"],
                    "attributes": {"dtype": "FILESYSTEM", "source": path, "target": "/app"},
                }
                with pytest.raises(ServiceValidationErrors) as ve:
                    call("container.device.create", device)
                assert (
                    ve.value.errors[0].errmsg
                    == f"{path} is also used by NFS share {path!r}, App 'compat-nginx'. {RISK}"
                )
                device_id = call("container.device.create", device, FORCE)["id"]
                try:
                    container_consumer = consumer("container", workload["id"], workload["name"], path)
                    assert warnings(path, "app") == [nfs_consumer, container_consumer]
                    assert alert_args() == [
                        {
                            "path": path,
                            "consumers": f"App 'compat-nginx', Container {workload['name']!r}, NFS share {path!r}",
                        }
                    ]
                finally:
                    call("container.device.delete", device_id)
                assert alert_args() == [{"path": path, "consumers": f"App 'compat-nginx', NFS share {path!r}"}]

                long_syntax = {"custom_compose_config_string": LONG_SYNTAX_COMPOSE.format(path=path)}
                with pytest.raises(ValidationErrors) as ve:
                    call("app.update", "compat-nginx", long_syntax, job=True)
                assert ve.value.errors[0].attribute == "options.force_path_conflicts"
                assert ve.value.errors[0].errmsg == f"{path} is also used by NFS share {path!r}. {RISK}"
                call("app.update", "compat-nginx", long_syntax, FORCE, job=True)

                assert alert_args() == [{"path": path, "consumers": f"App 'compat-nginx', NFS share {path!r}"}]

                # A top-level volume that binds a host directory is a bind too
                bound_volume = {"custom_compose_config_string": BOUND_VOLUME_COMPOSE.format(path=path)}
                with pytest.raises(ValidationErrors) as ve:
                    call("app.update", "compat-nginx", bound_volume, job=True)
                assert ve.value.errors[0].errmsg == f"{path} is also used by NFS share {path!r}. {RISK}"
                call("app.update", "compat-nginx", bound_volume, FORCE, job=True)
                assert warnings(path, "sharing.nfs") == [app_consumer]

                # A stopped app keeps the paths its compose declares
                call("app.stop", "compat-nginx", job=True)
                assert call("app.get_instance", "compat-nginx")["state"] == "STOPPED"
                assert warnings(path, "sharing.nfs") == [app_consumer]
                assert alert_args() == [{"path": path, "consumers": f"App 'compat-nginx', NFS share {path!r}"}]
                with pytest.raises(ServiceValidationErrors) as ve:
                    call("sharing.smb.create", {"path": path, "name": "compat_stopped"})
                assert ve.value.errors[0].errmsg == f"{path} is also used by App 'compat-nginx'. {RISK}"

            assert alert_args() == []


def test_catalog_app_on_a_shared_path_requires_force(docker_pool):
    with dataset("compat_catalog_app") as ds:
        path = f"/mnt/{ds}"
        with smb_share(path, "compat_catalog_app"):
            payload = {"train": "community", "catalog_app": "actual-budget", "values": host_path_values(path)}
            with pytest.raises(ValidationErrors) as ve:
                with app("compat-budget", payload, {"remove_images": False}):
                    pass
            assert ve.value.errors[0].attribute == "options.force_path_conflicts"
            assert ve.value.errors[0].errmsg == f"{path} is also used by SMB share 'compat_catalog_app'. {RISK}"

            # With the ACL enabled, the host path is the `path` of the ACL, reported once
            acl = {"path": path, "entries": [{"id_type": "USER", "id": 568, "access": "FULL_CONTROL"}]}
            acl_values = {
                "storage": {"data": {"type": "host_path", "host_path_config": {"acl_enable": True, "acl": acl}}},
            }
            with pytest.raises(ValidationErrors) as ve:
                with app("compat-budget", payload | {"values": acl_values}, {"remove_images": False}):
                    pass
            assert [e.attribute for e in ve.value.errors] == ["options.force_path_conflicts"]
            assert ve.value.errors[0].errmsg == f"{path} is also used by SMB share 'compat_catalog_app'. {RISK}"

            with app("compat-budget", payload, {"remove_images": False}, FORCE):
                # The app's own ix volumes are not consumers
                assert warnings(path, "sharing.smb") == [consumer("app", "compat-budget", "compat-budget", path)]
                with pytest.raises(ValidationErrors) as ve:
                    call("app.update", "compat-budget", {"values": host_path_values(path)}, job=True)
                assert ve.value.errors[0].attribute == "options.force_path_conflicts"
                call("app.update", "compat-budget", {"values": host_path_values(path)}, FORCE, job=True)

                # An upgrade without values keeps the acknowledged path
                rewind_installed_version("compat-budget")
                call("app.upgrade", "compat-budget", job=True)

                # An upgrade with values checks the paths again, like an update does
                rewind_installed_version("compat-budget")
                with pytest.raises(ValidationErrors) as ve:
                    call("app.upgrade", "compat-budget", {"values": host_path_values(path)}, job=True)
                assert ve.value.errors[0].attribute == "options.force_path_conflicts"
                assert ve.value.errors[0].errmsg == f"{path} is also used by SMB share 'compat_catalog_app'. {RISK}"
                # A rejected upgrade leaves the app stopped
                call("app.start", "compat-budget", job=True)
                call("app.upgrade", "compat-budget", {"values": host_path_values(path)} | FORCE, job=True)
                assert call("app.get_instance", "compat-budget")["upgrade_available"] is False

                # The app keeps its paths when it is converted to a custom app
                call("app.convert_to_custom", "compat-budget", job=True)
                assert call("app.get_instance", "compat-budget")["custom_app"] is True


def test_app_upgrade_and_rollback_refresh_the_alert(docker_pool):
    with dataset("compat_catalog_upgrade") as ds:
        path = f"/mnt/{ds}"
        with smb_share(path, "compat_catalog_upgrade"):
            payload = {"train": "community", "catalog_app": "actual-budget"}
            with app("compat-budget", payload, {"remove_images": False}):
                assert listed_alert_args() == []

                # Neither an upgrade nor a rollback is a CRUD action, so each clears the checker's last run itself
                rewound = rewind_installed_version("compat-budget")
                call("app.upgrade", "compat-budget", {"values": host_path_values(path)} | FORCE, job=True)
                assert listed_alert_args() == [
                    {"path": path, "consumers": "App 'compat-budget', SMB share 'compat_catalog_upgrade'"}
                ]

                call("app.rollback", "compat-budget", {"app_version": rewound}, job=True)
                assert listed_alert_args() == []
