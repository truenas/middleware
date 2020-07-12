from mako import exceptions
from mako.lookup import TemplateLookup
from middlewared.service import CallError, Service
from middlewared.utils import osc
from middlewared.utils.io import write_if_changed

import asyncio
from collections import defaultdict
import grp
import imp
import os
import pwd


class FileShouldNotExist(Exception):
    pass


class MakoRenderer(object):

    def __init__(self, service):
        self.service = service

    async def render(self, path):
        try:
            # Mako is not asyncio friendly so run it within a thread
            def do():
                # Split the path into template name and directory
                name = os.path.basename(path)
                dir = os.path.dirname(path)

                # This will be where we search for templates
                lookup = TemplateLookup(directories=[dir], module_directory="/tmp/mako/%s" % dir)

                # Get the template by its relative path
                tmpl = lookup.get_template(name)

                # Render the template
                return tmpl.render(
                    middleware=self.service.middleware,
                    service=self.service,
                    FileShouldNotExist=FileShouldNotExist,
                    IS_FREEBSD=osc.IS_FREEBSD,
                    IS_LINUX=osc.IS_LINUX,
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

    async def render(self, path):
        name = os.path.basename(path)
        find = imp.find_module(name, [os.path.dirname(path)])
        mod = imp.load_module(name, *find)
        if asyncio.iscoroutinefunction(mod.render):
            return await mod.render(self.service, self.service.middleware)
        else:
            return await self.service.middleware.run_in_thread(
                mod.render, self.service, self.service.middleware,
            )


class EtcService(Service):

    APACHE_DIR = 'local/apache24' if osc.IS_FREEBSD else 'local/apache2'

    GROUPS = {
        'user': [
            {'type': 'mako', 'path': 'local/smbusername.map'},
            {'type': 'mako', 'path': 'group'},
            {'type': 'mako', 'path': 'master.passwd' if osc.IS_FREEBSD else 'passwd', 'local_path': 'master.passwd'},
            {'type': 'py', 'path': 'pwd_db', 'platform': 'FreeBSD'},
            {'type': 'mako', 'path': 'shadow', 'platform': 'Linux', 'group': 'shadow', 'mode': 0o0640},
        ],
        'fstab': [
            {'type': 'mako', 'path': 'fstab'},
            {'type': 'py', 'path': 'fstab_configure', 'checkpoint_linux': 'post_init'}
        ],
        'system_dataset': [
            {'type': 'py', 'path': 'system_setup', 'checkpoint': 'pool_import'}
        ],
        'kerberos': [
            {'type': 'mako', 'path': 'krb5.conf'},
            {'type': 'py', 'path': 'krb5.keytab'},
        ],
        'afpd': [
            {'type': 'py', 'path': 'afpd', 'checkpoint': 'pool_import'},
        ],
        'cron': [
            {'type': 'mako', 'path': 'cron.d/middlewared', 'checkpoint': 'pool_import'},
            {'type': 'mako', 'path': 'crontab', 'platform': 'FreeBSD'},
        ],
        'ctld': [
            {'type': 'py', 'path': 'ctld', 'platform': 'FreeBSD', 'checkpoint': 'pool_import'},
        ],
        'grub': [
            {'type': 'py', 'path': 'grub', 'platform': 'Linux', 'checkpoint': 'post_init'},
        ],
        'ldap': [
            {'type': 'mako', 'path': 'local/openldap/ldap.conf'},
        ],
        'loader': [
            {'type': 'py', 'path': 'loader', 'platform': 'FreeBSD'},
        ],
        'network': [
            {'type': 'mako', 'path': 'dhclient.conf', 'platform': 'FreeBSD'},
        ],
        'nfsd': [
            {'type': 'py', 'path': 'nfsd', 'platform': 'FreeBSD', 'checkpoint': 'pool_import'},
            {'type': 'mako', 'path': 'default/nfs-common', 'platform': 'Linux'},
            {'type': 'mako', 'path': 'ganesha/ganesha.conf', 'platform': 'Linux', 'checkpoint': 'pool_import'},
        ],
        'nss': [
            {'type': 'mako', 'path': 'nsswitch.conf'},
            {'type': 'mako', 'path': 'local/nslcd.conf',
                'owner': 'nslcd', 'group': 'nslcd', 'mode': 0o0400},
        ],
        'pam': [
            {'type': 'mako', 'path': os.path.join('pam.d', f), 'platform': 'FreeBSD'}
            for f in os.listdir(
                os.path.realpath(
                    os.path.join(
                        os.path.dirname(__file__), '..', 'etc_files', 'pam.d'
                    )
                )
            )
        ],
        'ftp': [
            {'type': 'mako', 'path': 'local/proftpd.conf'},
            {'type': 'py', 'path': 'local/proftpd'},
        ],
        'rc': [
            {'type': 'py', 'path': 'rc.conf', 'platform': 'FreeBSD'},
            {'type': 'py', 'path': 'systemd', 'platform': 'Linux'},
        ],
        'sysctl': [
            {'type': 'py', 'path': 'sysctl_config'},
        ],
        's3': [
            {'type': 'py', 'path': 'local/minio/certificates'},
        ],
        'smartd': [
            {'type': 'py', 'path': 'smartd'},
        ],
        'ssl': [
            {'type': 'py', 'path': 'generate_ssl_certs'},
        ],
        'scst': [
            {
                'type': 'mako', 'path': 'scst.conf', 'platform': 'Linux',
                'local_path': 'scst.conf.mako', 'checkpoint': 'pool_import',
            }
        ],
        'webdav': [
            {
                'type': 'mako',
                'local_path': 'local/apache24/httpd.conf',
                'path': f'{APACHE_DIR}/httpd.conf',
            },
            {
                'type': 'mako',
                'local_path': 'local/apache24/Includes/webdav.conf',
                'path': f'{APACHE_DIR}/Includes/webdav.conf',
                'checkpoint': 'pool_import'
            },
            {
                'type': 'py',
                'local_path': 'local/apache24/webdav_config',
                'path': f'{APACHE_DIR}/webdav_config',
                'checkpoint': 'pool_import',
            },
        ],
        'nginx': [
            {'type': 'mako', 'path': 'local/nginx/nginx.conf', 'checkpoint': 'interface_sync'}
        ],
        'pf': [
            {'type': 'py', 'path': 'pf', 'platform': 'FreeBSD'},
        ],
        'collectd': [
            {
                'type': 'mako', 'path': 'local/collectd.conf' if osc.IS_FREEBSD else 'collectd/collectd.conf',
                'local_path': 'local/collectd.conf', 'checkpoint': 'pool_import',
            },
            {'type': 'mako', 'path': 'default/rrdcached', 'local_path': 'default/rrdcached.mako', 'platform': 'Linux'},
        ],
        'docker': [
            {'type': 'py', 'path': 'docker', 'platform': 'Linux', 'checkpoint': 'pool_import'},
        ],
        'inetd': [
            {'type': 'py', 'path': 'inetd_conf', 'platform': 'FreeBSD'}
        ],
        'motd': [
            {'type': 'mako', 'path': 'motd'}
        ],
        'mdns': [
            {'type': 'mako', 'path': 'local/avahi/avahi-daemon.conf', 'checkpoint': 'interface_sync'},
            {'type': 'py', 'path': 'local/avahi/avahi_services', 'checkpoint': 'interface_sync'}
        ],
        'ups': [
            {'type': 'py', 'path': 'local/nut/ups_config'},
            {'type': 'mako', 'path': 'local/nut/ups.conf', 'owner': 'root', 'group': 'uucp', 'mode': 0o440},
            {'type': 'mako', 'path': 'local/nut/upsd.conf', 'owner': 'root', 'group': 'uucp', 'mode': 0o440},
            {'type': 'mako', 'path': 'local/nut/upsd.users', 'owner': 'root', 'group': 'uucp', 'mode': 0o440},
            {'type': 'mako', 'path': 'local/nut/upsmon.conf', 'owner': 'root', 'group': 'uucp', 'mode': 0o440},
            {'type': 'mako', 'path': 'local/nut/upssched.conf', 'owner': 'root', 'group': 'uucp', 'mode': 0o440},
            {'type': 'py', 'path': 'local/nut/ups_perms'}
        ],
        'rsync': [
            {'type': 'mako', 'path': 'local/rsyncd.conf', 'checkpoint': 'pool_import'}
        ],
        'smb': [
            {'type': 'mako', 'path': 'local/smb4.conf', 'checkpoint': 'pool_import'},
            {'type': 'mako', 'path': 'security/pam_winbind.conf', 'checkpoint': 'pool_import'},
        ],
        'smb_share': [
            {'type': 'mako', 'path': 'local/smb4_share.conf', 'checkpoint': 'pool_import'},
        ],
        'snmpd': [
            {'type': 'mako', 'path': 'local/snmpd.conf' if osc.IS_FREEBSD else 'snmp/snmpd.conf',
             'local_path': 'local/snmpd.conf'},
        ],
        'sudoers': [
            {'type': 'mako', 'path': 'local/sudoers'}
        ],
        'syslogd': [
            {'type': 'py', 'path': 'syslogd', 'checkpoint': 'pool_import'},
        ],
        'hostname': [
            {'type': 'mako', 'path': 'hosts'},
            {'type': 'py', 'path': 'hostname', 'platform': 'Linux'},
        ],
        'ssh': [
            {'type': 'mako', 'path': 'local/ssh/sshd_config', 'checkpoint': 'interface_sync'},
            {'type': 'mako', 'path': 'pam.d/sshd'},
            {'type': 'mako', 'path': 'local/users.oath', 'mode': 0o0600},
            {'type': 'py', 'path': 'local/ssh/config'},
        ],
        'ntpd': [
            {'type': 'mako', 'path': 'ntp.conf'}
        ],
        'localtime': [
            {'type': 'py', 'path': 'localtime_config'}
        ],
        'inadyn': [
            {'type': 'mako', 'path': 'local/inadyn.conf'}
        ],
        'aliases': [
            {'type': 'mako', 'path': 'mail/aliases' if osc.IS_FREEBSD else 'aliases', 'local_path': 'mail/aliases.mako'}
        ],
        'ttys': [
            {'type': 'mako', 'path': 'ttys', 'platform': 'FreeBSD'},
            {'type': 'py', 'path': 'ttys_config', 'checkpoint_linux': None}
        ],
        'openvpn_server': [
            {'type': 'mako', 'path': 'local/openvpn/server/openvpn_server.conf'}
        ],
        'openvpn_client': [
            {'type': 'mako', 'path': 'local/openvpn/client/openvpn_client.conf'}
        ],
        'kmip': [
            {'type': 'mako', 'path': 'pykmip/pykmip.conf'}
        ],
        'truecommand': [
            {'type': 'mako', 'path': 'wireguard/wg0.conf'}
        ]
    }
    LOCKS = defaultdict(asyncio.Lock)

    checkpoints = ['initial', 'interface_sync', 'post_init', 'pool_import']

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

    async def generate(self, name, checkpoint=None):
        group = self.GROUPS.get(name)
        if group is None:
            raise ValueError('{0} group not found'.format(name))

        async with self.LOCKS[name]:
            for entry in group:
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
                if osc.IS_LINUX:
                    if entry_path.startswith('local/'):
                        entry_path = entry_path[len('local/'):]
                outfile = f'/etc/{entry_path}'
                try:
                    rendered = await renderer.render(path)
                except FileShouldNotExist:
                    self.logger.debug(f'{entry["type"]}:{entry["path"]} file removed.')

                    try:
                        os.unlink(outfile)
                    except FileNotFoundError:
                        pass

                    continue
                except Exception:
                    self.logger.error(f'Failed to render {entry["type"]}:{entry["path"]}', exc_info=True)
                    continue

                if rendered is None:
                    continue

                outfile_dirname = os.path.dirname(outfile)
                if not os.path.exists(outfile_dirname):
                    os.makedirs(outfile_dirname)

                changes = write_if_changed(outfile, rendered)

                # If ownership or permissions are specified, see if
                # they need to be changed.
                st = os.stat(outfile)
                if 'owner' in entry and entry['owner']:
                    try:
                        pw = await self.middleware.run_in_thread(pwd.getpwnam, entry['owner'])
                        if st.st_uid != pw.pw_uid:
                            os.chown(outfile, pw.pw_uid, -1)
                            changes = True
                    except Exception:
                        pass
                if 'group' in entry and entry['group']:
                    try:
                        gr = await self.middleware.run_in_thread(grp.getgrnam, entry['group'])
                        if st.st_gid != gr.gr_gid:
                            os.chown(outfile, -1, gr.gr_gid)
                            changes = True
                    except Exception:
                        pass
                if 'mode' in entry and entry['mode']:
                    try:
                        if (st.st_mode & 0x3FF) != entry['mode']:
                            os.chmod(outfile, entry['mode'])
                            changes = True
                    except Exception:
                        pass

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

    if args['id'] == 'ready':
        asyncio.ensure_future(await middleware.call('etc.generate_checkpoint', 'post_init'))


async def setup(middleware):
    middleware.event_subscribe('system', __event_system_ready)
