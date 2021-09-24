from middlewared.service import private, Service
from middlewared.service_exception import CallError
from middlewared.plugins.smb_.smbconf.reg_global_smb import GlobalSchema
from middlewared.plugins.activedirectory import AD_SMBCONF_PARAMS
from middlewared.plugins.ldap import LDAP_SMBCONF_PARAMS

import errno

DEFAULT_GLOBAL_PARAMETERS = {
    "dns proxy": {"smbconf": "dns proxy", "default": False},
    "max log size": {"smbconf": "max log size", "default": 51200},
    "load printers": {"smbconf": "load printers", "default": False},
    "printing": {"smbconf": "printing", "default": "bsd"},
    "printcap": {"smbconf": "printcap", "default": "/dev/null"},
    "disable spoolss": {"smbconf": "disable spoolss", "default": True},
    "dos filemode": {"smbconf": "dos filemode", "default": True},
    "kernel change notify": {"smbconf": "kernel change notify", "default": True},
    "enable web service discovery": {"smbconf": "enable web service discovery", "default": True},
    "bind interfaces only": {"smbconf": "bind interfaces only", "default": True},
    "registry": {"smbconf": "registry", "default": True},
    "registry shares": {"smbconf": "registry shares", "default": True},
}


class SMBService(Service):

    class Config:
        service = 'cifs'
        service_verb = 'restart'

    @private
    async def strip_idmap(self, reg_defaults):
        """
        All params related to idmap backends will be handled
        in idmap plugin.
        """
        idmap_params = {}
        for k, v in reg_defaults.items():
            if k.startswith("idmap config"):
                idmap_params[k] = v

        for e in idmap_params.keys():
            reg_defaults.pop(e, "")

        return idmap_params

    @private
    async def strip_directory_services(self, reg_defaults):
        def_ds_params = []
        def_ds_params.extend(AD_SMBCONF_PARAMS.keys())
        def_ds_params.extend(LDAP_SMBCONF_PARAMS.keys())
        ds_params = {}

        for k, v in reg_defaults.items():
            if k in def_ds_params:
                ds_params[k] = v

        for e in ds_params.keys():
            reg_defaults.pop(e, "")

        return ds_params

    @private
    async def reg_globals(self):
        """
        Split smb.conf parameters into portions used by relevant plugins.

        `raw` contains unmodified smb.conf
        `idmap` contains idmap configuration
        `ds` contains directory service configuration
        `smb` contains smb service configuation (smb plugin)
        """
        ret = {}
        """
        reg_showshare will fail for `global` if registry has no global entries.
        In this case simply return an empty config (since it's actually empty anyway).
        """
        try:
            global_conf = await self.middleware.call('sharing.smb.reg_showshare', 'global')
        except CallError as e:
            if e.errno == errno.ENXIO:
                self.logger.warning("Unable to query globals due to unhealthy ctdb state")
            return {'raw': {}, 'idmap': {}, 'ds': {}, 'smb': {}}
        except Exception:
            self.logger.debug("Failed to retrieve global share config from registry")
            return {'raw': {}, 'idmap': {}, 'ds': {}, 'smb': {}}

        ret['raw'] = global_conf['parameters'].copy()
        ret['idmap'] = await self.strip_idmap(global_conf['parameters'])
        ret['ds'] = await self.strip_directory_services(global_conf['parameters'])
        ret['smb'] = global_conf['parameters']
        return ret

    @private
    async def reg_update(self, data):
        diff = await self.diff_conf_and_registry(data, True)
        await self.middleware.call('sharing.smb.apply_conf_diff', 'GLOBAL', diff)

    @private
    async def get_ds_role(self, params):
        params['ad'] = await self.middleware.call("activedirectory.config")
        params['ldap'] = await self.middleware.call("ldap.config")
        if params['ad']['enable']:
            params['role'] = 'ad_member'
        elif params['ldap']['enable'] and params['ldap']['has_samba_schema']:
            params['role'] = 'ldap_member'

    @private
    async def diff_conf_and_registry(self, data, full_check):
        """
        return differences between running configuration and a dict of smb.conf parameters.
        When full_check is True, then we diff the full running configuration.
        """
        new_conf = await self.global_to_smbconf(data)
        running_conf = (await self.middleware.call('smb.reg_globals'))['smb']

        s_keys = set(new_conf.keys())
        r_keys = set(running_conf.keys())
        intersect = s_keys.intersection(r_keys)
        return {
            'added': {x: new_conf[x] for x in s_keys - r_keys},
            'removed': {x: running_conf[x] for x in r_keys - s_keys} if full_check else {},
            'modified': {x: new_conf[x]for x in intersect if new_conf[x] != running_conf[x]},
        }

    @private
    async def global_to_smbconf(self, data):
        """
        Convert the SMB share config into smb.conf parameters prior to
        registry insertion. Optimization in this case to _only_ set bare minimum
        parameters to reflect the specified smb service configuration.
        """
        to_set = {}
        data['ds_state'] = await self.middleware.call('directoryservices.get_state')
        data['shares'] = await self.middleware.call(
            'sharing.smb.query',
            [('enabled', '=', True), ('locked', '=', False)]
        )
        data['ms_accounts'] = await self.middleware.call(
            'user.query',
            [('microsoft_account', '=', True), ('locked', '=', False)],
            {'count': True}
        )
        gs = GlobalSchema()
        gs.convert_schema_to_registry(data, to_set)

        for i in data.get('smb_options', '').splitlines():
            kv = i.split("=", 1)
            if len(kv) != 2:
                continue
            to_set.update({kv[0]: {"parsed": kv[1], "raw": kv[1]}})

        return to_set

    @private
    async def initialize_globals(self):
        data = await self.middleware.call('smb.config')
        await self.reg_update(data)
