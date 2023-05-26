import asyncio
from collections import defaultdict
import imp
import os
import stat

from mako import exceptions
from middlewared.service import CallError, Service
from middlewared.utils import osc
from middlewared.utils.io import write_if_changed
from middlewared.utils.mako import get_template

DEFAULT_ETC_PERMS = 0o644


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
                    IS_FREEBSD=osc.IS_FREEBSD,
                    IS_LINUX=osc.IS_LINUX,
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
        'user': {
            'ctx': [
                {'method': 'user.query'},
                {'method': 'group.query'},
            ],
            'entries': [
                {'type': 'mako', 'path': 'group'},
                {'type': 'mako', 'path': 'passwd', 'local_path': 'master.passwd'},
                {'type': 'mako', 'path': 'shadow', 'group': 'shadow', 'mode': 0o0640},
                {'type': 'mako', 'path': 'local/sudoers'},
                {'type': 'mako', 'path': 'aliases', 'local_path': 'mail/aliases'},
                {'type': 'py', 'path': 'web_ui_root_login_alert'},
            ]
        },
        'fstab': [
            {'type': 'mako', 'path': 'fstab'},
            {'type': 'py', 'path': 'fstab_configure', 'checkpoint_linux': 'post_init'}
        ],
        'kerberos': [
            {'type': 'mako', 'path': 'krb5.conf'},
            {'type': 'py', 'path': 'krb5.keytab'},
        ],
        'cron': [
            {'type': 'mako', 'path': 'cron.d/middlewared', 'checkpoint': 'pool_import'},
        ],
        'grub': [
            {'type': 'py', 'path': 'grub', 'checkpoint': 'post_init'},
        ],
        'keyboard': [
            {'type': 'mako', 'path': 'default/keyboard'},
            {'type': 'mako', 'path': 'vconsole.conf'},
        ],
        'ldap': [
            {'type': 'mako', 'path': 'local/openldap/ldap.conf'},
            {'type': 'mako', 'path': 'local/nslcd.conf', 'owner': 'nslcd', 'group': 'nslcd', 'mode': 0o0400},
        ],
        'dhclient': [
            {'type': 'mako', 'path': 'dhcp/dhclient.conf', 'local_path': 'dhclient.conf'},
        ],
        'nfsd': {
            'ctx': [
                {'method': 'sharing.nfs.query', 'args': [[("enabled", "=", True), ("locked", "=", False)]]},
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
            {'type': 'mako', 'path': 'scst.conf', 'checkpoint': 'pool_import'},
            {'type': 'mako', 'path': 'scst.env', 'checkpoint': 'pool_import', 'mode': 0o744},
        ],
        'scst_targets': [
            {'type': 'mako', 'path': 'initiators.allow', 'checkpoint': 'pool_import'},
            {'type': 'mako', 'path': 'initiators.deny', 'checkpoint': 'pool_import'},
        ],
        'udev': [
            {'type': 'py', 'path': 'udev'},
        ],
        'webdav': {
            'ctx': [
                {'method': 'sharing.webdav.query', 'args': [[('enabled', '=', True)]]},
                {'method': 'webdav.config'},
            ],
            'entries': [
                {
                    'type': 'mako',
                    'local_path': 'local/apache24/httpd.conf',
                    'path': 'local/apache2/apache2.conf',
                },
                {
                    'type': 'mako',
                    'local_path': 'local/apache24/Includes/webdav.conf',
                    'path': 'local/apache2/Includes/webdav.conf',
                    'checkpoint': 'pool_import'
                },
                {
                    'type': 'py',
                    'local_path': 'local/apache24/webdav_config',
                    'path': 'local/apache2/webdav_config',
                    'checkpoint': 'pool_import',
                },
            ]
        },
        'nginx': [
            {'type': 'mako', 'path': 'local/nginx/nginx.conf', 'checkpoint': 'interface_sync'}
        ],
        'haproxy': [
            {'type': 'mako', 'path': 'haproxy/haproxy.cfg', 'checkpoint': 'interface_sync'},
        ],
        'glusterd': [
            {
                'type': 'mako',
                'path': 'glusterfs/glusterd.vol',
                'local_path': 'glusterd.conf',
                'user': 'root', 'group': 'root', 'mode': 0o644,
                'checkpoint': 'pool_import',
            },
        ],
        'keepalived': [
            {
                'type': 'mako',
                'path': 'keepalived/keepalived.conf',
                'user': 'root', 'group': 'root', 'mode': 0o644,
                'local_path': 'keepalived.conf',
            },

        ],
        'collectd': [
            {
                'type': 'mako', 'path': 'collectd/collectd.conf',
                'local_path': 'local/collectd.conf', 'checkpoint': 'pool_import',
            },
            {'type': 'mako', 'path': 'default/rrdcached', 'checkpoint': 'pool_import'},
        ],
        'motd': [
            {'type': 'mako', 'path': 'motd'}
        ],
        'mdns': [
            {'type': 'mako', 'path': 'local/avahi/avahi-daemon.conf', 'checkpoint': None},
            {'type': 'py', 'path': 'local/avahi/avahi_services', 'checkpoint': None}
        ],
        'nscd': [
            {'type': 'mako', 'path': 'nscd.conf'},
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
        'rsync': [
            {'type': 'mako', 'path': 'local/rsyncd.conf', 'checkpoint': 'pool_import'}
        ],
        'smb': [
            {'type': 'mako', 'path': 'local/smb4.conf'},
        ],
        'ctdb': [
            {
                'type': 'mako',
                'path': 'ctdb/ctdb.conf',
                'checkpoint': 'pool_import',
                'local_path': 'ctdb.conf',
            },
        ],
        'snmpd': [
            {'type': 'mako', 'path': 'snmp/snmpd.conf', 'local_path': 'local/snmpd.conf'},
        ],
        'syslogd': [
            {'type': 'py', 'path': 'syslogd', 'checkpoint': 'pool_import'},
        ],
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
                {'type': 'mako', 'path': 'local/users.oath', 'mode': 0o0600},
                {'type': 'py', 'path': 'local/ssh/config'},
            ]
        },
        'ntpd': [
            {'type': 'mako', 'path': 'ntp.conf'}
        ],
        'localtime': [
            {'type': 'py', 'path': 'localtime_config'}
        ],
        'inadyn': [
            {'type': 'mako', 'path': 'local/inadyn.conf'}
        ],
        'openvpn_server': [
            {
                'type': 'mako', 'local_path': 'local/openvpn/server/openvpn_server.conf',
                'path': 'local/openvpn/server/server.conf'
            },
            {'type': 'py', 'path': 'local/openvpn/server/perms'},
        ],
        'openvpn_client': [
            {
                'type': 'mako', 'local_path': 'local/openvpn/client/openvpn_client.conf',
                'path': 'local/openvpn/client/client.conf'
            }
        ],
        'kmip': [
            {'type': 'mako', 'path': 'pykmip/pykmip.conf'}
        ],
        'truecommand': [
            {'type': 'mako', 'path': 'wireguard/ix-truecommand.conf'},
        ],
        'k3s': [
            {'type': 'mako', 'path': 'containerd.env', 'checkpoint': None},
            {'type': 'py', 'path': 'rancher/k3s/flags', 'checkpoint': None},
            {'type': 'py', 'path': 'rancher/node/node_passwd', 'checkpoint': None},
        ],
        'cni': [
            {'type': 'py', 'path': 'cni/multus', 'checkpoint': None},
            {'type': 'py', 'path': 'cni/kube-router', 'checkpoint': None},
            {'type': 'mako', 'path': 'cni/net.d/multus.d/multus.kubeconfig', 'checkpoint': None},
            {'type': 'mako', 'path': 'cni/net.d/kube-router.d/kubeconfig', 'checkpoint': None},
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
            rv[method] = await self.middleware.call(method, *args)

        return rv

    def set_etc_file_perms(self, fd, entry):
        perm_changed = False
        user_name = entry.get('owner')
        group_name = entry.get('group')
        mode = entry.get('mode', DEFAULT_ETC_PERMS)

        if all(i is None for i in (user_name, group_name, mode)):
            return perm_changed

        uid = self.middleware.call_sync('user.get_builtin_user_id', user_name) if user_name else -1
        gid = self.middleware.call_sync('group.get_builtin_group_id', group_name) if group_name else -1
        st = os.fstat(fd)
        uid_to_set = -1
        gid_to_set = -1

        if uid != -1 and st.st_uid != uid:
            uid_to_set = uid

        if gid != -1 and st.st_gid != gid:
            gid_to_set = gid

        if gid_to_set != -1 or uid_to_set != -1:
            os.fchown(fd, uid_to_set, gid_to_set)
            perm_changed = True

        if mode and stat.S_IMODE(st.st_mode) != mode:
            os.fchmod(fd, mode)
            perm_changed = True

        return perm_changed

    def make_changes(self, full_path, entry, rendered):
        mode = entry.get('mode', DEFAULT_ETC_PERMS)

        def opener(path, flags):
            return os.open(path, os.O_CREAT | os.O_RDWR, mode=mode)

        outfile_dirname = os.path.dirname(full_path)
        if outfile_dirname != '/etc':
            os.makedirs(outfile_dirname, exist_ok=True)

        with open(full_path, "w", opener=opener) as f:
            perms_changed = self.set_etc_file_perms(f.fileno(), entry)
            contents_changed = write_if_changed(f.fileno(), rendered)

        return perms_changed or contents_changed

    async def generate(self, name, checkpoint=None):
        group = self.GROUPS.get(name)
        if group is None:
            raise ValueError('{0} group not found'.format(name))

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

                if 'platform' in entry and entry['platform'].upper() != osc.SYSTEM:
                    continue

                if checkpoint:
                    checkpoint_system = f'checkpoint_{osc.SYSTEM.lower()}'
                    if checkpoint_system in entry:
                        entry_checkpoint = entry[checkpoint_system]
                    else:
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
                    except FileNotFoundError:
                        pass

                    continue
                except Exception:
                    self.logger.error(f'Failed to render {entry["type"]}:{entry["path"]}', exc_info=True)
                    continue

                if rendered is None:
                    continue

                changes = await self.middleware.run_in_thread(self.make_changes, outfile, entry, rendered)

                if not changes:
                    self.logger.debug(f'No new changes for {outfile}')

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
