import configparser
import os
import shutil
import zipfile


from contextlib import closing

from middlewared.schema import Bool, Dict, Int, Patch, Str
from middlewared.service import accepts, ConfigService, private, ValidationErrors
from middlewared.validators import IpAddress

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
    def __update_plugin_zipfile(self, data):
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
            config.set('installation_parameter', 'port', data['port'])
            config.set('installation_parameter', 'password', data['enc_key'])
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
