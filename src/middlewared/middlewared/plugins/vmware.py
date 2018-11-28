import errno
import socket
import ssl

from middlewared.async_validators import resolve_hostname
from middlewared.schema import accepts, Dict, Int, Str, Patch
from middlewared.service import CallError, CRUDService, private, ValidationErrors

from pyVim import connect
from pyVmomi import vim, vmodl


class VMWareService(CRUDService):

    class Config:
        datastore = 'storage.vmwareplugin'
        datastore_extend = 'vmware.item_extend'

    @private
    async def item_extend(self, item):
        try:
            item['password'] = await self.middleware.call('notifier.pwenc_decrypt', item['password'])
        except Exception:
            self.logger.warn('Failed to decrypt password', exc_info=True)
        return item

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

            datastores = []
            for i in ds.values():
                datastores += i.keys()
            if data.get('datastore') not in datastores:
                verrors.add(
                    f'{schema_name}.datastore',
                    f'Datastore "{datastore}" not found on the server'
                )
        except Exception as e:
            verrors.add(
                f'{schema_name}.datastore',
                'Failed to connect: ' + str(e)
            )

        if verrors:
            raise verrors

    @accepts(
        Dict(
            'vmware_create',
            Str('datastore', required=True),
            Str('filesystem', required=True),
            Str('hostname', required=True),
            Str('password', password=True, required=True),
            Str('username', required=True),
            register=True
        )
    )
    async def do_create(self, data):
        await self.validate_data(data, 'vmware_create')

        data['password'] = await self.middleware.call(
            'notifier.pwenc_encrypt',
            data['password']
        )

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data
        )

        return await self._get_instance(data['id'])

    @accepts(
        Int('id', required=True),
        Patch('vmware_create', 'vmware_update', ('attr', {'update': True}))
    )
    async def do_update(self, id, data):
        old = await self._get_instance(id)
        new = old.copy()

        new.update(data)

        await self.validate_data(new, 'vmware_update')

        new['password'] = await self.middleware.call(
            'notifier.pwenc_encrypt',
            new['password']
        )

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
        )

        return await self._get_instance(id)

    @accepts(
        Int('id')
    )
    async def do_delete(self, id):

        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

        return response

    @accepts(Dict(
        'vmware-creds',
        Str('hostname'),
        Str('username'),
        Str('password'),
    ))
    def get_datastores(self, data):
        """
        Get datastores from VMWare.
        """
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
                elif host_mount_info.volume.type in ('OTHER', 'VFFS'):
                    # Ignore VFFS type, it does not store VM's
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

        ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        ssl_context.verify_mode = ssl.CERT_NONE
        server_instance = connect.SmartConnect(
            host=item['hostname'],
            user=item['username'],
            pwd=item['password'],
            sslContext=ssl_context,
        )

        content = server_instance.RetrieveContent()
        objview = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
        vm_view = objview.view
        objview.Destroy()

        vms = {}
        for vm in vm_view:
            data = {
                'uuid': vm.config.uuid,
                'name': vm.name,
                'power_state': vm.summary.runtime.powerState,
            }
            vms[vm.config.uuid] = data
        return vms
