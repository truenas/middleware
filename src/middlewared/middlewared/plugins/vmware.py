import errno
import socket
import ssl

from middlewared.schema import Dict, Int, Ref, Str, accepts
from middlewared.service import CallError, Service

from pyVim import connect
from pyVmomi import vim


class VMWareService(Service):

    @accepts(Ref('query-filters'), Ref('query-options'))
    def query(self, filters=None, options=None):
        if options is None:
            options = {}
        options['extend'] = 'vmware.item_extend'
        return self.middleware.call('datastore.query', 'storage.vmwareplugin', filters, options)

    def item_extend(self, item):
        try:
            item['password'] = self.middleware.call('notifier.pwenc_decrypt', item['password'])
        except:
            self.logger.warn('Failed to decrypt password', exc_info=True)
        return item

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
        except (vim.fault.InvalidLogin, vim.fault.NoPermission) as e:
            raise CallError(e.msg, errno.EPERM)
        except (socket.gaierror, OSError) as e:
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
                if host_mount_info.volume.type != 'VMFS':
                    continue

                datastores_host[host_mount_info.volume.name] = {
                    'uuid': host_mount_info.volume.uuid,
                    'capacity': host_mount_info.volume.capacity,
                    'vmfs_version': host_mount_info.volume.version,
                    'local': host_mount_info.volume.local,
                    'ssd': host_mount_info.volume.ssd
                }
            datastores[esxi_host.name] = datastores_host

        connect.Disconnect(server_instance)
        return datastores

    @accepts(Int('pk'))
    def get_virtual_machines(self, pk):

        item = self.query([('id', '=', pk)], {'get': True})

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
