import asyncio
from collections import defaultdict
import imp
import os

from mako import exceptions
from middlewared.service import CallError, Service
from middlewared.utils.io import write_if_changed, FileChanges
from middlewared.utils.mako import get_template

DEFAULT_ETC_PERMS = 0o644
DEFAULT_ETC_XID = 0


class FileShouldNotExist(Exception):
    pass


class MakoRenderer(object):

    def __init__(self, service):
        self.service = service

    async def render(self, path, ctx):
        try:
            # Mako is not asyncio friendly so run it within a thread
            def do():
                # Get the template by its relative path
                tmpl = get_template(os.path.relpath(path, os.path.dirname(os.path.dirname(__file__))) + ".mako")

                # Render the template
                return tmpl.render(
                    middleware=self.service.middleware,
                    service=self.service,
                    FileShouldNotExist=FileShouldNotExist,
                    render_ctx=ctx
                )

            return await self.service.middleware.run_in_thread(do)
        except FileShouldNotExist:
            raise
        except Exception:
            self.service.logger.debug('Failed to render mako template: {0}'.format(
                exceptions.text_error_template().render()
            ))
            raise


class PyRenderer(object):

    def __init__(self, service):
        self.service = service

    async def render(self, path, ctx):
        name = os.path.basename(path)
        find = imp.find_module(name, [os.path.dirname(path)])
        mod = imp.load_module(name, *find)
        args = [self.service, self.service.middleware]
        if ctx is not None:
            args.append(ctx)

        if asyncio.iscoroutinefunction(mod.render):
            return await mod.render(*args)
        else:
            return await self.service.middleware.run_in_thread(mod.render, *args)


class EtcService(Service):

    GROUPS = {
        'truenas_nvdimm': [
            {'type': 'py', 'path': 'truenas_nvdimm', 'checkpoint': 'post_init'},
        ],
        'shadow': {
            'ctx': [
                {'method': 'user.query'},
            ],
            'entries': [
                {'type': 'mako', 'path': 'shadow', 'group': 'shadow', 'mode': 0o0640},
            ]
        },
        'user': {
            'ctx': [
                {'method': 'user.query'},
                {'method': 'group.query'},
            ],
            'entries': [
                {'type': 'mako', 'path': 'group'},
                {'type': 'mako', 'path': 'passwd', 'local_path': 'master.passwd'},
                {'type': 'mako', 'path': 'shadow', 'group': 'shadow', 'mode': 0o0640},
                {'type': 'mako', 'path': 'local/sudoers', 'mode': 0o440},
                {'type': 'mako', 'path': 'aliases', 'local_path': 'mail/aliases'},
                {'type': 'py', 'path': 'web_ui_root_login_alert'},
            ]
        },
        'netdata': [
            {'type': 'mako', 'path': 'netdata/netdata.conf', 'checkpoint': 'pool_import'},
            {'type': 'mako', 'path': 'netdata/charts.d/exclude_netdata.conf', 'checkpoint': 'pool_import'},
            {'type': 'mako', 'path': 'netdata/exporting.conf'},
            {'type': 'mako', 'path': 'netdata/python.d/smart_log.conf'},
        ],
        'fstab': [
            {'type': 'mako', 'path': 'fstab'},
            {'type': 'py', 'path': 'fstab_configure', 'checkpoint': 'post_init'}
        ],
        'ipa': [
            {'type': 'py', 'path': 'ipa/default_conf'},
            {'type': 'py', 'path': 'ipa/ca.crt'},
            {'type': 'py', 'path': 'ipa/smb.keytab', 'mode': 0o600}
        ],
        'kerberos': {
            'ctx': [
                {'method': 'activedirectory.config'},
                {'method': 'ldap.config'},
                {'method': 'kerberos.config'},
                {'method': 'kerberos.realm.query'}
            ],
            'entries': [
                {'type': 'py', 'path': 'krb5.conf', 'mode': 0o644},
                {'type': 'py', 'path': 'krb5.keytab', 'mode': 0o600},
            ]
        },
        'cron': [
            {'type': 'mako', 'path': 'cron.d/middlewared', 'checkpoint': 'pool_import'},
        ],
        'grub': [
            {'type': 'py', 'path': 'grub', 'checkpoint': 'post_init'},
        ],
        'fips': [
            {'type': 'py', 'path': 'fips', 'checkpoint': None},
        ],
        'keyboard': [
            {'type': 'mako', 'path': 'default/keyboard'},
            {'type': 'mako', 'path': 'vconsole.conf'},
        ],
        'ldap': [
            {'type': 'mako', 'path': 'local/openldap/ldap.conf'},
            {'type': 'mako', 'path': 'sssd/sssd.conf', 'mode': 0o0600},
        ],
        'dhclient': [
            {'type': 'mako', 'path': 'dhcp/dhclient.conf', 'local_path': 'dhclient.conf'},
        ],
        'nfsd': {
            'ctx': [
                {
                    'method': 'sharing.nfs.query',
                    'args': [
                        [('enabled', '=', True), ('locked', '=', False)],
                        {'extra': {'use_cached_locked_datasets': False}}
                    ],
                },
                {'method': 'nfs.config'},
            ],
            'entries': [
                {'type': 'mako', 'path': 'nfs.conf.d/local.conf'},
                {'type': 'mako', 'path': 'default/rpcbind'},
                {'type': 'mako', 'path': 'idmapd.conf'},
                {'type': 'mako', 'path': 'exports', 'checkpoint': 'interface_sync'},
            ]
        },
        'pam': {
            'ctx': [
                {'method': 'activedirectory.config'},
                {'method': 'ldap.config'},
            ],
            'entries': [
                {'type': 'mako', 'path': 'pam.d/common-account'},
                {'type': 'mako', 'path': 'pam.d/common-auth'},
                {'type': 'mako', 'path': 'pam.d/common-password'},
                {'type': 'mako', 'path': 'pam.d/common-session-noninteractive'},
                {'type': 'mako', 'path': 'pam.d/common-session'},
                {'type': 'mako', 'path': 'security/pam_winbind.conf'},
            ]
        },
        'pam_middleware': [
            {'type': 'mako', 'path': 'pam.d/middleware'},
        ],
        'ftp': [
            {'type': 'mako', 'path': 'proftpd/proftpd.conf',
             'local_path': 'local/proftpd.conf'},
            {'type': 'py', 'path': 'local/proftpd'},
        ],
        'kdump': [
            {'type': 'mako', 'path': 'default/kdump-tools'},
        ],
        'rc': [
            {'type': 'py', 'path': 'systemd'},
        ],
        'sysctl': [
            {'type': 'mako', 'path': 'sysctl.d/tunables.conf'},
        ],
        'smartd': [
            {'type': 'mako', 'path': 'default/smartmontools'},
            {'type': 'py', 'path': 'smartd'},
        ],
        'ssl': [
            {'type': 'py', 'path': 'generate_ssl_certs'},
        ],
        'scst': [
            {'type': 'mako', 'path': 'scst.conf', 'checkpoint': 'pool_import', 'mode': 0o600},
            {'type': 'mako', 'path': 'scst.env', 'checkpoint': 'pool_import', 'mode': 0o744},
        ],
        'scst_targets': [
            {'type': 'mako', 'path': 'initiators.allow', 'checkpoint': 'pool_import'},
            {'type': 'mako', 'path': 'initiators.deny', 'checkpoint': 'pool_import'},
        ],
        'udev': [
            {'type': 'py', 'path': 'udev'},
        ],
        'nginx': [
            {'type': 'mako', 'path': 'local/nginx/nginx.conf', 'checkpoint': 'interface_sync'}
        ],
        'keepalived': [
            {
                'type': 'mako',
                'path': 'keepalived/keepalived.conf',
                'user': 'root', 'group': 'root', 'mode': 0o644,
                'local_path': 'keepalived.conf',
            },

        ],
        'motd': [
            {'type': 'mako', 'path': 'motd'}
        ],
        'mdns': {
            'ctx': [
                {'method': 'interface.query'},
                {'method': 'smb.config'},
                {'method': 'ups.config'},
                {'method': 'system.general.config'},
                {'method': 'service.started_or_enabled', 'args': ['cifs']},
                {'method': 'service.started_or_enabled', 'args': ['ups'], 'ctx_prefix': 'ups'}
            ],
            'entries': [
                {'type': 'mako', 'path': 'local/avahi/avahi-daemon.conf', 'checkpoint': None},
                {'type': 'py', 'path': 'local/avahi/services/ADISK.service', 'checkpoint': None},
                {'type': 'py', 'path': 'local/avahi/services/DEV_INFO.service', 'checkpoint': None},
                {'type': 'py', 'path': 'local/avahi/services/HTTP.service', 'checkpoint': None},
                {'type': 'py', 'path': 'local/avahi/services/SMB.service', 'checkpoint': None},
                {'type': 'py', 'path': 'local/avahi/services/nut.service', 'checkpoint': None},
            ]
        },
        'nscd': [
            {'type': 'mako', 'path': 'nscd.conf'},
        ],
        'nss': [
            {'type': 'mako', 'path': 'nsswitch.conf'},
        ],
        'wsd': [
            {'type': 'mako', 'path': 'local/wsdd.conf', 'checkpoint': 'post_init'},
        ],
        'ups': [
            {'type': 'py', 'path': 'local/nut/ups_config'},
            {'type': 'mako', 'path': 'local/nut/ups.conf', 'owner': 'root', 'group': 'nut', 'mode': 0o440},
            {'type': 'mako', 'path': 'local/nut/upsd.conf', 'owner': 'root', 'group': 'nut', 'mode': 0o440},
            {'type': 'mako', 'path': 'local/nut/upsd.users', 'owner': 'root', 'group': 'nut', 'mode': 0o440},
            {'type': 'mako', 'path': 'local/nut/upsmon.conf', 'owner': 'root', 'group': 'nut', 'mode': 0o440},
            {'type': 'mako', 'path': 'local/nut/upssched.conf', 'owner': 'root', 'group': 'nut', 'mode': 0o440},
            {'type': 'mako', 'path': 'local/nut/nut.conf', 'owner': 'root', 'group': 'nut', 'mode': 0o440},
            {'type': 'py', 'path': 'local/nut/ups_perms'}
        ],
        'smb': {
            'ctx': [
                {'method': 'smb.generate_smb_configuration'},
            ],
            'entries': [
                {'type': 'mako', 'path': 'local/smb4.conf'},
            ]
        },
        'snmpd': [
            {'type': 'mako', 'path': 'snmp/snmpd.conf',
                'local_path': 'local/snmpd.conf', 'owner': 'root', 'group': 'Debian-snmp', 'mode': 0o640
            },
        ],
        'syslogd': {
            'ctx': [
                {'method': 'system.advanced.config'},
                {'method': 'nfs.config'},
            ],
            'entries': [
                {'type': 'mako', 'path': 'syslog-ng/syslog-ng.conf'},
                {'type': 'mako', 'path': 'syslog-ng/conf.d/tndestinations.conf'},
                {'type': 'mako', 'path': 'syslog-ng/conf.d/tnfilters.conf'},
                {'type': 'mako', 'path': 'syslog-ng/conf.d/tnaudit.conf', 'mode': 0o600},
            ]
        },
        'hosts': [{'type': 'mako', 'path': 'hosts', 'mode': 0o644, 'checkpoint': 'pre_interface_sync'}],
        'hostname': [{'type': 'py', 'path': 'hostname', 'checkpoint': 'pre_interface_sync'}],
        'ssh': {
            "ctx": [
                {'method': 'ssh.config'},
                {'method': 'activedirectory.config'},
                {'method': 'ldap.config'},
                {'method': 'auth.twofactor.config'},
                {'method': 'interface.query'},
            ],
            "entries": [
                {'type': 'mako', 'path': 'local/ssh/sshd_config', 'checkpoint': 'interface_sync'},
                {'type': 'mako', 'path': 'pam.d/sshd', 'local_path': 'pam.d/sshd_linux'},
                {'type': 'mako', 'path': 'local/users.oath', 'mode': 0o0600, 'checkpoint': 'pool_import'},
                {'type': 'py', 'path': 'local/ssh/config'},
            ]
        },
        'ntpd': [
            {'type': 'mako', 'path': 'chrony/chrony.conf'}
        ],
        'localtime': [
            {'type': 'py', 'path': 'localtime_config'}
        ],
        'kmip': [
            {'type': 'mako', 'path': 'pykmip/pykmip.conf'}
        ],
        'truecommand': [
            {'type': 'mako', 'path': 'wireguard/ix-truecommand.conf'},
        ],
        'libvirt': [
            {'type': 'py', 'path': 'libvirt', 'checkpoint': None},
        ],
        'libvirt_guests': [
            {'type': 'mako', 'path': 'default/libvirt-guests', 'checkpoint': None},
        ]
    }
    LOCKS = defaultdict(asyncio.Lock)

    checkpoints = ['initial', 'interface_sync', 'post_init', 'pool_import', 'pre_interface_sync']

    class Config:
        private = True

    def __init__(self, *args, **kwargs):
        super(EtcService, self).__init__(*args, **kwargs)
        self.files_dir = os.path.realpath(
            os.path.join(os.path.dirname(__file__), '..', 'etc_files')
        )
        self._renderers = {
            'mako': MakoRenderer(self),
            'py': PyRenderer(self),
        }

    async def gather_ctx(self, methods):
        rv = {}
        for m in methods:
            method = m['method']
            args = m.get('args', [])
            prefix = m.get('ctx_prefix', None)
            key = f'{prefix}.{method}' if prefix else method
            rv[key] = await self.middleware.call(method, *args)

        return rv

    def get_perms_and_ownership(self, entry):
        user_name = entry.get('owner')
        group_name = entry.get('group')
        mode = entry.get('mode', DEFAULT_ETC_PERMS)

        uid = self.middleware.call_sync('user.get_builtin_user_id', user_name) if user_name else DEFAULT_ETC_XID
        gid = self.middleware.call_sync('group.get_builtin_group_id', group_name) if group_name else DEFAULT_ETC_XID

        return {'uid': uid, 'gid': gid, 'perms': mode}

    def make_changes(self, full_path, entry, rendered):
        mode = entry.get('mode', DEFAULT_ETC_PERMS)

        def opener(path, flags):
            return os.open(path, os.O_CREAT | os.O_RDWR, mode=mode)

        outfile_dirname = os.path.dirname(full_path)
        if outfile_dirname != '/etc':
            os.makedirs(outfile_dirname, exist_ok=True)

        payload = self.get_perms_and_ownership(entry)
        try:
            changes = write_if_changed(full_path, rendered, **payload)
        except Exception:
            changes = 0
            self.logger.warning('%s: failed to write changes to configuration file', full_path, exc_info=True)

        if (unexpected_changes := changes & ~FileChanges.CONTENTS):
            self.logger.error(
                '%s: unexpected changes [%s] were made to configuration file that may '
                'allow unauthorized user to alter service behavior', full_path,
                ', '.join(FileChanges.dump(unexpected_changes))
            )

        return changes

    async def generate(self, name, checkpoint=None):
        group = self.GROUPS.get(name)
        if group is None:
            raise ValueError('{0} group not found'.format(name))

        output = []
        async with self.LOCKS[name]:
            if isinstance(group, dict):
                ctx = await self.gather_ctx(group['ctx'])
                entries = group['entries']
            else:
                ctx = None
                entries = group

            for entry in entries:
                renderer = self._renderers.get(entry['type'])
                if renderer is None:
                    raise ValueError(f'Unknown type: {entry["type"]}')

                if checkpoint:
                    entry_checkpoint = entry.get('checkpoint', 'initial')
                    if entry_checkpoint != checkpoint:
                        continue

                path = os.path.join(self.files_dir, entry.get('local_path') or entry['path'])
                entry_path = entry['path']
                if entry_path.startswith('local/'):
                    entry_path = entry_path[len('local/'):]
                outfile = f'/etc/{entry_path}'

                try:
                    rendered = await renderer.render(path, ctx)
                except FileShouldNotExist:
                    try:
                        await self.middleware.run_in_thread(os.unlink, outfile)
                        self.logger.debug(f'{entry["type"]}:{entry["path"]} file removed.')
                        output.append({
                            'path': outfile,
                            'status': 'REMOVED',
                            'changes': FileChanges.dump(FileChanges.CONTENTS)
                        })
                    except FileNotFoundError:
                        # Nothing to log
                        pass

                    continue
                except Exception:
                    self.logger.error(f'Failed to render {entry["type"]}:{entry["path"]}', exc_info=True)
                    continue

                if rendered is None:
                    # TODO: scripts that write config files internally should be refacorted
                    # to return bytes or str so that we can properly monitor for changes
                    continue

                changes = await self.middleware.run_in_thread(self.make_changes, outfile, entry, rendered)

                if not changes:
                    self.logger.trace('No new changes for %s', outfile)

                else:
                    output.append({
                        'path': outfile,
                        'status': 'CHANGED',
                        'changes': FileChanges.dump(changes)
                    })

        return output

    async def generate_checkpoint(self, checkpoint):
        if checkpoint not in await self.get_checkpoints():
            raise CallError(f'"{checkpoint}" not recognised')

        for name in self.GROUPS.keys():
            try:
                await self.generate(name, checkpoint)
            except Exception:
                self.logger.error(f'Failed to generate {name} group', exc_info=True)

    async def get_checkpoints(self):
        return self.checkpoints


async def __event_system_ready(middleware, event_type, args):
    middleware.create_task(middleware.call('etc.generate_checkpoint', 'post_init'))


async def pool_post_import(middleware, pool):
    if pool is None:
        await middleware.call('etc.generate_checkpoint', 'pool_import')


async def setup(middleware):
    middleware.event_subscribe('system.ready', __event_system_ready)
    # Generate `etc` files before executing other post-boot-time-pool-import actions.
    # There are no explicit requirements for that, we are just preserving execution order
    # when moving checkpoint generation to pool.post_import hook.
    middleware.register_hook('pool.post_import', pool_post_import, order=-1000)
