import errno
import socket
import ssl

from middlewared.schema import Dict, Int, Str, accepts
from middlewared.service import CallError, CRUDService, private, job

from pyVim import connect, task as VimTask
from pyVmomi import vim, vmodl


class VMWareService(CRUDService):

    class Config:
        datastore = 'storage.vmwareplugin'
        datastore_extend = 'vmware.item_extend'

    @private
    async def esxi_retrive_content(self, data):
        try:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
            ssl_context.verify_mode = ssl.CERT_NONE
            server_instance = connect.SmartConnect(
                host=data['hostname'],
                user=data['username'],
                pwd=data['password'],
                sslContext=ssl_context,
            )
        except (vim.fault.InvalidLogin, vim.fault.NoPermission, vim.fault.RestrictedVersion) as e:
            raise CallError(e.msg, errno.EPERM)
        except vmodl.RuntimeFault as e:
            raise CallError(e.msg)
        except (socket.gaierror, socket.error, OSError) as e:
            raise CallError(str(e), e.errno)

        content = server_instance.RetrieveContent()
        
        return content


    @private
    async def item_extend(self, item):
        try:
            item['password'] = await self.middleware.call('notifier.pwenc_decrypt', item['password'])
        except:
            self.logger.warn('Failed to decrypt password', exc_info=True)
        return item

    @accepts(Dict(
        'vmware-creds',
        Str('hostname'),
        Str('username'),
        Str('password'),
    ))
    async def get_datastores(self, data):
        """
        Get datastores from VMWare.
        """
        content = await self.esxi_retrive_content(data)
        objview = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.HostSystem], True
        )

        esxi_hosts = objview.view
        objview.Destroy()

        datastores = {}
        for esxi_host in esxi_hosts:
            storage_system = esxi_host.configManager.storageSystem
            datastores_host = {}

            if storage_system.fileSystemVolumeInfo is None:
                continue

            for host_mount_info in storage_system.fileSystemVolumeInfo.mountInfo:
                if host_mount_info.volume.type == 'VMFS':
                    datastores_host[host_mount_info.volume.name] = {
                        'type': host_mount_info.volume.type,
                        'uuid': host_mount_info.volume.uuid,
                        'capacity': host_mount_info.volume.capacity,
                        'vmfs_version': host_mount_info.volume.version,
                        'local': host_mount_info.volume.local,
                        'ssd': host_mount_info.volume.ssd
                    }
                elif host_mount_info.volume.type == 'NFS':
                    datastores_host[host_mount_info.volume.name] = {
                        'type': host_mount_info.volume.type,
                        'capacity': host_mount_info.volume.capacity,
                        'remote_host': host_mount_info.volume.remoteHost,
                        'remote_path': host_mount_info.volume.remotePath,
                        'remote_hostnames': host_mount_info.volume.remoteHostNames,
                        'username': host_mount_info.volume.userName,
                    }
                elif host_mount_info.volume.type == 'OTHER':
                    # Ignore OTHER type, it does not seem to be meaningful
                    pass
                else:
                    self.logger.debug(f'Unknown volume type "{host_mount_info.volume.type}": {host_mount_info.volume}')
                    continue
            datastores[esxi_host.name] = datastores_host

        connect.Disconnect(server_instance)
        return datastores


    @accepts(Int('pk'))
    async def get_virtual_machines(self, pk):
        item = await self.query([('id', '=', pk)], {'get': True})
        content = await self.esxi_retrive_content(item)
        objview = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
        vm_view = objview.view
        objview.Destroy()

        vms = {}
        for vm in vm_view:
            data = {
                'uuid': vm.config.uuid,
                'name': vm.name,
                'power_state': vm.summary.runtime.powerState,
                'datastores': [datastore.name for datastore in vm.datastore]

            }
            vms[vm.config.uuid] = data
        return vms

  
    @accepts(Int('pk'), Str('vm_uuid'), Str('snap_name'), Str('description'))
    async def create_vm_snapshot(self, pk, vm_uuid, snap_name, description):
        item = self.query([('id', '=', pk)], {'get': True})
        content = self.esxi_retrive_content(item)
        objview = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
        vm_view = objview.view
        objview.Destroy()

        for vm in vm_view:
            if vm.config.uuid == vm_uuid:
                break

        task = vm.CreateSnapshot_Task(name=snap_name, description=description, memory=False, quiesce=False)
        VimTask.WaitForTask(task)
        return task.info.state


    @accepts(Int('pk'), Str('vm_uuid'), Str('snap_name'))   
    async def delete_vm_snapshot(self, pk, vm_uuid, snap_name):
        item = await self.query([('id', '=', pk)], {'get': True})
        content = await self.esxi_retrive_content(item)
        #import pudb; pu.db
        vm = content.searchIndex.FindByUuid(None, vm_uuid, True)
        snap_to_remove = None

        tree = vm.snapshot.rootSnapshotList
        while tree[0].childSnapshotList is not None:
            snap = tree[0]
            if snap.name == snap_name:
                snap_to_remove = snap.snapshot
            if len(tree[0].childSnapshotList) < 1:
                break
            tree = tree[0].childSnapshotList
        
        if snap_to_remove is not None:
            task = snap_to_remove.RemoveSnapshot_Task(True)

            VimTask.WaitForTask(task)
            return task.info.state


