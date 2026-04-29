from __future__ import annotations

import errno
import re
import shlex
from typing import TYPE_CHECKING, Any, TypeVar
import uuid

from truenas_pylibvirt import DomainDoesNotExistError
from truenas_pylibvirt.domain.base.configuration import parse_numeric_set

from middlewared.api.current import (
    QueryOptions,
    VMCreate,
    VMDeleteOptions,
    VMDeviceDeleteOptions,
    VMDiskDevice,
    VMEntry,
    VMUpdate,
)
from middlewared.plugins.zfs.zvol_utils import zvol_path_to_name
from middlewared.pylibvirt import gather_pylibvirt_domains_states, get_pylibvirt_domain_state
from middlewared.service import CallError, CRUDServicePart, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.libvirt.utils import ACTIVE_STATES

from .capabilities import guest_architecture_and_machine_choices
from .info import (
    MAXIMUM_SUPPORTED_VCPUS,
    bootloader_ovmf_choices,
    cpu_model_choices,
    license_active,
    supports_virtualization,
    vm_flags,
)
from .lifecycle import pylibvirt_vm
from .utils import delete_vm_state, rename_vm_state, vm_state_missing_sources

if TYPE_CHECKING:
    from middlewared.utils.types import AuditCallback


RE_NAME = re.compile(r"^[a-zA-Z_0-9]+$")
VMDataT = TypeVar("VMDataT", bound=VMEntry)


class VMModel(sa.Model):
    __tablename__ = "vm_vm"

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(150))
    description = sa.Column(sa.String(250))
    vcpus = sa.Column(sa.Integer(), default=1)
    memory = sa.Column(sa.Integer())
    min_memory = sa.Column(sa.Integer(), nullable=True)
    autostart = sa.Column(sa.Boolean(), default=False)
    time = sa.Column(sa.String(5), default="LOCAL")
    bootloader = sa.Column(sa.String(50), default="UEFI")
    cores = sa.Column(sa.Integer(), default=1)
    threads = sa.Column(sa.Integer(), default=1)
    hyperv_enlightenments = sa.Column(sa.Boolean(), default=False)
    shutdown_timeout = sa.Column(sa.Integer(), default=90)
    cpu_mode = sa.Column(sa.Text())
    cpu_model = sa.Column(sa.Text(), nullable=True)
    cpuset = sa.Column(sa.Text(), default=None, nullable=True)
    nodeset = sa.Column(sa.Text(), default=None, nullable=True)
    pin_vcpus = sa.Column(sa.Boolean(), default=False)
    hide_from_msr = sa.Column(sa.Boolean(), default=False)
    suspend_on_snapshot = sa.Column(sa.Boolean(), default=False)
    ensure_display_device = sa.Column(sa.Boolean(), default=True)
    arch_type = sa.Column(sa.String(255), default=None, nullable=True)
    machine_type = sa.Column(sa.String(255), default=None, nullable=True)
    uuid = sa.Column(sa.String(255))
    command_line_args = sa.Column(sa.Text(), default="", nullable=False)
    bootloader_ovmf = sa.Column(sa.String(1024), default="OVMF_CODE.fd")
    trusted_platform_module = sa.Column(sa.Boolean(), default=False)
    enable_cpu_topology_extension = sa.Column(sa.Boolean(), default=False)
    enable_secure_boot = sa.Column(sa.Boolean(), default=False, nullable=False)


class VMServicePart(CRUDServicePart[VMEntry]):
    _datastore = "vm.vm"
    _entry = VMEntry

    def extend_context_sync(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> dict[str, Any]:
        return {
            "states": gather_pylibvirt_domains_states(
                self.middleware,
                rows,
                self.middleware.libvirt_domains_manager.vms_connection,
                lambda vm: pylibvirt_vm(self, vm),
            ),
        }

    async def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        vm_devices = await self.call2(
            self.s.vm.device.query, [["vm", "=", data["id"]]], QueryOptions(force_sql_filters=True)
        )
        data.update({
            "devices": vm_devices,
            "display_available": any(device.attributes.dtype == "DISPLAY" for device in vm_devices),
            "status": get_pylibvirt_domain_state(context["states"], data)
        })
        return data

    async def do_create(self, data: VMCreate) -> VMEntry:
        verrors = ValidationErrors()
        data = await self.validate(verrors, "vm_create", data)

        if data.bootloader_ovmf is not None and data.bootloader_ovmf not in await self.to_thread(
            bootloader_ovmf_choices
        ):
            verrors.add("vm_create.bootloader_ovmf", "Invalid bootloader ovmf choice specified")

        if data.enable_secure_boot:
            # Only q35 machine type supports secure boot
            # https://docs.openstack.org/nova/latest/admin/secure-boot.html
            updates: dict[str, Any] = {}
            if not data.machine_type:
                updates["machine_type"] = "pc-q35-6.2"
                if not data.arch_type:
                    # If arch type is not specified, we assume x86_64 architecture
                    # we set this because otherwise vm.update will fail if this is not set
                    # explicitly
                    updates["arch_type"] = "x86_64"
            elif "pc-q35" not in data.machine_type:
                verrors.add(
                    "vm_create.machine_type",
                    "Secure boot is only available in q35 machine type"
                )

            if data.bootloader_ovmf is None:
                updates["bootloader_ovmf"] = "OVMF_CODE_4M.secboot.fd"

            if updates:
                data = data.model_copy(update=updates)

            if data.bootloader_ovmf is None:
                verrors.add(
                    "vm_create.bootloader_ovmf",
                    "Bootloader OVMF must be specified when secure boot is enabled"
                )
            elif "secboot" not in data.bootloader_ovmf.lower():
                verrors.add(
                    "vm_create.bootloader_ovmf",
                    "Select a bootloader_ovmf that supports secure boot i.e OVMF_CODE_4M.secboot.fd"
                )

        if data.bootloader_ovmf is None:
            data = data.model_copy(update={"bootloader_ovmf": "OVMF_CODE_4M.fd"})

        verrors.check()

        entry = await self._create(data.model_dump())
        await self.middleware.call("etc.generate", "libvirt_guests")
        return entry

    async def do_update(self, id_: int, data: VMUpdate, *, audit_callback: AuditCallback) -> VMEntry:
        old = await self.get_instance(id_)
        new = old.updated(data)
        audit_callback(new.name)

        if new.name != old.name:
            if old.status.state in ACTIVE_STATES:
                raise CallError("VM name can only be changed when VM is inactive")

        verrors = ValidationErrors()
        await self.validate(verrors, "vm_update", new, old=old)
        verrors.check()

        renamed = False
        if new.name != old.name:
            try:
                await self.to_thread(rename_vm_state, old.id, old.name, new.id, new.name)
            except FileExistsError as e:
                raise CallError(
                    f"Cannot rename VM {old.name!r} -> {new.name!r}: on-disk state already "
                    "exists at the destination (likely stale NVRAM/TPM left over from a "
                    "previously deleted VM). Name change aborted; VM configuration is unchanged."
                ) from e
            except OSError as e:
                raise CallError(
                    f"Failed to rename VM state for {old.name!r} -> {new.name!r}: "
                    f"{e.strerror or e} (errno={e.errno}). Name change aborted; "
                    f"VM configuration is unchanged."
                ) from e
            renamed = True

            missing = await self.to_thread(
                vm_state_missing_sources, new.id, new.name,
                old.bootloader, old.trusted_platform_module,
            )
            if missing:
                self.logger.warning(
                    "%s: rename to %r proceeded with no prior on-disk state for %s; "
                    "libvirt/swtpm will initialise fresh state on next start.",
                    old.name, new.name, ", ".join(missing),
                )

        try:
            entry = await self._update(id_, new.model_dump(exclude={"id", "devices", "display_available", "status"}))
        except Exception:
            if renamed:
                try:
                    await self.to_thread(rename_vm_state, new.id, new.name, old.id, old.name)
                except Exception:
                    self.logger.error(
                        "%s: state-file rollback failed after DB update failure",
                        old.name, exc_info=True,
                    )
            raise

        if old.shutdown_timeout != new.shutdown_timeout:
            await self.middleware.call("etc.generate", "libvirt_guests")

        return entry

    def do_delete(self, id_: int, data: VMDeleteOptions, *, audit_callback: AuditCallback) -> None:
        vm = self.get_instance__sync(id_)
        audit_callback(vm.name)

        if data.zvols:
            disk_devices = self.call_sync2(
                self.s.vm.device.query,
                [("vm", "=", id_), ("attributes.dtype", "=", "DISK")]
            )
            for device in disk_devices:
                if not isinstance(device.attributes, VMDiskDevice):
                    continue
                if not device.attributes.path or not device.attributes.path.startswith("/dev/zvol/"):
                    continue

                disk_name = zvol_path_to_name(device.attributes.path)
                try:
                    self.call_sync2(self.s.zfs.resource.destroy_impl, disk_name, recursive=True)
                except Exception:
                    if not data.force:
                        raise

                    self.logger.error(
                        "Failed to delete %r volume when removing %r VM", disk_name, vm.name, exc_info=True
                    )

        pylibvirt_vm_obj = pylibvirt_vm(self, vm.model_dump(by_alias=True, context={"expose_secrets": True}))
        try:
            self.middleware.libvirt_domains_manager.vms.delete(pylibvirt_vm_obj)
        except DomainDoesNotExistError:
            pass

        for device in vm.devices:
            self.call_sync2(self.s.vm.device.delete, device.id, VMDeviceDeleteOptions(force=False))

        self.run_coroutine(self._delete(id_))
        try:
            delete_vm_state(vm.id, vm.name)
        except Exception:
            self.logger.error(
                "%s: failed to remove on-disk VM state (nvram/tpm)", vm.name, exc_info=True,
            )
        self.middleware.call_sync("etc.generate", "libvirt_guests")

    async def validate(
        self, verrors: ValidationErrors, schema_name: str, data: VMDataT, old: VMEntry | None = None,
    ) -> VMDataT:
        if data.uuid is None:
            data = data.model_copy(update={"uuid": str(uuid.uuid4())})

        if not await license_active(self):
            verrors.add(f"{schema_name}.name", "System is not licensed to use VMs")

        if data.min_memory and data.min_memory > data.memory:
            verrors.add(
                f"{schema_name}.min_memory",
                "Minimum memory should not be greater than defined/maximum memory"
            )

        try:
            shlex.split(data.command_line_args)
        except ValueError as e:
            verrors.add(f"{schema_name}.command_line_args", f"Parse error: {e.args[0]}")

        vcpus = data.vcpus * data.cores * data.threads
        if vcpus:
            flags = await vm_flags(self)
            if vcpus > MAXIMUM_SUPPORTED_VCPUS:
                verrors.add(
                    f"{schema_name}.vcpus",
                    f'Maximum {MAXIMUM_SUPPORTED_VCPUS} vcpus are supported.'
                    f'Please ensure the product of "{schema_name}.vcpus", "{schema_name}.cores" and '
                    f'"{schema_name}.threads" is less than {MAXIMUM_SUPPORTED_VCPUS}.'
                )
            elif flags.intel_vmx:
                if vcpus > 1 and flags.unrestricted_guest is False:
                    verrors.add(f"{schema_name}.vcpus", "Only one Virtual CPU is allowed in this system.")
            elif flags.amd_rvi:
                if vcpus > 1 and flags.amd_asids is False:
                    verrors.add(f"{schema_name}.vcpus", "Only one virtual CPU is allowed in this system.")
            elif not await self.to_thread(supports_virtualization):
                verrors.add(schema_name, "This system does not support virtualization.")

        if data.arch_type or data.machine_type:
            choices = await self.to_thread(guest_architecture_and_machine_choices, self)
            if data.arch_type and data.arch_type not in choices:
                verrors.add(
                    f"{schema_name}.arch_type",
                    "Specified architecture type is not supported on this system"
                )
            if data.machine_type:
                if not data.arch_type:
                    verrors.add(
                        f"{schema_name}.arch_type",
                        f'Must be specified when "{schema_name}.machine_type" is set'
                    )
                elif data.arch_type in choices and data.machine_type not in choices[data.arch_type]:
                    verrors.add(
                        f"{schema_name}.machine_type",
                        f"Specified machine type is not supported for {choices[data.arch_type]!r} architecture type"
                    )

        if data.cpu_mode != "CUSTOM" and data.cpu_model:
            verrors.add(
                f"{schema_name}.cpu_model",
                'This attribute should not be specified when "cpu_mode" is not "CUSTOM".'
            )
        elif data.cpu_model and data.cpu_model not in await self.to_thread(cpu_model_choices):
            verrors.add(f"{schema_name}.cpu_model", "Please select a valid CPU model.")

        if not old or data.name != old.name:
            filters: list[tuple[str, str, Any]] = [("name", "=", data.name)]
            if old:
                filters.append(("id", "!=", old.id))
            if await self.middleware.call("datastore.query", "vm.vm", filters):
                verrors.add(f"{schema_name}.name", "This name already exists.", errno.EEXIST)
            elif not RE_NAME.search(data.name):
                verrors.add(f"{schema_name}.name", "Only alphanumeric characters are allowed.")

        if data.pin_vcpus:
            if not data.cpuset:
                verrors.add(
                    f"{schema_name}.cpuset",
                    f'Must be specified when "{schema_name}.pin_vcpus" is set.'
                )
            elif len(parse_numeric_set(data.cpuset)) != vcpus:
                verrors.add(
                    f"{schema_name}.pin_vcpus",
                    f'Number of cpus in "{schema_name}.cpuset" must be equal to total number '
                    'vcpus if pinning is enabled.'
                )

        # TODO: Let's please implement PCI express hierarchy as the limit on devices in KVM is quite high
        # with reports of users having thousands of disks
        # Let's validate that the VM has the correct no of slots available to accommodate currently configured devices

        return data
