from middlewared.service import private, Service
from middlewared.service_exception import CallError
from middlewared.plugins.smb_.smbconf.reg_service import ShareSchema
from .utils import smb_strip_comments
from .util_net_conf import (
        reg_setparm,
        reg_delparm,
        reg_addshare,
        reg_listshares,
        reg_showshare,
)

import os

CONF_JSON_VERSION = {"major": 0, "minor": 1}


class SharingSMBService(Service):

    class Config:
        namespace = 'sharing.smb'

    @private
    def reg_addshare(self, data):
        """
        wrapper around net_conf method
        """
        conf = self.share_to_smbconf(data)
        name = 'homes' if data['home'] else data['name']

        reg_addshare(name, conf)

    @private
    def reg_listshares(self):
        """
        Wrapper primarily used by CI to validate list of shares
        """
        return reg_listshares()

    @private
    def get_global_params(self, globalconf):
        if globalconf is None:
            globalconf = {}

        gl = {
            'fruit_enabled': globalconf.get('fruit_enabled', None),
            'ad_enabled': globalconf.get('ad_enabled', None),
            'nfs_exports': globalconf.get('nfs_exports', None),
            'smb_shares': globalconf.get('smb_shares', None)
        }
        if gl['nfs_exports'] is None:
            gl['nfs_exports'] = self.middleware.call_sync('sharing.nfs.query', [['enabled', '=', True]])
        if gl['smb_shares'] is None:
            gl['smb_shares'] = self.middleware.call_sync('sharing.smb.query', [['enabled', '=', True]])
            for share in gl['smb_shares']:
                share['auxsmbconf'] = smb_strip_comments(share['auxsmbconf'])

        if gl['ad_enabled'] is None:
            gl['ad_enabled'] = self.middleware.call_sync('activedirectory.config')['enable']

        if gl['fruit_enabled'] is None:
            smbconf = self.middleware.call_sync('smb.config')
            gl['fruit_enabled'] = smbconf['aapl_extensions']

        return gl

    @private
    def diff_middleware_and_registry(self, share, data):
        if share is None:
            raise CallError('Share name must be specified.')

        if data is None:
            data = self.middleware.call_sync('sharing.smb.query', [('name', '=', share)], {'get': True})

        data['auxsmbconf'] = smb_strip_comments(data['auxsmbconf'])
        share_conf = self.share_to_smbconf(data)
        try:
            reg_conf = reg_showshare(share if not data['home'] else 'homes')['parameters']
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
    def apply_conf_diff(self, share, diff):
        set_payload = {"service": share, "parameters": diff["added"] | diff["modified"]}
        del_payload = {"service": share, "parameters": diff["removed"]}

        if set_payload["parameters"]:
            reg_setparm(set_payload)

        if del_payload["parameters"]:
            reg_delparm(del_payload)

        return

    @private
    def create_domain_paths(self, path):
        if not path:
            return

        for dom in self.middleware.call_sync('smb.domain_choices'):
            if dom == 'BUILTIN':
                continue

            try:
                os.mkdir(os.path.join(path, dom))
            except FileExistsError:
                pass

    @private
    def share_to_smbconf(self, conf_in, globalconf=None):
        data = conf_in.copy()
        gl = self.get_global_params(globalconf)
        data['auxsmbconf'] = smb_strip_comments(data['auxsmbconf'])
        conf = {}

        if not data['path_suffix'] and data['home']:
            """
            Homes shares must have some macro expansion (to avoid giving users same
            homedir) unless path is omitted for share.

            Omitting path is special configuration that shares out every user's
            home directory (regardless of path).
            """
            if gl['ad_enabled']:
                data['path_suffix'] = '%D/%U'
                self.create_domain_paths(conf_in['path'])
            elif data['path']:
                data['path_suffix'] = '%U'

        ss = ShareSchema(self.middleware)
        ss.convert_schema_to_registry(data, conf)

        return conf
