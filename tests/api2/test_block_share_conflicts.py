import contextlib
import errno

import pytest

from middlewared.service_exception import ValidationError, ValidationErrors
from truenas_api_client import ValidationErrors as ClientValidationErrors
from middlewared.test.integration.assets.iscsi import iscsi_extent
from middlewared.test.integration.assets.nvmet import nvmet_namespace, nvmet_subsys
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.vm import vm, vm_device
from middlewared.test.integration.utils import call, pool, ssh

MiB = 1024 * 1024


@pytest.fixture(scope="module")
def conflict_vm():
    with vm({"name": "conflict_vm"}) as instance:
        yield instance


@contextlib.contextmanager
def zvol(name):
    with dataset(name, {"type": "VOLUME", "volsize": MiB}) as ds:
        yield ds


@pytest.mark.parametrize("name,link", [("conflict_zvol", "conflict_zvol"), ("conflict zvol", "conflict+zvol")])
def test_vm_disk_rejects_zvol_used_by_iscsi_extent(conflict_vm, name, link):
    with zvol(name):
        with iscsi_extent({"name": "conflict_extent", "type": "DISK", "disk": f"zvol/{pool}/{link}"}):
            with pytest.raises(ValidationErrors) as ve:
                call(
                    "vm.device.create",
                    {
                        "vm": conflict_vm["id"],
                        "attributes": {"dtype": "DISK", "path": f"/dev/zvol/{pool}/{link}"},
                    },
                )

            assert ve.value.errors == [
                ValidationError(
                    "attributes.path",
                    "Disk currently in use by iSCSI extent conflict_extent",
                )
            ]


def test_vm_disk_rejects_zvol_used_by_nvmet_namespace(conflict_vm):
    with zvol("conflict_zvol") as ds, nvmet_subsys("conflict_subsys") as subsys:
        with nvmet_namespace(subsys["id"], f"zvol/{ds}") as ns:
            with pytest.raises(ValidationErrors) as ve:
                call(
                    "vm.device.create",
                    {
                        "vm": conflict_vm["id"],
                        "attributes": {"dtype": "DISK", "path": f"/dev/zvol/{ds}"},
                    },
                )

            assert ve.value.errors == [
                ValidationError(
                    "attributes.path",
                    f"Disk currently in use by NVMe-oF subsystem conflict_subsys NSID {ns['nsid']}",
                )
            ]


def test_vm_disk_update_rejects_zvol_used_by_iscsi_extent(conflict_vm):
    with zvol("conflict_free") as free, zvol("conflict_used") as used:
        with (
            iscsi_extent({"name": "conflict_extent", "type": "DISK", "disk": f"zvol/{used}"}),
            vm_device(conflict_vm["id"], {"dtype": "DISK", "path": f"/dev/zvol/{free}"}) as device,
        ):
            with pytest.raises(ValidationErrors) as ve:
                call("vm.device.update", device["id"], {"attributes": {"path": f"/dev/zvol/{used}"}})

            assert ve.value.errors == [
                ValidationError(
                    "attributes.path",
                    "Disk currently in use by iSCSI extent conflict_extent",
                )
            ]


@pytest.mark.parametrize("name,link", [("conflict_zvol", "conflict_zvol"), ("conflict zvol", "conflict+zvol")])
def test_iscsi_extent_rejects_zvol_used_by_vm_disk(conflict_vm, name, link):
    with zvol(name):
        with vm_device(conflict_vm["id"], {"dtype": "DISK", "path": f"/dev/zvol/{pool}/{link}"}):
            with pytest.raises(ValidationErrors) as ve:
                call(
                    "iscsi.extent.create",
                    {
                        "name": "conflict_extent",
                        "type": "DISK",
                        "disk": f"zvol/{pool}/{link}",
                    },
                )

            assert ve.value.errors == [
                ValidationError(
                    "iscsi_extent_create.disk",
                    "Disk currently in use by VM conflict_vm",
                )
            ]


def test_iscsi_extent_update_rejects_zvol_used_by_vm_disk(conflict_vm):
    with zvol("conflict_free") as free, zvol("conflict_used") as used:
        with (
            iscsi_extent({"name": "conflict_extent", "type": "DISK", "disk": f"zvol/{free}"}) as extent,
            vm_device(conflict_vm["id"], {"dtype": "DISK", "path": f"/dev/zvol/{used}"}),
        ):
            with pytest.raises(ValidationErrors) as ve:
                call("iscsi.extent.update", extent["id"], {"disk": f"zvol/{used}"})

            assert ve.value.errors == [
                ValidationError(
                    "iscsi_extent_update.disk",
                    "Disk currently in use by VM conflict_vm",
                )
            ]


def test_nvmet_namespace_rejects_zvol_used_by_vm_disk(conflict_vm):
    with zvol("conflict_zvol") as ds, nvmet_subsys("conflict_subsys") as subsys:
        with vm_device(conflict_vm["id"], {"dtype": "DISK", "path": f"/dev/zvol/{ds}"}):
            with pytest.raises(ValidationErrors) as ve:
                call(
                    "nvmet.namespace.create",
                    {
                        "subsys_id": subsys["id"],
                        "device_type": "ZVOL",
                        "device_path": f"zvol/{ds}",
                    },
                )

            assert ve.value.errors == [
                ValidationError(
                    "nvmet_namespace_create.device_path",
                    "Disk currently in use by VM conflict_vm",
                )
            ]


def test_nvmet_namespace_update_rejects_zvol_used_by_vm_disk(conflict_vm):
    with zvol("conflict_free") as free, zvol("conflict_used") as used, nvmet_subsys("conflict_subsys") as subsys:
        with (
            nvmet_namespace(subsys["id"], f"zvol/{free}") as ns,
            vm_device(conflict_vm["id"], {"dtype": "DISK", "path": f"/dev/zvol/{used}"}),
        ):
            with pytest.raises(ValidationErrors) as ve:
                call("nvmet.namespace.update", ns["id"], {"device_path": f"zvol/{used}"})

            assert ve.value.errors == [
                ValidationError(
                    "nvmet_namespace_update.device_path",
                    "Disk currently in use by VM conflict_vm",
                )
            ]


def test_nvmet_namespace_update_rejects_file_used_by_vm_raw(conflict_vm):
    with dataset("conflict_files") as ds, nvmet_subsys("conflict_subsys") as subsys:
        free, used = f"/mnt/{ds}/free.img", f"/mnt/{ds}/used.img"
        with (
            nvmet_namespace(subsys["id"], free, device_type="FILE", filesize=MiB) as ns,
            vm_device(conflict_vm["id"], {"dtype": "RAW", "path": used, "exists": False, "size": MiB}),
        ):
            with pytest.raises(ValidationErrors) as ve:
                call("nvmet.namespace.update", ns["id"], {"device_path": used})

            assert ve.value.errors == [
                ValidationError(
                    "nvmet_namespace_update.device_path",
                    "File currently in use by VM conflict_vm",
                )
            ]


def test_vm_raw_rejects_file_used_by_iscsi_extent(conflict_vm):
    with dataset("conflict_files") as ds:
        path = f"/mnt/{ds}/disk.img"
        with iscsi_extent({"name": "conflict_extent", "type": "FILE", "path": path, "filesize": MiB}):
            with pytest.raises(ValidationErrors) as ve:
                call(
                    "vm.device.create",
                    {
                        "vm": conflict_vm["id"],
                        "attributes": {"dtype": "RAW", "path": path, "exists": True},
                    },
                )

            assert ve.value.errors == [
                ValidationError(
                    "attributes.path",
                    "File currently in use by iSCSI extent conflict_extent",
                )
            ]


def test_vm_raw_rejects_file_used_by_nvmet_namespace(conflict_vm):
    with dataset("conflict_files") as ds, nvmet_subsys("conflict_subsys") as subsys:
        path = f"/mnt/{ds}/disk.img"
        with nvmet_namespace(subsys["id"], path, device_type="FILE", filesize=MiB) as ns:
            with pytest.raises(ValidationErrors) as ve:
                call(
                    "vm.device.create",
                    {
                        "vm": conflict_vm["id"],
                        "attributes": {"dtype": "RAW", "path": path, "exists": True},
                    },
                )

            assert ve.value.errors == [
                ValidationError(
                    "attributes.path",
                    f"File currently in use by NVMe-oF subsystem conflict_subsys NSID {ns['nsid']}",
                )
            ]


def test_iscsi_extent_rejects_file_used_by_vm_raw(conflict_vm):
    with dataset("conflict_files") as ds:
        path = f"/mnt/{ds}/disk.img"
        with vm_device(conflict_vm["id"], {"dtype": "RAW", "path": path, "exists": False, "size": MiB}):
            with pytest.raises(ValidationErrors) as ve:
                call("iscsi.extent.create", {"name": "conflict_extent", "type": "FILE", "path": path, "filesize": MiB})

            assert ve.value.errors == [
                ValidationError(
                    "iscsi_extent_create.path",
                    "File currently in use by VM conflict_vm",
                )
            ]


def test_nvmet_namespace_rejects_file_used_by_vm_raw(conflict_vm):
    with dataset("conflict_files") as ds, nvmet_subsys("conflict_subsys") as subsys:
        path = f"/mnt/{ds}/disk.img"
        with vm_device(conflict_vm["id"], {"dtype": "RAW", "path": path, "exists": False, "size": MiB}):
            with pytest.raises(ValidationErrors) as ve:
                call(
                    "nvmet.namespace.create",
                    {
                        "subsys_id": subsys["id"],
                        "device_type": "FILE",
                        "device_path": path,
                        "filesize": MiB,
                    },
                )

            assert ve.value.errors == [
                ValidationError(
                    "nvmet_namespace_create.device_path",
                    "File currently in use by VM conflict_vm",
                )
            ]


def test_nvmet_namespace_rejects_space_zvol_used_by_iscsi_extent():
    with zvol("conflict zvol") as ds, nvmet_subsys("conflict_subsys") as subsys:
        with iscsi_extent({"name": "conflict_extent", "type": "DISK", "disk": f"zvol/{pool}/conflict+zvol"}):
            with pytest.raises(ValidationErrors) as ve:
                call(
                    "nvmet.namespace.create",
                    {
                        "subsys_id": subsys["id"],
                        "device_type": "ZVOL",
                        "device_path": f"zvol/{ds}",
                    },
                )

            assert ve.value.errors == [
                ValidationError(
                    "nvmet_namespace_create.device_path",
                    "Disk currently in use by iSCSI extent conflict_extent",
                )
            ]


def test_iscsi_extent_rejects_space_zvol_used_by_nvmet_namespace():
    with zvol("conflict zvol") as ds, nvmet_subsys("conflict_subsys") as subsys:
        with nvmet_namespace(subsys["id"], f"zvol/{ds}") as ns:
            with pytest.raises(ValidationErrors) as ve:
                call(
                    "iscsi.extent.create",
                    {
                        "name": "conflict_extent",
                        "type": "DISK",
                        "disk": f"zvol/{pool}/conflict+zvol",
                    },
                )

            assert ve.value.errors == [
                ValidationError(
                    "iscsi_extent_create.disk",
                    f"Disk currently in use by NVMe-oF subsystem conflict_subsys NSID {ns['nsid']}",
                )
            ]


def test_nvmet_namespace_rejects_space_zvol_used_by_other_namespace():
    with zvol("conflict zvol") as ds, nvmet_subsys("conflict_subsys") as subsys:
        with nvmet_namespace(subsys["id"], f"zvol/{ds}") as ns:
            with pytest.raises(ValidationErrors) as ve:
                call(
                    "nvmet.namespace.create",
                    {
                        "subsys_id": subsys["id"],
                        "device_type": "ZVOL",
                        "device_path": f"zvol/{pool}/conflict+zvol",
                    },
                )

            assert ve.value.errors == [
                ValidationError(
                    "nvmet_namespace_create.device_path",
                    f"Disk currently in use by NVMe-oF subsystem conflict_subsys NSID {ns['nsid']}",
                )
            ]


def test_convert_image_rejects_zvol_used_by_iscsi_extent():
    with dataset("conflict_files") as ds, zvol("conflict_zvol") as zv:
        image = f"/mnt/{ds}/source.raw"
        ssh(f"truncate -s 1M {image}")
        with iscsi_extent({"name": "conflict_extent", "type": "DISK", "disk": f"zvol/{zv}"}):
            with pytest.raises(ClientValidationErrors) as ve:
                call("vm.device.convert", {"source": image, "destination": f"/dev/zvol/{zv}"}, job=True)

            assert ve.value.errors == [
                (
                    "vm.device.convert.destination",
                    "Disk currently in use by iSCSI extent conflict_extent",
                    errno.EINVAL,
                ),
            ]


def test_vm_disk_can_be_shared_between_two_vms(conflict_vm):
    with zvol("conflict_zvol") as ds, vm({"name": "other_vm"}) as other:
        with vm_device(other["id"], {"dtype": "DISK", "path": f"/dev/zvol/{ds}"}):
            with vm_device(conflict_vm["id"], {"dtype": "DISK", "path": f"/dev/zvol/{ds}"}):
                pass


def test_disk_choices_follow_block_storage_registry(conflict_vm):
    with zvol("conflict_zvol") as ds:
        with vm_device(conflict_vm["id"], {"dtype": "DISK", "path": f"/dev/zvol/{ds}"}):
            assert f"zvol/{ds}" not in call("iscsi.extent.disk_choices")
            assert f"/dev/zvol/{ds}" in call("vm.device.disk_choices")

        with iscsi_extent({"name": "conflict_extent", "type": "DISK", "disk": f"zvol/{ds}"}):
            assert f"zvol/{ds}" not in call("iscsi.extent.disk_choices")
            assert f"/dev/zvol/{ds}" not in call("vm.device.disk_choices")


def test_vm_raw_update_rejects_file_used_by_iscsi_extent(conflict_vm):
    with dataset("conflict_files") as ds:
        free, used = f"/mnt/{ds}/free.img", f"/mnt/{ds}/used.img"
        with (
            iscsi_extent({"name": "conflict_extent", "type": "FILE", "path": used, "filesize": MiB}),
            vm_device(conflict_vm["id"], {"dtype": "RAW", "path": free, "exists": False, "size": MiB}) as device,
        ):
            with pytest.raises(ValidationErrors) as ve:
                call("vm.device.update", device["id"], {"attributes": {"path": used, "exists": True}})

            assert ve.value.errors == [
                ValidationError(
                    "attributes.path",
                    "File currently in use by iSCSI extent conflict_extent",
                )
            ]


def test_convert_image_into_unused_zvol():
    with dataset("conflict_files") as ds, zvol("conflict_zvol") as zv:
        image = f"/mnt/{ds}/source.raw"
        ssh(f"truncate -s 1M {image}")
        call("vm.device.convert", {"source": image, "destination": f"/dev/zvol/{zv}"}, job=True)


def test_convert_image_into_zvol_attached_to_stopped_vm(conflict_vm):
    with dataset("conflict_files") as ds, zvol("conflict_zvol") as zv:
        image = f"/mnt/{ds}/source.raw"
        ssh(f"truncate -s 1M {image}")
        with vm_device(conflict_vm["id"], {"dtype": "DISK", "path": f"/dev/zvol/{zv}"}):
            call("vm.device.convert", {"source": image, "destination": f"/dev/zvol/{zv}"}, job=True)


def test_iscsi_extent_already_sharing_zvol_with_vm_stays_editable(conflict_vm):
    with zvol("conflict_free") as free, zvol("conflict_used") as used, zvol("conflict_other") as other:
        with (
            iscsi_extent({"name": "conflict_extent", "type": "DISK", "disk": f"zvol/{free}"}) as extent,
            vm_device(conflict_vm["id"], {"dtype": "DISK", "path": f"/dev/zvol/{used}"}),
            vm_device(conflict_vm["id"], {"dtype": "DISK", "path": f"/dev/zvol/{other}"}),
        ):
            call(
                "datastore.update",
                "services.iscsitargetextent",
                extent["id"],
                {"iscsi_target_extent_path": f"zvol/{used}"},
            )

            call("iscsi.extent.update", extent["id"], {"comment": "still editable"})
            call("iscsi.extent.update", extent["id"], {"disk": f"zvol/{used}", "comment": "still editable"})
            call("pool.dataset.update", used, {"readonly": "ON"})
            assert call("iscsi.extent.get_instance", extent["id"])["ro"] is True
            call("iscsi.extent.update", extent["id"], {"enabled": False})

            with pytest.raises(ValidationErrors) as ve:
                call("iscsi.extent.update", extent["id"], {"disk": f"zvol/{other}"})

            assert ve.value.errors == [
                ValidationError("iscsi_extent_update.disk", "Disk currently in use by VM conflict_vm")
            ]


def test_nvmet_namespace_already_sharing_zvol_with_vm_stays_editable(conflict_vm):
    with (
        zvol("conflict_free") as free,
        zvol("conflict_used") as used,
        zvol("conflict_other") as other,
        nvmet_subsys("conflict_subsys") as subsys,
    ):
        with (
            nvmet_namespace(subsys["id"], f"zvol/{free}") as ns,
            vm_device(conflict_vm["id"], {"dtype": "DISK", "path": f"/dev/zvol/{used}"}),
            vm_device(conflict_vm["id"], {"dtype": "DISK", "path": f"/dev/zvol/{other}"}),
        ):
            call(
                "datastore.update",
                "services.nvmet_namespace",
                ns["id"],
                {"nvmet_namespace_device_path": f"zvol/{used}"},
            )

            call("nvmet.namespace.update", ns["id"], {"device_path": f"zvol/{used}"})
            call("nvmet.namespace.update", ns["id"], {"enabled": False})

            with pytest.raises(ValidationErrors) as ve:
                call("nvmet.namespace.update", ns["id"], {"device_path": f"zvol/{other}"})

            assert ve.value.errors == [
                ValidationError("nvmet_namespace_update.device_path", "Disk currently in use by VM conflict_vm")
            ]


def test_vm_disk_already_sharing_zvol_with_iscsi_extent_stays_editable(conflict_vm):
    with zvol("conflict_free") as free, zvol("conflict_used") as used, zvol("conflict_other") as other:
        with (
            iscsi_extent({"name": "conflict_extent", "type": "DISK", "disk": f"zvol/{used}"}),
            iscsi_extent({"name": "conflict_extent_other", "type": "DISK", "disk": f"zvol/{other}"}),
            vm_device(conflict_vm["id"], {"dtype": "DISK", "path": f"/dev/zvol/{free}"}) as device,
        ):
            call(
                "datastore.update",
                "vm.device",
                device["id"],
                {"attributes": {**device["attributes"], "path": f"/dev/zvol/{used}"}},
            )

            call("vm.device.update", device["id"], {"attributes": {"path": f"/dev/zvol/{used}"}})
            call("vm.device.update", device["id"], {"order": 1005})

            with pytest.raises(ValidationErrors) as ve:
                call("vm.device.update", device["id"], {"attributes": {"path": f"/dev/zvol/{other}"}})

            assert ve.value.errors == [
                ValidationError("attributes.path", "Disk currently in use by iSCSI extent conflict_extent_other")
            ]


def test_iscsi_extent_already_sharing_file_with_vm_raw_stays_editable(conflict_vm):
    with dataset("conflict_files") as ds:
        free, used, other = (f"/mnt/{ds}/{name}.img" for name in ("free", "used", "other"))
        with (
            iscsi_extent({"name": "conflict_extent", "type": "FILE", "path": free, "filesize": MiB}) as extent,
            vm_device(conflict_vm["id"], {"dtype": "RAW", "path": used, "exists": False, "size": MiB}),
            vm_device(conflict_vm["id"], {"dtype": "RAW", "path": other, "exists": False, "size": MiB}),
        ):
            call(
                "datastore.update",
                "services.iscsitargetextent",
                extent["id"],
                {"iscsi_target_extent_path": used},
            )

            call("iscsi.extent.update", extent["id"], {"comment": "still editable"})
            call("iscsi.extent.update", extent["id"], {"path": used, "comment": "still editable"})
            call("iscsi.extent.update", extent["id"], {"enabled": False})

            with pytest.raises(ValidationErrors) as ve:
                call("iscsi.extent.update", extent["id"], {"path": other})

            assert ve.value.errors == [
                ValidationError("iscsi_extent_update.path", "File currently in use by VM conflict_vm")
            ]


def test_nvmet_namespace_already_sharing_file_with_vm_raw_stays_editable(conflict_vm):
    with dataset("conflict_files") as ds, nvmet_subsys("conflict_subsys") as subsys:
        free, used, other = (f"/mnt/{ds}/{name}.img" for name in ("free", "used", "other"))
        with (
            nvmet_namespace(subsys["id"], free, device_type="FILE", filesize=MiB) as ns,
            vm_device(conflict_vm["id"], {"dtype": "RAW", "path": used, "exists": False, "size": MiB}),
            vm_device(conflict_vm["id"], {"dtype": "RAW", "path": other, "exists": False, "size": MiB}),
        ):
            call(
                "datastore.update",
                "services.nvmet_namespace",
                ns["id"],
                {"nvmet_namespace_device_path": used},
            )

            call("nvmet.namespace.update", ns["id"], {"device_path": used})
            call("nvmet.namespace.update", ns["id"], {"enabled": False})

            with pytest.raises(ValidationErrors) as ve:
                call("nvmet.namespace.update", ns["id"], {"device_path": other})

            assert ve.value.errors == [
                ValidationError("nvmet_namespace_update.device_path", "File currently in use by VM conflict_vm")
            ]


def test_vm_raw_already_sharing_file_with_iscsi_extent_stays_editable(conflict_vm):
    with dataset("conflict_files") as ds:
        free, used, other = (f"/mnt/{ds}/{name}.img" for name in ("free", "used", "other"))
        with (
            iscsi_extent({"name": "conflict_extent", "type": "FILE", "path": used, "filesize": MiB}),
            iscsi_extent({"name": "conflict_extent_other", "type": "FILE", "path": other, "filesize": MiB}),
            vm_device(conflict_vm["id"], {"dtype": "RAW", "path": free, "exists": False, "size": MiB}) as device,
        ):
            call(
                "datastore.update",
                "vm.device",
                device["id"],
                {"attributes": {**device["attributes"], "path": used}},
            )

            call("vm.device.update", device["id"], {"attributes": {"path": used}})
            call("vm.device.update", device["id"], {"order": 1005})

            with pytest.raises(ValidationErrors) as ve:
                call("vm.device.update", device["id"], {"attributes": {"path": other, "exists": True}})

            assert ve.value.errors == [
                ValidationError("attributes.path", "File currently in use by iSCSI extent conflict_extent_other")
            ]


def test_nvmet_namespace_already_sharing_zvol_with_vm_stays_editable_when_respelled(conflict_vm):
    # A zvol with a space in its name is reachable both as `zvol/pool/conflict zvol` and, the way udev
    # spells it, `zvol/pool/conflict+zvol`. Resubmitting the other spelling is not a new claim.
    with (
        zvol("conflict_free") as free,
        zvol("conflict zvol") as used,
        nvmet_subsys("conflict_subsys") as subsys,
    ):
        link = f"zvol/{pool}/conflict+zvol"
        with (
            nvmet_namespace(subsys["id"], f"zvol/{free}") as ns,
            vm_device(conflict_vm["id"], {"dtype": "DISK", "path": f"/dev/{link}"}),
        ):
            call(
                "datastore.update",
                "services.nvmet_namespace",
                ns["id"],
                {"nvmet_namespace_device_path": f"zvol/{used}"},
            )

            call("nvmet.namespace.update", ns["id"], {"device_path": link})

            assert call("nvmet.namespace.get_instance", ns["id"])["device_path"] == link
