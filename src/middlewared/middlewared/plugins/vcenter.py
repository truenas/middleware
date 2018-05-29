import configparser
import os
import shutil
import socket
import zipfile


from contextlib import closing
from datetime import datetime
from pkg_resources import parse_version
from pyVim.connect import SmartConnect
from pyVmomi import vim


from middlewared.async_validators import resolve_hostname
from middlewared.plugins.crypto import get_context_object
from middlewared.schema import Bool, Dict, Int, Patch, Ref, Str
from middlewared.service import accepts, ConfigService, private, ValidationError, ValidationErrors
from middlewared.validators import IpAddress, Port


class VCenterService(ConfigService):

    PRIVATE_GROUP_NAME = 'iXSystems'

    class Config:
        datastore = 'vcp.vcenterconfiguration'
        datastore_prefix = 'vc_'
        datastore_extend = 'vcenter.vcenter_extend'

    @private
    async def common_validation(self, data, schema_name):
        verrors = ValidationErrors()

        ip = data.get('ip')
        if ip:
            await resolve_hostname(self.middleware, verrors, f'{schema_name}.ip', ip)

        management_ip = data.get('management_ip')
        if management_ip and management_ip not in (await self.get_management_ip_choices()):
            verrors.add(
                f'{schema_name}.management_ip',
                'Please select a valid IP for your TrueNAS system'
            )

        action = data.get('action')
        if action and action != 'UNINSTALL':
            if (
                not (await self.middleware.call('vcenteraux.config'))['enable_https'] and
                (await self.middleware.call('system.general.config'))['ui_protocol'].upper() == 'HTTPS'
            ):
                verrors.add(
                    f'{schema_name}.action',
                    'Please enable vCenter plugin over HTTPS'
                )

        return verrors

    @private
    async def vcenter_extend(self, data):
        data['password'] = await self.middleware.call('notifier.pwenc_decrypt', data['password'])
        data['port'] = int(data['port']) if data['port'] else 443  # Defaulting to 443
        return data

    @accepts(
        Dict(
            'vcenter_update_dict',
            Int('port', validators=[Port()]),
            Str('action', enum=['INSTALL', 'REPAIR', 'UNINSTALL', 'UPGRADE'], required=True),
            Str('management_ip'),
            Str('ip'),  # HOST IP
            Str('password', password=True),
            Str('username'),
        )
    )
    async def do_update(self, data):
        old = await self.config()
        new = old.copy()
        new.update(data)

        schema_name = 'vcenter_update'
        verrors = await self.common_validation(new, schema_name)
        if verrors:
            raise verrors

        action = new.pop('action')
        system_general = await self.middleware.call('system.general.config')
        ui_protocol = system_general['ui_protocol']
        ui_port = system_general['ui_port'] if ui_protocol.lower() != 'https' else system_general['ui_httpsport']
        fingerprint = await self.middleware.call(
            'certificate.get_host_certificates_thumbprint',
            new['management_ip'], new['port']
        )
        plugin_file_name = await self.middleware.run_in_io_thread(
            self.get_plugin_file_name
        )
        # TODO: Is legacy valid in the mgmt addr ?
        management_addr = f'{ui_protocol}://{new["management_ip"]}:{ui_port}/legacy/static/{plugin_file_name}'

        install_dict = {
            'port': new['port'],
            'fingerprint': fingerprint,
            'management_ip': management_addr,
            'ip': new['ip'],
            'password': new['password'],
            'username': new['username']
        }

        if action == 'INSTALL':

            if new['installed']:
                verrors.add(
                    f'{schema_name}.action',
                    'Plugin is already installed'
                )
            else:

                for r_key in ('management_ip', 'ip', 'password', 'port', 'username'):
                    if not new[r_key]:
                        verrors.add(
                            f'{schema_name}.{r_key}',
                            'This field is required to install the plugin'
                        )

                if verrors:
                    raise verrors

                try:
                    await self.middleware.run_in_io_thread(
                        self.__install_vcenter_plugin,
                        install_dict
                    )
                except ValidationError as e:
                    verrors.add_validation_error(e)
                else:
                    new['version'] = await self.middleware.run_in_io_thread(self.get_plugin_version)
                    new['installed'] = True

        elif action == 'REPAIR':

            if not new['installed']:
                verrors.add(
                    f'{schema_name}.action',
                    'Plugin is not installed. Please install it first'
                )
            else:
                
                # FROM MY UNDERSTANDING REPAIR IS CALLED WHEN THE DATABASE APPARENTLY TELLS THAT THE PLUGIN IS PRESENT
                # BUT THE SYSTEM FAILS TO RECOGNIZE THE PLUGIN EXTENSION

                try:
                    credential_dict = install_dict.copy()
                    credential_dict.pop('management_ip')
                    credential_dict.pop('fingerprint')

                    found_plugin = await self.middleware.run_in_io_thread(
                        self._find_plugin,
                        credential_dict
                    )
                    if found_plugin:
                        verrors.add(
                            f'{schema_name}.action',
                            'Plugin repair is not required'
                        )
                except ValidationError as e:
                    verrors.add_validation_error(e)
                else:
                    
                    if verrors:
                        raise verrors

                    try:
                        repair_dict = install_dict.copy()
                        repair_dict['install_mode'] = 'REPAIR'
                        await self.middleware.run_in_io_thread(
                            self.__install_vcenter_plugin,
                            repair_dict
                        )
                    except ValidationError as e:
                        verrors.add_validation_error(e)

        elif action == 'UNINSTALL':

            if not new['installed']:
                verrors.add(
                    f'{schema_name}.action',
                    'Plugin is not installed on the system'
                )
            else:

                try:
                    uninstall_dict = install_dict.copy()
                    uninstall_dict.pop('management_ip')
                    uninstall_dict.pop('fingerprint')
                    await self.middleware.run_in_io_thread(
                        self.__uninstall_vcenter_plugin,
                        uninstall_dict
                    )
                except ValidationError as e:
                    verrors.add_validation_error(e)
                else:
                    new['installed'] = False
                    new['port'] = 443
                    for key in new:
                        # flushing existing object with empty values
                        if key not in ('installed', 'id', 'port'):
                            new[key] = ''

        else:

            if not new['installed']:
                verrors.add(
                    f'{schema_name}.action',
                    'Plugin not installed'
                )
            elif not (await self.is_update_available()):
                verrors.add(
                    f'{schema_name}.action',
                    'No update is available for vCenter plugin'
                )
            else:

                try:
                    await self.middleware.run_in_io_thread(
                        self.__upgrade_vcenter_plugin,
                        install_dict
                    )
                except ValidationError as e:
                    verrors.add_validation_error(e)
                else:
                    new['version'] = await self.middleware.run_in_io_thread(self.get_plugin_version)

        if verrors:
            raise verrors

        new['password'] = await self.middleware.call('notifier.pwenc_encrypt', new['password'])

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            new['id'],
            new,
            {'prefix': self._config.datastore_prefix}
        )

        return await self.config()
    
    async def is_update_available(self):
        latest_version = await self.middleware.run_in_io_thread(self.get_plugin_version)
        current_version = (await self.config())['version']
        return latest_version if parse_version(latest_version) > parse_version(current_version) else None

    async def plugin_root_path(self):
        return await self.middleware.call('notifier.gui_static_root')

    @private
    async def get_management_ip_choices(self):
        ip_list = await self.middleware.call(
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
            resource_folder_path = self.middleware.call_sync('vcenter.resource_folder_path')
            for file in os.listdir(resource_folder_path):
                eri = vim.Extension.ResourceInfo()

                # Read locale file from vcp_locale
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
                'vcenter_update.create_event_keyvalue_pairs',
                f'Can not read locales : {e}'
            )

    @private
    def get_extension_key(self):
        cp = configparser.ConfigParser()
        cp.read(self.middleware.call_sync('vcenter.property_file_path'))
        return cp.get('RegisterParam', 'key')

    @accepts(
        Dict(
            'install_vcenter_plugin',
            Int('port', required=True),
            Str('fingerprint', required=True),
            Str('management_ip', required=True),
            Str('install_mode', enum=['NEW', 'REPAIR'], required=False, default='NEW'),
            Str('ip', required=True),  # HOST IP
            Str('password', password=True, required=True),  # Password should be decrypted
            Str('username', required=True),
            register=True
        )
    )
    def __install_vcenter_plugin(self, data):

        encrypted_password = self.middleware.call_sync('notifier.pwenc_encrypt', data['password'])

        update_zipfile_dict = data.copy()
        update_zipfile_dict.pop('management_ip')
        update_zipfile_dict.pop('fingerprint')
        update_zipfile_dict['password'] = encrypted_password
        update_zipfile_dict['plugin_version_old'] = 'null'
        update_zipfile_dict['plugin_version_new'] = self.get_plugin_version()
        self.__update_plugin_zipfile(update_zipfile_dict)

        data.pop('install_mode')

        try:
            ext = self.get_extension(data['management_ip'], data['fingerprint'])

            data.pop('fingerprint')
            data.pop('management_ip')
            si = self.__check_credentials(data)

            si.RetrieveServiceContent().extensionManager.RegisterExtension(ext)

        except vim.fault.NoPermission:
            raise ValidationError(
                'vcenter_update.username',
                'VCenter user has no permission to install the plugin'
            )

    @accepts(
        Patch(
            'install_vcenter_plugin', 'uninstall_vcenter_plugin',
            ('rm', {'name': 'fingerprint'}),
            ('rm', {'name': 'install_mode'}),
            ('rm', {'name': 'management_ip'}),
            register=True
        )
    )
    def __uninstall_vcenter_plugin(self, data):
        try:
            extkey = self.get_extension_key()

            si = self.__check_credentials(data)
            si.RetrieveServiceContent().extensionManager.UnregisterExtension(extkey)

        except vim.fault.NoPermission:
            raise ValidationError(
                'vcenter_update.username',
                'VCenter user does not have necessary permission to uninstall the plugin'
            )

    @accepts(
        Patch(
            'install_vcenter_plugin', 'upgrade_vcenter_plugin',
            ('rm', {'name': 'install_mode'})
        )
    )
    def __upgrade_vcenter_plugin(self, data):

        update_zipfile_dict = data.copy()
        update_zipfile_dict.pop('management_ip')
        update_zipfile_dict.pop('fingerprint')
        update_zipfile_dict['install_mode'] = 'UPGRADE'
        update_zipfile_dict['password'] = self.middleware.call_sync('notifier.pwenc_encrypt', data['password'])
        update_zipfile_dict['plugin_version_old'] = str((self.middleware.call_sync('vcenter.config'))['version'])
        update_zipfile_dict['plugin_version_new'] = self.middleware.call_sync('vcenter.get_plugin_version')
        self.__update_plugin_zipfile(update_zipfile_dict)

        try:
            ext = self.get_extension(data['management_ip'], data['fingerprint'])

            data.pop('fingerprint')
            data.pop('management_ip')
            si = self.__check_credentials(data)

            si.RetrieveServiceContent().extensionManager.UpdateExtension(ext)

        except vim.fault.NoPermission:
            raise ValidationError(
                'vcenter_update.username',
                'VCenter user has no permission to upgrade the plugin'
            )

    @accepts(
        Ref('uninstall_vcenter_plugin')
    )
    def _find_plugin(self, data):
        try:
            si = self.__check_credentials(data)

            extkey = self.get_extension_key()
            ext = si.RetrieveServiceContent().extensionManager.FindExtension(extkey)

            if ext is None:
                return False
            else:
                return f'TrueNAS System : {ext.client[0].url.split("/")[2]}'
        except vim.fault.NoPermission:
            raise ValidationError(
                'vcenter_update.username',
                'VCenter user has no permission to find the plugin on this system'
            )

    @accepts(
        Ref('uninstall_vcenter_plugin')
    )
    def __check_credentials(self, data):
        try:
            si = SmartConnect(
                "https", data['ip'], data['port'],
                data['username'], data['password'], sslContext=get_context_object()
            )

            if si:
                return si

        except (socket.gaierror, TimeoutError):
            raise ValidationError(
                'vcenter_update.ip',
                'Provided vCenter Hostname/IP or port are not valid'
            )
        except vim.fault.InvalidLogin:
            raise ValidationError(
                'vcenter_update.username',
                'Provided vCenter credentials are not valid ( username or password )'
            )
        except vim.fault.NoPermission:
            raise ValidationError(
                'vcenter_update.username',
                'vCenter user does not have permission to perform this operation'
            )
        except Exception as e:

            if 'not a vim server' in str(e).lower():
                # In case an IP is provided for a server which is not a VIM server - then Exception is raised with
                # following text
                # Exception: 10.XX.XX.XX:443 is not a VIM server

                raise ValidationError(
                    'vcenter_update.ip',
                    'Provided Hostname/IP is not a VIM server'
                )

            else:
                raise e

    @private
    def get_extension(self, vcp_url, fingerprint):
        try:
            cp = configparser.ConfigParser()
            cp.read(self.middleware.call_sync('vcenter.property_file_path'))
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
                'vcenter_update.get_extension',
                f'Property Missing : {e}'
            )

    @private
    def extract_zip(self, src_path, dest_path):
        if not os.path.exists(dest_path):
            os.makedirs(dest_path)
        with zipfile.ZipFile(src_path) as zip_f:
            zip_f.extractall(dest_path)

    @private
    def zipdir(self, src_path, dest_path):

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
            Str('install_mode', enum=['NEW', 'REPAIR', 'UPGRADE'], required=True),
            Str('plugin_version_old', required=True),
            Str('plugin_version_new', required=True),
            Str('password', required=True, password=True),  # should be encrypted
            Str('username', required=True),
            register=True
        )
    )
    def __update_plugin_zipfile(self, data):
        file_name = self.middleware.call_sync('vcenter.get_plugin_file_name')
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

        # TODO: GOT A STALE NFS HANDLE ERROR ONCE WHEN TRYING DIFFERENT SCENARIOS WITH THIS METHOD 
        # - UNABLE TO RECREATE IT FOR NOW - DO LOOK INTO WHAT CAUSED THE ISSUE
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


class VCenterAuxService(ConfigService):

    class Config:
        datastore = 'vcp.vcenterauxsettings'
        datastore_prefix = 'vc_'

    @accepts(
        Dict(
            'vcenter_aux_settings_update',
            Bool('enable_https')
        )
    )
    async def do_update(self, data):
        old = await self.config()
        new = old.copy()
        new.update(data)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            new['id'],
            new,
            {'prefix': self._config.datastore_prefix}
        )

        return await self.config()
