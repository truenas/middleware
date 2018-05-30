from mako import exceptions
from mako.template import Template
from mako.lookup import TemplateLookup
from middlewared.service import Service

import grp
import hashlib
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
                return tmpl.render(middleware=self.service.middleware)

            return await self.service.middleware.run_in_thread(do)
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
        return await mod.render(self.service, self.service.middleware)


class EtcService(Service):

    GROUPS = {
        # 'user': [
        #    {'type': 'mako', 'path': 'master.passwd'},
        #    {'type': 'py', 'path': 'pwd_db'},
        # ],

        #
        # Coming soon
        #
        # 'kerberos': [
        #    {'type': 'mako', 'path': 'krb5.conf'},
        #    {'type': 'mako', 'path': 'krb5.keytab'},
        # ],

        'ldap': [
            {'type': 'mako', 'path': 'local/openldap/ldap.conf'},
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
                'owner': 'nslcd', 'group': 'nslcd', 'mode': 0o0644},
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
        's3': [
            {'type': 'py', 'path': 'local/minio/certificates'},
        ],
        'smartd': [
            {'type': 'py', 'path': 'smartd'},
        ],
    }

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
            try:
                rendered = await renderer.render(path)
            except Exception:
                self.logger.error(f'Failed to render {entry["type"]}:{entry["path"]}', exc_info=True)
                continue

            if rendered is None:
                continue

            outfile = '/etc/{0}'.format(entry['path'])
            changes = False

            # Check hash of generated and existing file
            # Do not rewrite if they are the same
            if os.path.exists(outfile):
                with open(outfile, 'rb') as f:
                    existing_hash = hashlib.sha256(f.read()).hexdigest()

                new_hash = hashlib.sha256(rendered.encode('utf-8')).hexdigest()
                if existing_hash != new_hash:
                    with open(outfile, 'w') as f:
                        f.write(rendered)
                        changes = True

            if not os.path.exists(outfile):
                continue

            # If ownership or permissions are specified, see if
            # they need to be changed.
            st = os.stat(outfile)
            if 'owner' in entry and entry['owner']:
                try:
                    pw = pwd.getpwnam(entry['owner'])
                    if st.st_uid != pw.pw_uid:
                        os.chown(outfile, pw.pw_uid, -1)
                        changes = True
                except Exception as e:
                    pass
            if 'group' in entry and entry['group']:
                try:
                    gr = grp.getgrnam(entry['group'])
                    if st.st_gid != gr.gr_gid:
                        os.chown(outfile, -1, gr.gr_gid)
                        changes = True
                except Exception as e:
                    pass
            if 'mode' in entry and entry['mode']:
                try:
                    if (st.st_mode & 0x3FF) != entry['mode']:
                        os.chmod(outfile, entry['mode'])
                        changes = True
                except Exception as e:
                    pass

            if not changes:
                self.logger.debug(f'No new changes for {outfile}')

    async def generate_all(self):
        """
        Generate all configuration file groups
        """
        for name in self.GROUPS.keys():
            try:
                await self.generate(name)
            except Exception:
                self.logger.error(f'Failed to generate {name} group', exc_info=True)
