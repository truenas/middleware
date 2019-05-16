from mako import exceptions
from mako.lookup import TemplateLookup
from middlewared.service import Service
from middlewared.utils.exceptions import FileShouldNotExist
from middlewared.utils.io import write_if_changed

import asyncio
import grp
import imp
import os
import pwd


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
                return tmpl.render(middleware=self.service.middleware, FileShouldNotExist=FileShouldNotExist)

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

    GROUPS = {
        'user': [
            {'type': 'mako', 'path': 'group'},
            {'type': 'mako', 'path': 'master.passwd'},
            {'type': 'py', 'path': 'pwd_db'},
        ],
        'kerberos': [
            {'type': 'mako', 'path': 'krb5.conf'},
            {'type': 'py', 'path': 'krb5.keytab'},
        ],
        'afpd': [
            {'type': 'py', 'path': 'afpd'},
        ],
        'cron': [
            {'type': 'mako', 'path': 'crontab'},
        ],
        'ctld': [
            {'type': 'py', 'path': 'ctld'},
        ],
        'ldap': [
            {'type': 'mako', 'path': 'local/openldap/ldap.conf'},
        ],
        'loader': [
            {'type': 'py', 'path': 'loader'},
        ],
        'network': [
            {'type': 'mako', 'path': 'dhclient.conf'},
        ],
        'nfsd': [
            {'type': 'py', 'path': 'nfsd'},
        ],
        'nss': [
            {'type': 'mako', 'path': 'nsswitch.conf'},
            {'type': 'mako', 'path': 'local/nslcd.conf',
                'owner': 'nslcd', 'group': 'nslcd', 'mode': 0o0400},
            {'type': 'mako', 'path': 'local/nss_ldap.conf'},
        ],
        'pam': [
            {'type': 'mako', 'path': os.path.join('pam.d', f)}
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
            {'type': 'py', 'path': 'rc.conf'},
        ],
        'sysctl': [
            {'type': 'py', 'path': 'sysctl_config'}
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
        'webdav': [
            {'type': 'mako', 'path': 'local/apache24/httpd.conf'},
            {'type': 'mako', 'path': 'local/apache24/Includes/webdav.conf'},
            {'type': 'py', 'path': 'local/apache24/webdav_config'},
        ],
        'nginx': [
            {'type': 'mako', 'path': 'local/nginx/nginx.conf'}
        ],
        'fstab': [
            {'type': 'mako', 'path': 'fstab'},
            {'type': 'py', 'path': 'fstab_configure'}
        ],
        'collectd': [
            {'type': 'mako', 'path': 'local/collectd.conf'}
        ],
        'system_dataset': [
            {'type': 'py', 'path': 'system_setup'}
        ],
        'netdata': [
            {'type': 'mako', 'path': 'local/netdata/netdata.conf'},
            {'type': 'mako', 'path': 'local/netdata/stream.conf'},
            {'type': 'py', 'path': 'local/netdata/alarms'}
        ],
        'inetd': [
            {'type': 'py', 'path': 'inetd_conf'}
        ],
        'motd': [
            {'type': 'mako', 'path': 'motd'}
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
            {'type': 'mako', 'path': 'local/rsyncd.conf'}
        ],
        'smb': [
            {'type': 'mako', 'path': 'local/smb4.conf'},
        ],
        'smb_share': [
            {'type': 'mako', 'path': 'local/smb4_share.conf'},
        ],
        'smb_configure': [
            {'type': 'mako', 'path': 'local/smbusername.map'},
            {'type': 'py', 'path': 'smb_configure'},
        ],
        'snmpd': [
            {'type': 'mako', 'path': 'local/snmpd.conf'},
        ],
        'sudoers': [
            {'type': 'mako', 'path': 'local/sudoers'}
        ],
        'syslogd': [
            {'type': 'py', 'path': 'syslogd'},
        ],
        'hostname': [
            {'type': 'mako', 'path': 'hosts'}
        ],
        'ssh': [
            {'type': 'mako', 'path': 'local/ssh/sshd_config'},
            {'type': 'mako', 'path': 'pam.d/sshd'},
            {'type': 'mako', 'path': 'local/users.oath', 'mode': 0o0600},
            {'type': 'py', 'path': 'local/ssh/config'}
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
            {'type': 'mako', 'path': 'mail/aliases'}
        ],
        'ttys': [
            {'type': 'mako', 'path': 'ttys'},
            {'type': 'py', 'path': 'ttys_config'}
        ],
        'openvpn_server': [
            {'type': 'mako', 'path': 'local/openvpn/server/openvpn_server.conf'}
        ]
    }

    SKIP_LIST = ['system_dataset', 'collectd', 'syslogd', 'smb_configure']

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

    async def generate(self, name):
        group = self.GROUPS.get(name)
        if group is None:
            raise ValueError('{0} group not found'.format(name))

        for entry in group:

            renderer = self._renderers.get(entry['type'])
            if renderer is None:
                raise ValueError(f'Unknown type: {entry["type"]}')

            path = os.path.join(self.files_dir, entry['path'])
            outfile = f'/etc/{entry["path"]}'
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

    async def generate_all(self, skip_list=True):
        """
        Generate all configuration file groups
        `skip_list` tells whether to skip groups in SKIP_LIST. This defaults to true.
        """
        for name in self.GROUPS.keys():
            if skip_list and name in self.SKIP_LIST:
                self.logger.info(f'Skipping {name} group generation')
                continue

            try:
                await self.generate(name)
            except Exception:
                self.logger.error(f'Failed to generate {name} group', exc_info=True)
