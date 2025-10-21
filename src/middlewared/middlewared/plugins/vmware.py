from collections import defaultdict
from datetime import datetime
import errno
import socket
import ssl
from typing import Any
import uuid

from pydantic import Secret
from pyVim import connect, task as VimTask
from pyVmomi import vim, vmodl

from middlewared.api import api_method
from middlewared.api.base import BaseModel
from middlewared.api.current import (
    VMWareEntry,
    VMWareCreateArgs, VMWareCreateResult,
    VMWareUpdateArgs, VMWareUpdateResult,
    VMWareDeleteArgs, VMWareDeleteResult,
    VMWareGetDatastoresArgs, VMWareGetDatastoresResult,
    VMWareMatchDatastoresWithDatasetsArgs, VMWareMatchDatastoresWithDatasetsResult,
    VMWareDatasetHasVmsArgs, VMWareDatasetHasVmsResult,
)
from middlewared.async_validators import resolve_hostname
from middlewared.service import CallError, CRUDService, job, private, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.time_utils import utc_now
from middlewared.utils.zfs import query_imported_fast_impl

NFS_VOLUME_TYPES = ('NFS', 'NFS41')


class VMWarePeriodicSnapshotTaskProceedArgs(BaseModel):
    context: Secret[Any]


class VMWarePeriodicSnapshotTaskProceedResult(BaseModel):
    result: Any


class VMWarePeriodicSnapshotTaskEndArgs(BaseModel):
    context: Secret[Any]


class VMWarePeriodicSnapshotTaskEndResult(BaseModel):
    result: Any


class VMWareModel(sa.Model):
    __tablename__ = 'storage_vmwareplugin'

    id = sa.Column(sa.Integer(), primary_key=True)
    hostname = sa.Column(sa.String(200))
    username = sa.Column(sa.String(200))
    password = sa.Column(sa.EncryptedText())
    filesystem = sa.Column(sa.String(200))
    datastore = sa.Column(sa.String(200))
    state = sa.Column(sa.JSON())


class VMWareService(CRUDService):

    class Config:
        datastore = 'storage.vmwareplugin'
        cli_namespace = 'storage.vmware'
        entry = VMWareEntry
        role_prefix = 'SNAPSHOT_TASK'

    @private
    async def validate_data(self, data, schema_name):
        verrors = ValidationErrors()

        await resolve_hostname(self.middleware, verrors, f'{schema_name}.hostname', data['hostname'])

        if data['filesystem'] not in (await self.middleware.call('pool.filesystem_choices')):
            verrors.add(
                f'{schema_name}.filesystem',
                'Invalid ZFS filesystem'
            )

        datastore = data.get('datastore')
        try:
            ds = await self.middleware.run_in_thread(
                self.get_datastores,
                {
                    'hostname': data.get('hostname'),
                    'username': data.get('username'),
                    'password': data.get('password'),
                }
            )

            if data.get('datastore') not in ds:
                verrors.add(
                    f'{schema_name}.datastore',
                    f'Datastore "{datastore}" not found on the server'
                )
        except Exception as e:
            verrors.add(
                f'{schema_name}.datastore',
                'Failed to connect: ' + str(e)
            )

        verrors.check()

    @api_method(VMWareCreateArgs, VMWareCreateResult)
    async def do_create(self, data):
        """
        Create VMWare snapshot.
        """
        await self.middleware.call('vmware.validate_data', data, 'vmware_create')

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            {**data, 'state': {'state': 'PENDING'}},
        )

        return await self.get_instance(data['id'])

    @api_method(VMWareUpdateArgs, VMWareUpdateResult)
    async def do_update(self, id_, data):
        """
        Update VMWare snapshot of `id`.
        """
        old = await self.get_instance(id_)
        old.pop('state')
        new = old.copy()

        new.update(data)

        await self.middleware.call('vmware.validate_data', new, 'vmware_update')

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id_,
            {**new, 'state': {'state': 'PENDING'}},
        )

        await self.middleware.call("alert.oneshot_delete", "VMWareLoginFailed", old["hostname"])

        return await self.get_instance(id_)

    @api_method(VMWareDeleteArgs, VMWareDeleteResult)
    async def do_delete(self, id_):
        """
        Delete VMWare snapshot of `id`.
        """

        vmsnapobj = await self.get_instance(id_)

        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id_
        )

        await self.middleware.call("alert.oneshot_delete", "VMWareLoginFailed", vmsnapobj["hostname"])

        return response

    @api_method(VMWareGetDatastoresArgs, VMWareGetDatastoresResult, roles=['READONLY_ADMIN'])
    def get_datastores(self, data):
        """
        Get datastores from VMWare.
        """
        return sorted(list(self.__get_datastores(data).keys()))

    @api_method(
        VMWareMatchDatastoresWithDatasetsArgs,
        VMWareMatchDatastoresWithDatasetsResult,
        roles=['READONLY_ADMIN'],
    )
    def match_datastores_with_datasets(self, data):
        """
        Requests datastores from vCenter server and tries to match them with local filesystems.

        Returns a list of datastores, a list of local filesystems and guessed relationship between them.
        """

        datastores = []
        for k, v in self.__get_datastores(data).items():
            if v["type"] in NFS_VOLUME_TYPES:
                description = f"NFS mount {v['remote_path']!r} on {' or '.join(v['remote_hostnames'])}"
                matches = [f"{hostname}:{v['remote_path']}" for hostname in v["remote_hostnames"]]
            elif v["type"] == "VMFS":
                description = (
                    f"iSCSI extent {', '.join(v['extent'])}"
                    if any(extent.startswith("naa.") for extent in v["extent"])
                    else ", ".join(v["extent"])
                )
                matches = v["extent"]
            else:
                self.logger.debug("Unknown volume type %r", v["type"])
                continue

            datastores.append({
                "name": k,
                "description": description,
                "matches": matches,
            })

        ip_addresses = sum([
            [alias["address"] for alias in interface["state"]["aliases"] if alias["type"] in ["INET", "INET6"]]
            for interface in self.middleware.call_sync("interface.query")
        ], [])
        iscsi_extents = defaultdict(list)
        for extent in self.middleware.call_sync("iscsi.extent.query", [], {"select": ["path", "naa"]}):
            if extent["path"].startswith("zvol/"):
                zvol = extent["path"][len("zvol/"):]
                iscsi_extents[zvol].append(f"naa.{extent['naa'][2:]}")
        filesystems = []
        zpools = [i["name"] for i in query_imported_fast_impl().values()]
        options = {"extra": {"retrieve_properties": False}}
        for fs in self.middleware.call_sync("pool.dataset.query", [("pool", "in", zpools)], options):
            if fs["type"] == "FILESYSTEM":
                filesystems.append({
                    "type": "FILESYSTEM",
                    "name": fs["name"],
                    "description": f"NFS mount {fs['mountpoint']!r} on {' or '.join(ip_addresses)}",
                    "matches": [f"{ip_address}:{fs['mountpoint']}" for ip_address in ip_addresses],
                })

            if fs["type"] == "VOLUME":
                filesystems.append({
                    "type": "VOLUME",
                    "name": fs["name"],
                    "description": (
                        f"iSCSI extent {', '.join(iscsi_extents[fs['name']])}"
                        if iscsi_extents[fs["name"]]
                        else "Not shared via iSCSI"
                    ),
                    "matches": iscsi_extents[fs["name"]],
                })

        for datastore in datastores:
            datastore["filesystems"] = [filesystem["name"] for filesystem in filesystems
                                        if set(filesystem["matches"]) & set(datastore["matches"])]
            datastore.pop("matches")

        for filesystem in filesystems:
            filesystem.pop("matches")

        return {
            "datastores": sorted(datastores, key=lambda datastore: datastore["name"]),
            "filesystems": sorted(filesystems, key=lambda filesystem: filesystem["name"]),
        }

    def __get_datastores(self, data):
        self.middleware.call_sync('network.general.will_perform_activity', 'vmware')

        try:
            server_instance = self.connect(data)
        except (vim.fault.InvalidLogin, vim.fault.NoPermission, vim.fault.RestrictedVersion) as e:
            raise CallError(e.msg, errno.EPERM)
        except vmodl.RuntimeFault as e:
            raise CallError(e.msg)
        except (socket.gaierror, socket.error, OSError) as e:
            raise CallError(str(e), e.errno)

        content = server_instance.RetrieveContent()
        objview = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.HostSystem], True
        )

        esxi_hosts = objview.view
        objview.Destroy()

        datastores = {}
        for esxi_host in esxi_hosts:
            storage_system = esxi_host.configManager.storageSystem

            if storage_system.fileSystemVolumeInfo is None:
                continue

            for host_mount_info in storage_system.fileSystemVolumeInfo.mountInfo:
                if host_mount_info.volume.type == 'VMFS':
                    datastores[host_mount_info.volume.name] = {
                        'type': host_mount_info.volume.type,
                        'uuid': host_mount_info.volume.uuid,
                        'capacity': host_mount_info.volume.capacity,
                        'vmfs_version': host_mount_info.volume.version,
                        'extent': [
                            partition.diskName
                            for partition in host_mount_info.volume.extent
                        ],
                        'local': host_mount_info.volume.local,
                        'ssd': host_mount_info.volume.ssd
                    }
                elif host_mount_info.volume.type in NFS_VOLUME_TYPES:
                    datastores[host_mount_info.volume.name] = {
                        'type': host_mount_info.volume.type,
                        'capacity': host_mount_info.volume.capacity,
                        'remote_host': host_mount_info.volume.remoteHost,
                        'remote_path': host_mount_info.volume.remotePath,
                        'remote_hostnames': host_mount_info.volume.remoteHostNames,
                        'username': host_mount_info.volume.userName,
                    }
                elif host_mount_info.volume.type in ('other', 'OTHER', 'VFFS'):
                    # Ignore VFFS type, it does not store VM's
                    # Ignore other type, it does not seem to be meaningful
                    pass
                else:
                    self.logger.debug(f'Unknown volume type "{host_mount_info.volume.type}": {host_mount_info.volume}')
                    continue

        connect.Disconnect(server_instance)

        return datastores

    @api_method(VMWareDatasetHasVmsArgs, VMWareDatasetHasVmsResult, roles=['READONLY_ADMIN'])
    def dataset_has_vms(self, dataset, recursive):
        """
        Returns "true" if `dataset` is configured with a VMWare snapshot
        """
        return len(self._dataset_get_vms(dataset, recursive)) > 0

    def _dataset_get_vms(self, dataset, recursive):
        f = ["filesystem", "=", dataset]
        if recursive:
            f = [
                "OR", [
                    f,
                    ["filesystem", "^", dataset + "/"],
                ],
            ]
        return self.middleware.call_sync("vmware.query", [f])

    @private
    def snapshot_begin(self, dataset, recursive):
        qs = self._dataset_get_vms(dataset, recursive)
        return self.snapshot_proceed(dataset, qs)

    @private
    def snapshot_proceed(self, dataset, qs):
        # Generate a unique snapshot name that won't collide with anything that exists on the VMWare side.
        vmsnapname = str(uuid.uuid4())

        # Generate a helpful description that is visible on the VMWare side.  Since we
        # are going to be creating VMWare snaps, if one gets left dangling this will
        # help determine where it came from.
        vmsnapdescription = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} TrueNAS Created Snapshot"

        # We keep track of snapshots per VMWare "task" because we are going to iterate
        # over all the VMWare tasks for a given ZFS filesystem, do all the VMWare snapshotting
        # then take the ZFS snapshot, then iterate again over all the VMWare "tasks" and undo
        # all the snaps we created in the first place.
        vmsnapobjs = []
        for vmsnapobj in qs:
            if not self.middleware.call_sync('network.general.can_perform_activity', 'vmware'):
                self.set_vmsnapobj_state(vmsnapobj, {
                    "state": "BLOCKED",
                })
                continue

            # Data structures that will be used to keep track of VMs that are snapped,
            # as wel as VMs we tried to snap and failed, and VMs we realized we couldn't
            # snapshot.
            snapvms = []
            snapvmfails = []
            snapvmskips = []

            try:
                si = self.connect(vmsnapobj)
                content = si.RetrieveContent()
            except Exception as e:
                self.logger.warning("VMware login to %s failed", vmsnapobj["hostname"], exc_info=True)
                self.alert_vmware_login_failed(vmsnapobj, e)
                continue

            # There's no point to even consider VMs that are paused or powered off.
            vm_view = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
            for vm in vm_view.view:
                if vm.summary.runtime.powerState != "poweredOn":
                    continue

                if self._doesVMDependOnDataStore(vm, vmsnapobj["datastore"]):
                    try:
                        if self._canSnapshotVM(vm):
                            if not self._findVMSnapshotByName(vm, vmsnapname):
                                # have we already created a snapshot of the VM for this volume
                                # iteration? can happen if the VM uses two datasets (a and b)
                                # where both datasets are mapped to the same ZFS volume in TrueNAS.
                                VimTask.WaitForTask(vm.CreateSnapshot_Task(
                                    name=vmsnapname,
                                    description=vmsnapdescription,
                                    memory=False, quiesce=True,
                                ))
                            else:
                                self.logger.debug("Not creating snapshot %s for VM %s because it "
                                                  "already exists", vmsnapname, vm)
                        else:
                            # TODO:
                            # we can try to shutdown the VM, if the user provided us an ok to do
                            # so (might need a new list property in obj to know which VMs are
                            # fine to shutdown and a UI to specify such exceptions)
                            # otherwise can skip VM snap and then make a crash-consistent zfs
                            # snapshot for this VM
                            self.logger.info("Can't snapshot VM %s that depends on "
                                             "datastore %s and filesystem %s. "
                                             "Possibly using PT devices. Skipping.",
                                             vm.name, vmsnapobj["datastore"], dataset)
                            snapvmskips.append([vm.config.uuid, vm.name])
                    except Exception as e:
                        self.logger.warning("Snapshot of VM %s failed", vm.name, exc_info=True)
                        self.middleware.call_sync("alert.oneshot_create", "VMWareSnapshotCreateFailed", {
                            "hostname": vmsnapobj["hostname"],
                            "vm": vm.name,
                            "snapshot": vmsnapname,
                            "error": self._vmware_exception_message(e),
                        })
                        snapvmfails.append([vm.config.uuid, vm.name])

                    snapvms.append(vm.config.uuid)

            self.disconnect(si)

            vmsnapobjs.append({
                "vmsnapobj": vmsnapobj,
                "snapvms": snapvms,
                "snapvmfails": snapvmfails,
                "snapvmskips": snapvmskips,
            })

        # At this point we've completed snapshotting VMs.

        if not vmsnapobjs:
            return None

        return {
            "vmsnapname": vmsnapname,
            "vmsnapobjs": vmsnapobjs,
            "vmsynced": vmsnapobjs and all(len(vmsnapobj["snapvms"]) > 0 and len(vmsnapobj["snapvmfails"]) == 0
                                           for vmsnapobj in vmsnapobjs)
        }

    @private
    def snapshot_end(self, context):
        self.middleware.call_sync('network.general.will_perform_activity', 'vmware')

        vmsnapname = context["vmsnapname"]

        for elem in context["vmsnapobjs"]:
            vmsnapobj = elem["vmsnapobj"]

            try:
                si = self.connect(vmsnapobj)
                self.delete_vmware_login_failed_alert(vmsnapobj)
            except Exception as e:
                self.logger.warning("VMware login failed to %s", vmsnapobj["hostname"])
                self.alert_vmware_login_failed(vmsnapobj, e)
                continue

            # vm is an object, so we'll dereference that object anywhere it's user facing.
            for vm_uuid in elem["snapvms"]:
                for vm in self.find_vms_by_uuid(si, vm_uuid):
                    if [vm_uuid, vm.name] not in elem["snapvmfails"] and [vm_uuid, vm.name] not in elem["snapvmskips"]:
                        try:
                            self.delete_snapshot(vm, vmsnapname)
                        except Exception as e:
                            self.logger.debug(
                                "Exception removing snapshot %s on %s", vmsnapname, vm.name, exc_info=True
                            )
                            self.middleware.call_sync("alert.oneshot_create", "VMWareSnapshotDeleteFailed", {
                                "hostname": vmsnapobj["hostname"],
                                "vm": vm.name,
                                "snapshot": vmsnapname,
                                "error": self._vmware_exception_message(e),
                            })

            self.disconnect(si)

    @private
    def periodic_snapshot_task_begin(self, task_id):
        task = self.middleware.call_sync("pool.snapshottask.query",
                                         [["id", "=", task_id]],
                                         {"get": True})

        # If there's a VMWare Plugin object for this filesystem
        # snapshot the VMs before taking the ZFS snapshot.
        # Once we've taken the ZFS snapshot we're going to log back in
        # to VMWare and destroy all the VMWare snapshots we created.
        # We do this because having VMWare snapshots in existence impacts
        # the performance of your VMs.
        qs = self._dataset_get_vms(task["dataset"], task["recursive"])
        if qs:
            return {
                "dataset": task["dataset"],
                "qs": qs,
            }

    @api_method(VMWarePeriodicSnapshotTaskProceedArgs, VMWarePeriodicSnapshotTaskProceedResult, private=True)
    @job()
    def periodic_snapshot_task_proceed(self, job, context):
        return self.snapshot_proceed(context["dataset"], context["qs"])

    @api_method(VMWarePeriodicSnapshotTaskEndArgs, VMWarePeriodicSnapshotTaskEndResult, private=True)
    @job()
    def periodic_snapshot_task_end(self, job, context):
        return self.snapshot_end(context)

    @private
    def connect(self, vmsnapobj):
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        ssl_context.verify_mode = ssl.CERT_NONE
        si = connect.SmartConnect(host=vmsnapobj["hostname"], user=vmsnapobj["username"],
                                  pwd=vmsnapobj["password"], sslContext=ssl_context)
        return si

    @private
    def disconnect(self, si):
        connect.Disconnect(si)

    @private
    def find_vms_by_uuid(self, si, vm_uuid):
        return si.content.searchIndex.FindAllByUuid(None, vm_uuid, True)

    @private
    def delete_snapshot(self, vm, vmsnapname):
        snap = self._findVMSnapshotByName(vm, vmsnapname)
        if snap:
            VimTask.WaitForTask(snap.RemoveSnapshot_Task(True))

    # Check if a VM is using a certain datastore
    def _doesVMDependOnDataStore(self, vm, dataStore):
        try:
            # simple case, VM config data is on a datastore.
            # not sure how critical it is to snapshot the store that has config data, but best to do so
            for i in vm.datastore:
                if i.info.name.startswith(dataStore):
                    return True
            # check if VM has disks on the data store
            # we check both "diskDescriptor" and "diskExtent" types of files
            for device in vm.config.hardware.device:
                if device.backing is None:
                    continue
                if hasattr(device.backing, 'fileName'):
                    if device.backing.datastore is None:
                        continue
                    if device.backing.datastore.info.name == dataStore:
                        return True
        except Exception:
            self.logger.debug('Exception in doesVMDependOnDataStore', exc_info=True)

        return False

    # check if VMware can snapshot a VM
    def _canSnapshotVM(self, vm):
        try:
            # check for PCI pass-through devices
            for device in vm.config.hardware.device:
                if isinstance(device, vim.VirtualPCIPassthrough):
                    return False
            # consider supporting more cases of VMs that can't be snapshoted
            # https://kb.vmware.com/selfservice/microsites/search.do?language=en_US&cmd=displayKC&externalId=1006392
        except Exception:
            self.logger.debug('Exception in canSnapshotVM', exc_info=True)

        return True

    def _findVMSnapshotByName(self, vm, snapshotName):
        try:
            if vm.snapshot is None:
                return None

            for tree in vm.snapshot.rootSnapshotList:
                result = self._findVMSnapshotByNameInTree(tree, snapshotName)
                if result:
                    return result
        except Exception:
            self.logger.debug('Exception in _findVMSnapshotByName', exc_info=True)

        return None

    def _findVMSnapshotByNameInTree(self, tree, snapshotName):
        if tree.name == snapshotName:
            return tree.snapshot

        for i in tree.childSnapshotList:
            if i.name == snapshotName:
                return i.snapshot

            if hasattr(i, "childSnapshotList"):
                result = self._findVMSnapshotByNameInTree(i, snapshotName)
                if result:
                    return result

        return None

    def _vmware_exception_message(self, e):
        if hasattr(e, "msg"):
            return e.msg
        else:
            return str(e)

    @private
    def alert_vmware_login_failed(self, vmsnapobj, e):
        error = self._vmware_exception_message(e)
        self.middleware.call_sync("alert.oneshot_create", "VMWareLoginFailed", {
            "hostname": vmsnapobj["hostname"],
            "error": error,
        })
        self.set_vmsnapobj_state(vmsnapobj, {
            "state": "ERROR",
            "error": error,
        })

    @private
    def delete_vmware_login_failed_alert(self, vmsnapobj):
        self.middleware.call_sync("alert.oneshot_delete", "VMWareLoginFailed", vmsnapobj["hostname"])
        self.set_vmsnapobj_state(vmsnapobj, {
            "state": "SUCCESS",
        })

    @private
    def set_vmsnapobj_state(self, vmsnapobj, state):
        for vmware in self.middleware.call_sync(
            "datastore.query",
            "storage.vmwareplugin",
            [["hostname", "=", vmsnapobj["hostname"]],
             ["username", "=", vmsnapobj["username"]]],
        ):
            if vmware["password"] == vmsnapobj["password"]:  # These need to be decoded to be compared
                self.set_vmsnapobj_state_by_id(vmware["id"], state)

    @private
    def set_vmsnapobj_state_by_id(self, id_, state):
        self.middleware.call_sync("datastore.update", "storage.vmwareplugin", id_, {
            "state": {
                **state,
                "datetime": utc_now(),
            },
        })


async def setup(middleware):
    await middleware.call('network.general.register_activity', 'vmware', 'VMware Snapshots')
