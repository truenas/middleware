import configparser
import os
import requests
import shutil
import zipfile


from contextlib import closing
from datetime import datetime

from middlewared.plugins.crypto import get_context_object
from middlewared.schema import Bool, Dict, Int, Patch, Ref, Str
from middlewared.service import accepts, ConfigService, private, Service, ValidationError, ValidationErrors
from middlewared.validators import IpAddress


from pyVim.connect import SmartConnect
from pyVmomi import vim

from pprint import pprint


class VCenterService(ConfigService):

    class Config:
        datastore = 'vcp.vcenterconfiguration'
        datastore_prefix = 'vc_'
        datastore_extend = ''

    async def do_update(self, data):
        old = await self.config()
        pprint(old)
        return old

    async def plugin_root_path(self):
        return await self.middleware.call('notifier.gui_static_root')
    
    @private
    async def get_management_ip_choices(self):
        # TODO: Make sure this returns all the relevant management ips
        ip_list = self.middleware.call(
            'interfaces.ip_in_use', {
                'ipv4': True
            }
        )

        return [ip_dict['address'] for ip_dict in ip_list]
    
    @private
    def get_plugin_file_name(self):
        # TODO: The path to the plugin should be moved over to middlewared from django
        root_path = self.middleware.call_sync('vcenter.plugin_root_path')
        return next(v for v in os.listdir(root_path) if 'plugin' in v and '.zip' in v)
    
    @private
    def get_plugin_version(self):
        file_name = self.get_plugin_file_name()
        return file_name.split('_')[1]

    @private
    def extract_zip(self, src_path, dest_path):
        if not os.path.exists(dest_path):
            os.makedirs(dest_path)
        with zipfile.ZipFile(src_path) as zip_f:
            zip_f.extractall(dest_path)

    @private
    def zipdir(self, src_path, dest_path):
        # TODO: CAN THIS BE IMPROVED ?
        assert os.path.isdir(src_path)
        with closing(zipfile.ZipFile(dest_path, "w")) as z:

            for root, dirs, files in os.walk(src_path):
                for fn in files:
                    absfn = os.path.join(root, fn)
                    zfn = absfn[len(src_path) + len(os.sep):]
                    z.write(absfn, zfn)

    @private
    def remove_directory(self, dest_path):
        if os.path.exists(dest_path):
            shutil.rmtree(dest_path)
    
    @accepts(
        Dict(
            'update_vcp_plugin_zipfile',
            Int('port', required=True),
            Str('ip', required=True, validators=[IpAddress()]),
            Str('install_mode', required=True),  # TODO: Would this require an enum ?
            Str('plugin_version_old', required=True),
            Str('plugin_version_new', required=True),
            Str('password', required=True, password=True),  # should be encrypted
            Str('username', required=True),
            register=True
        )
    )
    def _update_plugin_zipfile(self, data):
        file_name = self.get_plugin_file_name()
        plugin_root_path = self.middleware.call_sync('vcenter.plugin_root_path')

        self.extract_zip(
            os.path.join(plugin_root_path, file_name),
            os.path.join(plugin_root_path, 'plugin')
        )
        self.extract_zip(
            os.path.join(plugin_root_path, 'plugin/plugins/ixsystems-vcp-service.jar'),
            os.path.join(plugin_root_path, 'plugin/plugins/ixsystems-vcp-service')
        )

        data['fpath'] = os.path.join(
            plugin_root_path,
            'plugin/plugins/ixsystems-vcp-service/META-INF/config/install.properties'
        )

        self.__create_property_file(data)
        self.zipdir(
            os.path.join(plugin_root_path, 'plugin/plugins/ixsystems-vcp-service'),
            os.path.join(plugin_root_path, 'plugin/plugins/ixsystems-vcp-service.jar')
        )
        self.remove_directory(os.path.join(plugin_root_path, 'plugin/plugins/ixsystems-vcp-service'))

        shutil.make_archive(
            os.path.join(plugin_root_path, file_name[0:-4]),
            'zip',
            os.path.join(plugin_root_path, 'plugin')
        )

        self.remove_directory(os.path.join(plugin_root_path, 'plugin'))

    @accepts(
        Patch(
            'update_vcp_plugin_zipfile', '__create_property_file',
            ('add', {'name': 'fpath', 'type': 'str'}),
        )
    )
    def __create_property_file(self, data):
        # Password encrypted using notifier.pwenc_encrypt

        config = configparser.ConfigParser()
        with open(data['fpath'], 'w') as config_file:
            config.add_section('installation_parameter')
            config.set('installation_parameter', 'ip', data['ip'])
            config.set('installation_parameter', 'username', data['username'])
            config.set('installation_parameter', 'port', str(data['port']))
            config.set('installation_parameter', 'password', data['password'])
            config.set('installation_parameter', 'install_mode', data['install_mode'])
            config.set(
                'installation_parameter',
                'plugin_version_old',
                data['plugin_version_old'])
            config.set(
                'installation_parameter',
                'plugin_version_new',
                data['plugin_version_new'])
            config.write(config_file)
    

class VCenterPluginService(Service):

    PRIVATE_GROUP_NAME = 'iXSystems'

    @private
    async def property_file_path(self):
        return os.path.join(
            (await self.middleware.call('notifier.gui_base_path')),
            'vcp/Extensionconfig.ini.dist'
        )

    @private
    async def resource_folder_path(self):
        return os.path.join(
            (await self.middleware.call('notifier.gui_base_path')),
            'vcp/vcp_locales'
        )

    @private
    def create_event_keyvalue_pairs(self):
        try:
            eri_list = []
            resource_folder_path = self.middleware.call_sync('vcenterplugin.resource_folder_path')
            for file in os.listdir(resource_folder_path):
                eri = vim.Extension.ResourceInfo()

                #Read locale file from vcp_locale
                eri.module = file.split("_")[0]
                with open(os.path.join(resource_folder_path, file), 'r') as file:
                    for line in file:
                        if len(line) > 2 and '=' in line:
                            if 'locale' in line:
                                eri.locale = line.split('=')[1].lstrip().rstrip()
                            else:
                                prop = line.split('=')
                                key_val = vim.KeyValue()
                                key_val.key = prop[0].lstrip().rstrip()
                                key_val.value = prop[1].lstrip().rstrip()
                                eri.data.append(key_val)
                eri_list.append(eri)
            return eri_list
        except Exception as e:
            raise ValidationError(
                'vcenterplugin.create_event_keyvalue_pairs',
                f'Can not read locales : {e}'
            )

    @private
    def get_extension_key(self):
        cp = configparser.ConfigParser()
        cp.read(self.middleware.call_sync('vcenterplugin.property_file_path'))
        return cp.get('RegisterParam', 'key')

    @accepts(
        Dict(
            'install_vcenter_plugin',
            Int('port', required=True),
            Str('fingerprint', required=True),
            Str('client_url', required=True),
            Str('ip', required=True),  # HOST IP
            Str('password', password=True, required=True),  # Password should be decrypted
            Str('username', required=True),
            register=True
        )
    )
    def install_vcenter_plugin(self, data):
        try:
            si = SmartConnect(
                "https", data['ip'], data['port'],
                data['username'], data['password'], sslContext=get_context_object()
            )
            ext = self.get_extension(data['client_url'], data['fingerprint'])

            si.RetrieveServiceContent().extensionManager.RegisterExtension(ext)

        except vim.fault.NoPermission:
            raise ValidationError(
                'vcenterplugin.install_vcenter_plugin',
                'VCenter user has no permission to install the plugin'
            )

    @accepts(
        Patch(
            'install_vcenter_plugin', 'uninstall_vcenter_plugin',
            ('rm', {'name': 'fingerprint'}),
            ('rm', {'name': 'client_url'}),
            register=True
        )
    )
    def uninstall_vcenter_plugin(self, data):
        try:
            si = SmartConnect(
                "https", data['ip'], data['port'],
                data['username'], data['password'], sslContext=get_context_object()
            )
            extkey = self.get_extension_key()

            si.RetrieveServiceContent().extensionManager.UnregisterExtension(extkey)
        except vim.fault.NoPermission:
            raise ValidationError(
                'vcenterplugin.uninstall_vcenter_plugin',
                'VCenter user has no permission to uninstall the plugin'
            )

    @accepts(
        Ref('install_vcenter_plugin')
    )
    def upgrade_vcenter_plugin(self, data):
        try:
            si = SmartConnect(
                "https", data['ip'], data['port'],
                data['username'], data['password'], sslContext=get_context_object()
            )
            ext = self.get_extension(data['client_url'], data['fingerprint'])

            si.RetrieveServiceContent().extensionManager.UpdateExtension(ext)
        except vim.fault.NoPermission:
            raise ValidationError(
                'vcenterplugin.upgrade_vcenter_plugin',
                'VCenter user has no permission to upgrade the plugin'
            )

    @accepts(
        Ref('uninstall_vcenter_plugin')
    )
    def find_plugin(self, data):
        try:
            si = SmartConnect(
                "https", data['ip'], data['port'],
                data['username'], data['password'], sslContext=get_context_object()
            )
            extkey = self.get_extension_key()
            ext = si.RetrieveServiceContent().extensionManager.FindExtension(extkey)
            if ext is None:
                return False
            else:
                # TODO: REFINE THIS
                try:
                    return 'TruNAS System : ' + ext.client[0].url.split('/')[2]
                except Exception:
                    return 'TruNAS System :'
        except vim.fault.NoPermission:
            raise ValidationError(
                'vcenterplugin.uninstall_vcenter_plugin',
                'VCenter user has no permission to perform this operation'
            )

    @accepts(
        Ref('uninstall_vcenter_plugin')
    )
    def check_credentials(self, data):
        try:
            si = SmartConnect(
                "https", data['ip'], data['port'],
                data['username'], data['password'], sslContext=get_context_object()
            )
            if si is None:
                return False
            else:
                return True

        except requests.exceptions.ConnectionError:
            raise ValidationError(
                'vcenterplugin.ip',
                'Provided vCenter Hostname/IP or port are not valid'
            )
        except vim.fault.InvalidLogin:
            raise ValidationError(
                'vcenterplugin.username',
                'Provided vCenter credentials are not valid ( username or password )'
            )
        except vim.fault.NoPermission:
            raise ValidationError(
                'vcenterplugin.check_credentials',
                'vCenter user does not have permission to perform this operation'
            )
        except Exception as e:
            # TODO: SHOULD AN EXCEPTION BE LOGGED TO MIDDLEWARED LOGS ?
            raise ValidationError(
                'vcenterplugin.check_credentials',
                str(e)
            )
            #return 'Internal Error. Please contact support.'

    @private
    def get_extension(self, vcp_url, fingerprint):
        try:
            cp = configparser.ConfigParser()
            cp.read(self.middleware.call_sync('vcenterplugin.property_file_path'))
            version = self.middleware.call_sync('vcenter.get_plugin_version')

            description = vim.Description()
            description.label = cp.get('RegisterParam', 'label')
            description.summary = cp.get('RegisterParam', 'description')

            ext = vim.Extension()
            ext.company = cp.get('RegisterParam', 'company')
            ext.version = version
            ext.key = cp.get('RegisterParam', 'key')
            ext.description = description
            ext.lastHeartbeatTime = datetime.now()

            server_info = vim.Extension.ServerInfo()
            server_info.serverThumbprint = fingerprint
            server_info.type = vcp_url.split(':')[0].upper()  # sysgui protocol
            server_info.url = vcp_url
            server_info.description = description
            server_info.company = cp.get('RegisterParam', 'company')
            server_info.adminEmail = ['ADMIN EMAIL']
            ext.server = [server_info]

            client = vim.Extension.ClientInfo()
            client.url = vcp_url
            client.company = cp.get('RegisterParam', 'company')
            client.version = version
            client.description = description
            client.type = "vsphere-client-serenity"
            ext.client = [client]

            event_info = []
            for e in cp.get('RegisterParam', 'events').split(","):
                ext_event_type_info = vim.Extension.EventTypeInfo()
                ext_event_type_info.eventID = e
                event_info.append(ext_event_type_info)

            task_info = []
            for t in cp.get('RegisterParam', 'tasks').split(","):
                ext_type_info = vim.Extension.TaskTypeInfo()
                ext_type_info.taskID = t
                task_info.append(ext_type_info)

            # Register custom privileges required for vcp RBAC
            priv_info = []
            for priv in cp.get('RegisterParam', 'auth').split(","):
                ext_type_info = vim.Extension.PrivilegeInfo()
                ext_type_info.privID = priv
                ext_type_info.privGroupName = self.PRIVATE_GROUP_NAME
                priv_info.append(ext_type_info)

            ext.taskList = task_info
            ext.eventList = event_info
            ext.privilegeList = priv_info

            resource_list = self.create_event_keyvalue_pairs()
            ext.resourceList = resource_list

            return ext
        except configparser.NoOptionError as e:
            raise ValidationError(
                'vcenterplugin.get_extension',
                f'Property Missing : {e}'
            )

