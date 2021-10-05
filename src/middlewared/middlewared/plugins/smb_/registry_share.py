from middlewared.service import private, Service, filterable
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.utils import run, filter_list
from middlewared.plugins.smb import SMBCmd, SMBHAMODE
from middlewared.plugins.smb_.smbconf.reg_service import ShareSchema

import errno
import json

CONF_JSON_VERSION = {"major": 0, "minor": 1}


class SharingSMBService(Service):

    class Config:
        namespace = 'sharing.smb'

    @private
    async def json_check_version(self, version):
        if version == CONF_JSON_VERSION:
            return

        raise CallError(
            "Unexpected JSON version returned from Samba utils: "
            f"[{version}]. Expected version was: [{CONF_JSON_VERSION}]. "
            "Behavior is undefined with a version mismatch and so refusing "
            "to perform groupmap operation. Please file a bug report at "
            "jira.ixsystems.com with this traceback."
        )

    @private
    async def netconf(self, **kwargs):
        """
        wrapper for net(8) conf. This manages the share configuration, which is stored in
        samba's registry.tdb file.
        """
        action = kwargs.get('action')
        if action not in [
            'list',
            'showshare',
            'addshare',
            'delshare',
            'getparm',
            'setparm',
            'delparm'
        ]:
            raise CallError(f'Action [{action}] is not permitted.', errno.EPERM)

        ha_mode = SMBHAMODE[(await self.middleware.call('smb.get_smb_ha_mode'))]
        if ha_mode == SMBHAMODE.CLUSTERED:
            ctdb_healthy = await self.middleware.call('ctdb.general.healthy')
            if not ctdb_healthy:
                raise CallError(
                    "Registry calls not permitted when ctdb unhealthy.", errno.ENXIO
                )

        share = kwargs.get('share')
        args = kwargs.get('args', [])
        jsoncmd = kwargs.get('jsoncmd', False)
        if jsoncmd:
            cmd = [SMBCmd.NET.value, '--json', 'conf', action]
        else:
            cmd = [SMBCmd.NET.value, 'conf', action]

        if share:
            cmd.append(share)

        if args:
            cmd.extend(args)

        netconf = await run(cmd, check=False)
        if netconf.returncode != 0:
            # net_conf needs to be reworked to return errors consistently.
            if action != 'getparm':
                self.logger.trace('netconf failure for command [%s]: %s',
                                  cmd, netconf.stderr.decode())

            errmsg = netconf.stderr.decode().strip()
            if 'SBC_ERR_NO_SUCH_SERVICE' in errmsg or 'does not exist' in errmsg:
                svc = share if share else json.loads(args[0])['service']
                raise MatchNotFound(svc)

            raise CallError(
                f'net conf {action} [{cmd}] failed with error: {errmsg}'
            )

        if jsoncmd:
            out = netconf.stdout.decode()
            if out:
                out = json.loads(out)
        else:
            out = netconf.stdout.decode()

        return out

    @private
    async def reg_listshares(self):
        out = []
        res = await self.netconf(action='list', jsoncmd=True)
        version = res.pop('version')
        await self.json_check_version(version)

        for s in res['sections']:
            if s['is_share']:
                out.append(s['service'])

        return out

    @private
    async def reg_list(self):
        res = await self.netconf(action='list', jsoncmd=True)
        version = res.pop('version')
        await self.json_check_version(version)

        return res

    @private
    async def reg_addshare(self, data):
        conf = await self.middleware.call("sharing.smb.share_to_smbconf", data)
        name = 'homes' if data['home'] else data['name']

        payload = {
            "service": name,
            "parameters": conf,
        }
        await self.netconf(
            action='addshare',
            jsoncmd=True,
            args=[json.dumps(payload)]
        )

    @private
    async def reg_delshare(self, share):
        return await self.netconf(action='delshare', share=share)

    @private
    async def reg_showshare(self, share):
        net = await self.netconf(action='showshare', share=share, jsoncmd=True)
        version = net.pop('version')
        await self.json_check_version(version)

        to_list = ['vfs objects', 'hosts allow', 'hosts deny']
        parameters = net.get('parameters', {})

        for p in to_list:
            if parameters.get(p):
                parameters[p]['parsed'] = parameters[p]['raw'].split()

        return net

    @private
    async def reg_setparm(self, data):
        return await self.netconf(action='setparm', args=[json.dumps(data)], jsoncmd=True)

    @private
    async def reg_delparm(self, data):
        return await self.netconf(action='delparm', args=[json.dumps(data)], jsoncmd=True)

    @private
    async def reg_getparm(self, share, parm):
        to_list = ['vfs objects', 'hosts allow', 'hosts deny']
        try:
            ret = (await self.netconf(action='getparm', share=share, args=[parm])).strip()
        except CallError as e:
            if f"Error: given parameter '{parm}' is not set." in e.errmsg:
                # Copy behavior of samba python binding
                return None
            else:
                raise

        return ret.split() if parm in to_list else ret

    @private
    async def get_global_params(self, globalconf):
        if globalconf is None:
            globalconf = {}

        gl = {}
        gl.update({
            'fruit_enabled': globalconf.get('fruit_enabled', None),
            'ad_enabled': globalconf.get('ad_enabled', None),
            'nfs_exports': globalconf.get('nfs_exports', None),
            'smb_shares': globalconf.get('smb_shares', None)
        })
        if gl['nfs_exports'] is None:
            gl['nfs_exports'] = await self.middleware.call('sharing.nfs.query', [['enabled', '=', True]])
        if gl['smb_shares'] is None:
            gl['smb_shares'] = await self.middleware.call('sharing.smb.query', [['enabled', '=', True]])
            for share in gl['smb_shares']:
                await self.middleware.call('sharing.smb.strip_comments', share)

        if gl['ad_enabled'] is None:
            gl['ad_enabled'] = (await self.middleware.call('activedirectory.config'))['enable']

        if gl['fruit_enabled'] is None:
            smbconf = await self.middleware.call('smb.config')
            gl['fruit_enabled'] = smbconf['aapl_extensions']

        return gl

    @private
    async def diff_middleware_and_registry(self, share, data):
        if share is None:
            raise CallError('Share name must be specified.')

        if data is None:
            data = await self.middleware.call('sharing.smb.query', [('name', '=', share)], {'get': True})

        await self.middleware.call('sharing.smb.strip_comments', data)
        share_conf = await self.middleware.call("sharing.smb.share_to_smbconf", data)
        try:
            reg_conf = (await self.reg_showshare(share if not data['home'] else 'homes'))['parameters']
        except Exception:
            return None

        s_keys = set(share_conf.keys())
        r_keys = set(reg_conf.keys())
        intersect = s_keys.intersection(r_keys)

        return {
            'added': {x: share_conf[x] for x in s_keys - r_keys},
            'removed': {x: reg_conf[x] for x in r_keys - s_keys},
            'modified': {x: share_conf[x] for x in intersect if share_conf[x] != reg_conf[x]},
        }

    @private
    async def apply_conf_diff(self, share, diff):
        set_payload = {"service": share, "parameters": diff["added"] | diff["modified"]}
        del_payload = {"service": share, "parameters": diff["removed"]}

        if set_payload["parameters"]:
            await self.reg_setparm(set_payload)

        if del_payload["parameters"]:
            await self.reg_delparm(del_payload)

        return

    @private
    @filterable
    def reg_query(self, filters, options):
        """
        Filterable method for querying SMB shares from the registry
        config. Can be reverted back to registry / smb.conf without
        loss of information. This is necessary to provide consistent
        API for viewing samba's current running configuration, which
        is of particular importance with clustered registry shares.
        """
        try:
            reg_shares = self.middleware.call_sync('sharing.smb.reg_list')
        except CallError:
            return []

        rv = []
        for idx, s in enumerate(reg_shares['sections']):
            if not s['is_share']:
                continue

            is_home = s['service'] == "HOMES"
            s["parameters"]["name"] = "HOMES_SHARE" if is_home else s['service']
            s["parameters"]["home"] = is_home
            parsed_conf = self.smbconf_to_share(s['parameters'])

            entry = {"id": idx + 1}
            entry.update(parsed_conf)
            rv.append(entry)

        return filter_list(rv, filters, options)

    @private
    def smbconf_to_share(self, data):
        """
        Wrapper to convert registry share into approximation of
        normal API return for sharing.smb.query.
        Disabled and locked shares are not in samba's running
        configuration in registry.tdb and so we assume that this
        is not the case.
        """
        ret = {}
        conf_in = data.copy()
        # TO_DO - need to validate whether VFS objects have been manually overridden by
        # auxiliary parameters or CLI changes (e.g. "net conf setparm").
        try:
            conf_in['vfs objects']["parsed"] = data["vfs objects"]["parsed"].split()
        except KeyError:
            conf_in["vfs objects"] = {"raw": "", "parsed": []}

        ss = ShareSchema(self.middleware)
        ss.convert_registry_to_schema(conf_in, ret)
        conf_in.pop("vfs objects", [])
        ret.update({
            "home": conf_in.pop("home", False),
            "name": conf_in.pop("name"),
        })

        return ret

    @private
    def share_to_smbconf(self, conf_in, globalconf=None):
        data = conf_in.copy()
        gl = self.middleware.call_sync('sharing.smb.get_global_params', globalconf)
        self.middleware.call_sync('sharing.smb.strip_comments', data)
        conf = {}

        if data['home'] and gl['ad_enabled']:
            data['path_suffix'] = '%D/%U'
        elif data['home'] and data['path']:
            data['path_suffix'] = '%U'

        ss = ShareSchema(self.middleware)
        ss.convert_schema_to_registry(data, conf)

        return conf
