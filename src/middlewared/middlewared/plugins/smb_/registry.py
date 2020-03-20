from middlewared.service import private, Service
from middlewared.service_exception import CallError
from middlewared.utils import run
from middlewared.plugins.smb import SMBCmd, SMBSharePreset

import errno


class SharingSMBService(Service):

    class Config:
        namespace = 'sharing.smb'

    @private
    async def netconf(self, **kwargs):
        """
        wrapper for net(8) conf. This manages the share configuration, which is stored in
        samba's registry.tdb file.
        """
        action = kwargs.get('action')
        if action not in [
            'listshares',
            'showshare',
            'addshare',
            'delshare',
            'getparm',
            'setparm',
            'delparm'
        ]:
            raise CallError(f'Action [{action}] is not permitted.', errno.EPERM)

        share = kwargs.get('share')
        args = kwargs.get('args', [])
        cmd = [SMBCmd.NET.value, 'conf', action]

        if share:
            cmd.append(share)

        if args:
            cmd.extend(args)

        netconf = await run(cmd, check=False)
        if netconf.returncode != 0:
            self.logger.debug('netconf failure stdout: %s', netconf.stdout.decode())
            raise CallError(
                f'net conf {action} failed with error: {netconf.stderr.decode()}'
            )

        return netconf.stdout.decode()

    @private
    async def reg_listshares(self):
        return (await self.netconf(action='listshares')).splitlines()

    @private
    async def reg_addshare(self, data):
        conf = await self.share_to_smbconf(data)
        path = conf.pop('path')
        name = 'homes' if data['home'] else data['name']
        await self.netconf(
            action='addshare',
            share=name,
            args=[path, f'writeable={"N" if data["ro"] else "y"}',
                  f'guest_ok={"y" if data["guestok"] else "N"}']
        )
        for k, v in conf.items():
            await self.reg_setparm(name, k, v)

    @private
    async def reg_delshare(self, share):
        return await self.netconf(action='delshare', share=share)

    @private
    async def reg_showshare(self, share):
        ret = {}
        to_list = ['vfs objects', 'hosts allow', 'hosts deny']
        net = await self.netconf(action='showshare', share=share)
        for param in net.splitlines()[1:]:
            kv = param.strip().split('=', 1)
            k = kv[0].strip()
            v = kv[1].strip()
            ret[k] = v if k not in to_list else v.split()

        return ret

    @private
    async def reg_setparm(self, share, parm, value):
        if type(value) == list:
            value = ' '.join(value)
        return await self.netconf(action='setparm', share=share, args=[parm, value])

    @private
    async def reg_delparm(self, share, parm):
        return await self.netconf(action='delparm', share=share, args=[parm])

    @private
    async def reg_getparm(self, share, parm):
        to_list = ['vfs objects', 'hosts allow', 'hosts deny']
        try:
            ret = await self.netconf(action='getparm', share=share, args=[parm])
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
            'afp_shares': globalconf.get('afp_shares', None),
            'nfs_exports': globalconf.get('nfs_exports', None),
            'smb_shares': globalconf.get('smb_shares', None)
        })
        if gl['afp_shares'] is None:
            gl['afp_shares'] = await self.middleware.call('sharing.afp.query', [['enabled', '=', True]])
        if gl['nfs_exports'] is None:
            gl['nfs_exports'] = await self.middleware.call('sharing.nfs.query', [['enabled', '=', True]])
        if gl['smb_shares'] is None:
            gl['smb_shares'] = await self.middleware.call('sharing.smb.query', [['enabled', '=', True]])
        if gl['ad_enabled'] is None:
            gl['ad_enabled'] = False if (await self.middleware.call('activedirectory.get_state')) == "DISABLED" else True

        if gl['fruit_enabled'] is None:
            gl['fruit_enabled'] = (await self.middleware.call('smb.config'))['aapl_extensions']

        return gl

    @private
    async def order_vfs_objects(self, vfs_objects):
        vfs_objects_special = ('catia', 'zfs_space', 'fruit', 'streams_xattr', 'shadow_copy_zfs',
                               'noacl', 'ixnas', 'zfsacl', 'crossrename', 'recycle')

        vfs_objects_ordered = []

        if 'fruit' in vfs_objects:
            if 'streams_xattr' not in vfs_objects:
                vfs_objects.append('streams_xattr')

        if 'noacl' in vfs_objects:
            if 'ixnas' in vfs_objects:
                vfs_objects.remove('ixnas')

        for obj in vfs_objects:
            if obj not in vfs_objects_special:
                vfs_objects_ordered.append(obj)

        for obj in vfs_objects_special:
            if obj in vfs_objects:
                vfs_objects_ordered.append(obj)

        return vfs_objects_ordered

    @private
    async def diff_middleware_and_registry(self, share, data):
        if share is None:
            raise CallError('Share name must be specified.')

        if data is None:
            data = await self.middleware.call('sharing.smb.query', [('name', '=', share)], {'get': True})

        share_conf = await self.share_to_smbconf(data)
        reg_conf = await self.reg_showshare(share)
        s_keys = set(share_conf.keys())
        r_keys = set(reg_conf.keys())
        intersect = s_keys.intersection(r_keys)
        return {
            'added': {x: share_conf[x] for x in s_keys - r_keys},
            'removed': {x: reg_conf[x] for x in r_keys - s_keys},
            'modified': {x: (share_conf[x], reg_conf[x]) for x in intersect if share_conf[x] != reg_conf[x]},
        }

    @private
    async def apply_conf_registry(self, share, diff):
        for k, v in diff['added'].items():
            await self.reg_setparm(share, k, v)

        for k, v in diff['removed'].items():
            await self.reg_delparm(share, k)

        for k, v in diff['modified'].items():
            await self.reg_setparm(share, k, v[0])

    @private
    async def apply_conf_diff(self, target, share, confdiff):
        self.logger.trace('target: [%s], share: [%s], diff: [%s]',
                          target, share, confdiff)
        if target not in ['REGISTRY', 'FNCONF']:
            raise CallError(f'Invalid target: [{target}]', errno.EINVAL)

        if target == 'FNCONF':
            # TODO: add ability to convert the registry back to our sqlite table
            raise CallError('FNCONF target not implemented')

        return await self.apply_conf_registry(share, confdiff)

    @private
    async def share_to_smbconf(self, conf_in, globalconf=None):
        data = conf_in.copy()
        gl = await self.get_global_params(globalconf)
        conf = {}

        if data['home'] and gl['ad_enabled']:
            data['path_suffix'] = '%d/%U'
        elif data['home']:
            data['path_suffix'] = '%U'

        conf['path'] = '/'.join([data['path'], data['path_suffix']]) if data['path_suffix'] else data['path']
        data['vfsobjects'] = ['aio_fbsd']
        if data['comment']:
            conf["comment"] = data['comment']
        if not data['browsable']:
            conf["browseable"] = "no"
        if data['abe']:
            conf["access based share enum"] = "yes"
        if data['hostsallow']:
            conf["hosts allow"] = data['hostsallow']
        if data['hostsdeny']:
            conf["hosts deny"] = data['hostsdeny']
        conf["read only"] = "yes" if data['ro'] else "no"
        conf["guest ok"] = "yes" if data['guestok'] else "no"

        nfs_path_list = []
        for export in gl['nfs_exports']:
            nfs_path_list.extend(export['paths'])

        if any(filter(lambda x: f"{conf['path']}/" in f"{x}/", nfs_path_list)):
            self.logger.debug("SMB share [%s] is also an NFS export. "
                              "Applying parameters for mixed-protocol share.", data['name'])
            conf.update({
                "strict locking": "yes",
                "level2 oplocks": "no",
                "oplocks": "no"
            })
            if data['durablehandle']:
                self.logger.warn("Disabling durable handle support on SMB share [%s] "
                                 "due to NFS export of same path.", data['name'])
                await self.middleware.call('datastore.update', 'sharing.cifs_share',
                                           data['id'], {'cifs_durablehandle': False})
                data['durablehandle'] = False

        if gl['fruit_enabled']:
            data['vfsobjects'].append('fruit')

        if data['acl']:
            data['vfsobjects'].append('ixnas')
        else:
            data['vfsobjects'].append('noacl')

        if data['recyclebin']:
            # crossrename is required for 'recycle' to work across sub-datasets
            # FIXME: crossrename imposes 20MB limit on filesize moves across mountpoints
            # This really needs to be addressed with a zfs-aware recycle bin.
            data['vfsobjects'].extend(['recycle', 'crossrename'])

        if data['shadowcopy'] or data['fsrvp']:
            data['vfsobjects'].append('shadow_copy_zfs')

        if data['durablehandle']:
            conf.update({
                "kernel oplocks": "no",
                "kernel share modes": "no",
                "posix locking": "no",
            })

        if data['fsrvp']:
            data['vfsobjects'].append('zfs_fsrvp')
            conf.update({
                "shadow:ignore_empty_snaps": "false",
                "shadow:include": "fss-*",
            })

        conf.update({
            "nfs4:chown": "true",
            "ea support": "false",
        })

        if data['aapl_name_mangling']:
            data['vfsobjects'].append('catia')
            conf.update({
                'fruit:encoding': 'native',
                'mangled names': 'no'
            })

        if data['timemachine']:
            conf["fruit:time machine"] = "yes"

        if data['purpose'] == 'ENHANCED_TIMEMACHINE':
            data['vfsobjects'].append('tmprotect')
        elif data['purpose'] == 'WORM_DROPBOX':
            data['vfsobjects'].append('worm')

        conf["vfs objects"] = await self.order_vfs_objects(data['vfsobjects'])

        if gl['fruit_enabled']:
            conf["fruit:metadata"] = "stream"
            conf["fruit:resource"] = "stream"

        if any(filter(lambda x: f"{x['path']}/" in f"{conf['path']}/" or f"{conf['path']}/" in f"{x['path']}/", gl['afp_shares'])):
            self.logger.debug("SMB share [%s] is also an AFP share. "
                              "Applying parameters for mixed-protocol share.", data['name'])
            conf.update({
                "fruit:locking": "netatalk",
                "fruit:metadata": "netatalk",
                "fruit:resource": "file",
                "strict locking": "auto",
                "streams_xattr:prefix": "user.",
                "streams_xattr:store_stream_type": "no"
            })

        nfs_path_list = []

        if data['recyclebin']:
            conf.update({
                "recycle:repository": ".recycle/%D/%U" if gl['ad_enabled'] else ".recycle/%U",
                "recycle:keeptree": "yes",
                "recycle:keepversions": "yes",
                "recycle:touch": "yes",
                "recycle:directory_mode": "0777",
                "recycle:subdir_mode": "0700"
            })

        if not data['auxsmbconf']:
            data['auxsmbconf'] = (SMBSharePreset[data["purpose"]].value)["params"]["auxsmbconf"]

        for param in data['auxsmbconf'].splitlines():
            if not param.strip():
                continue
            try:
                kv = param.split('=', 1)
                conf[kv[0].strip()] = kv[1].strip()
            except Exception:
                self.logger.debug("[%s] contains invalid auxiliary parameter: [%s]",
                                  data['name'], param)

        return conf
