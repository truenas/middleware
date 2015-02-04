#!/usr/local/bin/python

import os
import re
import string
import sys
import tempfile
import time

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI'
])

os.environ["DJANGO_SETTINGS_MODULE"] = "freenasUI.settings"

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from django.db.models import Q

from freenasUI.middleware.notifier import notifier
from freenasUI.common.freenasldap import (
    FreeNAS_ActiveDirectory,
    FreeNAS_LDAP,
    FLAGS_DBINIT
)
from freenasUI.common.ssl import (
    get_certificate_path,
    get_privatekey_path,
    get_certificateauthority_path,
    get_certificateauthority_privatekey_path
)
from freenasUI.common.system import (
    activedirectory_enabled,
    domaincontroller_enabled,
    ldap_enabled
)
from freenasUI.directoryservice.models import (
    ActiveDirectory,
    LDAP
)
from freenasUI.services.models import (
    CIFS,
    services
)
from freenasUI.sharing.models import CIFS_Share
from freenasUI.system.models import Settings

SSSD_CONFIGFILE	="/usr/local/etc/sssd/sssd.conf"

class SSSDBase(object):
    def __init__(self, *args, **kwargs):
        self.path = SSSD_CONFIGFILE
        self.stdin = sys.stdin
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        self._config = []

        for key in kwargs:
            if key == 'path' and kwargs[key]:
                self.path = kwargs[key]
            elif key == 'stdin' and kwargs[key]:
                self.stdin = kwargs[key]
            elif key == 'stdout' and kwargs[key]:
                self.stdout = kwargs[key]
            elif key == 'stderr' and kwargs[key]:
                self.stderr = kwargs[key]

    def parse(self, line):
        if not line:
            self._config.append(line)
        elif line.startswith(';'):
            self._config.append(line)
        elif line.startswith('#'):
            self._config.append(line)
        else:
            parts = line.split(' ')
            if len(parts) > 2:
                key = parts[0]
                val = string.join(parts[2:], ' ')
                self._config.append({ key : val })

    def get_section_type(self): 
        return None
    def get_header(self):
        return None

    def get_config(self):
        str = None
        if not self.is_empty():
            for pair in self._config:
                if isinstance(pair, dict):
                    for key in pair.keys():  
                        line = "%s = %s" % (key, pair[key])
                elif isinstance(pair, basestring):
                    line = "%s" % pair
                lines.append(line.strip())
            str = string.join(lines, '\n')
        return "%s" % str

    def generate_header(self):
        if not self.is_empty():
            print >> self.stdout, self.get_header()

    def generate_config(self):
        if not self.is_empty():
            for pair in self._config:
                try:
                    for key in pair.keys():  
                        print >> self.stdout, "%s = %s" % (key, pair[key])
                except: 
                        print >> self.stdout, "%s" % pair

    def is_empty(self):
        ret = True  
        if len(self._config):
            ret = False
        return ret

    def __str__(self):
        str = None
        
        if self.is_empty():
            str = self.get_header()
        else:
            lines = []
            header = self.get_header()
            if header:
                lines.append(header.strip())
            for pair in self._config:
                if isinstance(pair, dict):
                    for key in pair.keys():  
                        line = "%s = %s" % (key, pair[key])
                elif isinstance(pair, basestring):
                    line = "%s" % pair
                lines.append(line.strip())
            str = string.join(lines, '\n')

        return "%s" % str

    def __len__(self):
        len = 0  
        if not self.is_empty():
            for pair in self._config:
                len += 1  
        return len


class SSSDSectionBase(SSSDBase):
    def add_newline(self):
        self._config.append('\n')

    def add_comment(self, comment, delim='#'):
        self._config.append('%s %s' % (delim, comment.strip()))

    def __setattr__(self, name, value):
        if name in ('stdin', 'stdout', 'stderr', 'path', 'domain', '_config'):
            super(SSSDSectionBase, self).__setattr__(name, value)  
        else:
            i = 0
            found = False 
            length = len(self._config)

            while i < length:
                pair = self._config[i]
                if isinstance(pair, dict):
                    if name in pair:
                        pair[name] = value  
                        found = True
                i += 1

            if not found:
                self._config.append({ name : value})

    def __getattr__(self, name):
        attr = None
        if name in ('stdin', 'stdout', 'stderr', 'path', 'domain', '_config'):
            attr = super(SSSDSectionBase, self).__getattr__(name)
        else:
            for pair in self._config:
                if isinstance(pair, dict) and name in pair:
                    attr = pair[name]
        return attr

    def __iter__(self):
        for pair in self._config:
            if isinstance(pair, dict):
                yield pair.keys()[0]
            else:
                yield pair

    def get_header(self):
        return "[%s]" % self.get_section_type()


class SSSDSectionNULL(SSSDSectionBase):
    def __str__(self):
        if self.is_empty():
            return ""
        else:
            return super(SSSDSectionNULL, self).__str__()


class SSSDSectionSSSD(SSSDSectionBase):
    def get_section_type(self): 
        return "sssd"

    def add_domain(self, domain):
        if not self.domains:
            self.domains = domain
        else:
            domains = []
            self_domains = self.domains.split(',')
            for d in self_domains:
                d = d.strip()  
                domains.append(d)
                if d == domain:
                    return
            domains.append(domain)
            self.domains = string.join(domains, ',')

    def add_service(self, service):
        if not service in ('nss', 'pam', 'sudo', 'ssh'):
            return
        if not self.services:
            self.services = service
        else:
            services = []
            self_services = self.services.split(',')
            for s in self_services:
                s = s.strip()  
                services.append(s)
                if s == service:
                    return
            services.append(service)
            self.services = string.join(services, ',')


class SSSDServiceSectionBase(SSSDSectionBase):
    pass


class SSSDSectionNSS(SSSDServiceSectionBase):
    def get_section_type(self): 
        return "nss"


class SSSDSectionPAM(SSSDServiceSectionBase):
    def get_section_type(self): 
        return "pam"


class SSSDSectionSUDO(SSSDServiceSectionBase):
    def get_section_type(self): 
        return "sudo"


class SSSDSectionSSH(SSSDServiceSectionBase):
    def get_section_type(self): 
        return "ssh"


class SSSDSectionDomain(SSSDSectionBase):
    def __init__(self, *args, **kwargs):
        super(SSSDSectionDomain, self).__init__(*args, **kwargs)

        self.domain = None  
        if args and args[0]:
            parts = args[0].split('/')
            if parts and len(parts) > 1:
                self.domain = parts[1]

    def is_empty(self):
        if not self.domain:
            return True  
        return super(SSSDSectionDomain, self).is_empty()

    def get_section_type(self): 
        if self.domain:
            return "domain/%s" % self.domain
        return super(SSSDSectionDomain, self).get_section_type()


class SSSDSection(object):
    def __new__(cls, *args, **kwargs):
        obj = None
        if not args:
            return SSSDSectionNULL(*args, **kwargs)

        section = args[0]
        if (section.lower() == 'sssd'):
            obj = SSSDSectionSSSD(*args, **kwargs)
        elif (section.lower() == 'nss'):
            obj = SSSDSectionNSS(*args, **kwargs)
        elif (section.lower() == 'pam'):
            obj = SSSDSectionPAM(*args, **kwargs)
        elif (section.lower() == 'sudo'):
            obj = SSSDSectionSUDO(*args, **kwargs)
        elif (section.lower() == 'ssh'):
            obj = SSSDSectionSSH(*args, **kwargs)
        elif (section.lower().startswith('domain')):
            obj = SSSDSectionDomain(*args, **kwargs)
        else:
            obj = SSSDSectionNULL(*args, **kwargs)

        return obj


class SSSDSectionContainer(object):
    def __init__(self):
        super(SSSDSectionContainer, self).__init__()
        self.sections = []

    def __setattr__(self, name, value):
        if name != 'sections':
            self.sections.append({ name : value })
        else:
            super(SSSDSectionContainer, self).__setattr__(name, value)

    def __setitem__(self, name, value):
        if name != 'sections':
            for section in self.sections:
                key = section.keys()[0]
                if key == name:
                    section[key] = value
                    return
            self.sections.append({ name : value })
        else:
            super(SSSDSectionContainer, self).__setitem__(name, value)

    def __getattr__(self, name):
        if name != 'sections':
            section = None
            for s in self.sections:
                key = s.keys()[0]
                if key == name:
                    section = s[key]
            return section
                
        else:
            return super(SSSDSectionContainer, self).__getattr__(name)

    def __getitem__(self, name):
        return self.__getattr__(name)

    def __iter__(self):
        for section in self.sections:
            yield section[section.keys()[0]]


class SSSDConf(SSSDBase):
    def __init__(self, *args, **kwargs):
        super(SSSDConf, self).__init__(*args, **kwargs)
        self.sections = SSSDSectionContainer()

        if 'parse' in kwargs:
            self.parse = kwargs.pop('parse')

        self.parse()

    def parse(self):
        with open(self.path, "r") as f:
            lines = f.readlines()
            f.close()

        section = None
        for line in lines:
            line = line.strip()

            if line.startswith('['):
                r = re.match('^\[([^\s]+)\]', line)
                if r:
                    s = r.group(1)
                    section = SSSDSection(s)
                    self.sections[s] = section

            elif section != None:
                section.parse(line)  

    def keys(self):
        keys = []   
        for section in self.sections:
            key = section.get_section_type()
            if key:
                keys.append(key)
        return keys

    def __iter__(self):
        for key in self.keys():
            yield self.sections[key]

    def __getitem__(self, name):
        if name != 'sections':
            return self.sections[name]
        else:
            return super(SSSDConf, self).__getitem__(name)

    def __setitem__(self, name, value):
        if name != 'sections':
            self.sections[name] = value
        else:
            super(SSSDConf, self).__setitem__(name, value)

    def __str__(self):
        str = None
        for s in self.sections:
            if not str:
                str = "%s" % s
            else:
                str = "%s\n%s" % (str, s)  
        return "%s" % str

    def save(self, path=None):
        stdout = self.stdout
        if path:
            stdout = open(path, "w")

        print >> stdout, self.__str__()  

        if path:
            stdout.close()
            os.chmod(path, 0600)


def activedirectory_has_unix_extensions():
    ad_unix_extensions = False

    try:
        ad = ActiveDirectory.objects.all()[0]
        ad_unix_extensions = ad.ad_unix_extensions
    except:
        pass

    return ad_unix_extensions


def sssd_mkdir(dir):
    try:
        os.makedirs(dir)
    except Exception as e:
        pass


def sssd_setup():
    sssd_mkdir("/var/log/sssd")
    sssd_mkdir("/var/db/sss")
    sssd_mkdir("/var/db/sss_mc")
    sssd_mkdir("/var/run/sss/private")

    if os.path.exists(SSSD_CONFIGFILE):
        os.chown(SSSD_CONFIGFILE, 0, 0)
        os.chmod(SSSD_CONFIGFILE, 0600)


def add_ldap(sc):
    ldap = LDAP.objects.all()[0]
    cifs = CIFS.objects.all()[0]

    ldap_hostname = ldap.ldap_hostname.upper()
    parts = ldap_hostname.split('.')
    ldap_hostname = parts[0]

    ldap_cookie = ldap_hostname
    ldap_domain = 'domain/%s' % ldap_cookie

    ldap_section = None
    for key in sc.keys():
        if key == ldap_domain:
            ldap_section = sc[key]
            break

    if not ldap_section:
        ldap_section = SSSDSectionDomain(ldap_domain)
        ldap_section.description = ldap_cookie
    if ldap_section.description != ldap_cookie:
        return

    ldap_defaults = [
        { 'enumerate': 'true' },
        { 'cache_credentials': 'true' },
        { 'id_provider': 'ldap'},
        { 'auth_provider': 'ldap' },
        { 'chpass_provider': 'ldap' },
        { 'ldap_schema': 'rfc2307bis' },
        { 'ldap_force_upper_case_realm': 'true' },
        { 'use_fully_qualified_names': 'false' }
    ]

    for d in ldap_defaults:
        key = d.keys()[0]  
        if not key in ldap_section:
            setattr(ldap_section, key, d[key])

    ldap_section.ldap_schema = ldap.ldap_schema
    ldap_section.ldap_uri = "%s://%s" % (
        "ldaps" if ldap.ldap_ssl == 'on' else "ldap",
        ldap.ldap_hostname
    )
    ldap_section.ldap_search_base = ldap.ldap_basedn

    if ldap.ldap_usersuffix:
        ldap_section.ldap_user_search_base = "%s,%s" % (
            ldap.ldap_usersuffix, ldap.ldap_basedn
        )
    else:
        ldap_section.ldap_user_search_base = "%s%s" % (
            ldap.ldap_basedn,
            "?subtree?(objectclass=posixAccount)"
        )

    if ldap.ldap_groupsuffix:
        ldap_section.ldap_group_search_base = "%s,%s" % (
            ldap.ldap_groupsuffix, ldap.ldap_basedn
        )
    else:
        ldap_section.ldap_group_search_base = "%s%s" % (
            ldap.ldap_basedn,
            "?subtree?(objectclass=posixGroup)"
        )

    if ldap.ldap_sudosuffix:
        if not sc['sudo']:
            sc['sudo'] = SSSDSectionSUDO()
        sc['sssd'].add_service('sudo')
        ldap_section.sudo_provider = 'ldap' 
        ldap_section.ldap_sudo_search_base = "%s,%s" % (
            ldap.ldap_sudosuffix,
            ldap.ldap_basedn
        )

    if ldap.ldap_ssl == 'on':
        certpath = get_certificateauthority_path(ldap.ldap_certificate)
        if certpath:
            ldap_section.ldap_tls_cacert = certpath

    elif ldap.ldap_ssl == 'start_tls':
        ldap_section.tls_reqcert = 'demand'
        certpath = get_certificateauthority_path(ldap.ldap_certificate)
        if certpath:
            ldap_section.ldap_tls_cacert = certpath
        ldap_section.ldap_id_use_start_tls = 'true'

    if ldap.ldap_auxiliary_parameters:
        lines = ldap.ldap_auxiliary_parameters.splitlines()
        for l in lines:
            parts = l.split('=',1)
            if len(parts) < 2:
                continue
            setattr(ldap_section, parts[0].strip(), parts[1].strip())

    ldap = FreeNAS_LDAP(flags=FLAGS_DBINIT)
    
    if ldap.keytab_name and ldap.kerberos_realm:
        ldap_section.auth_provider = 'krb5'
        ldap_section.chpass_provider = 'krb5'
        ldap_section.ldap_sasl_mech = 'GSSAPI'
        ldap_section.ldap_sasl_authid = ldap.keytab_principal
        ldap_section.krb5_server = ldap.krb_kdc
        ldap_section.krb5_realm = ldap.krb_realm
        ldap_section.krb5_canonicalize = 'false'

    else:
        ldap_section.ldap_default_bind_dn = ldap.binddn
        ldap_section.ldap_default_authtok_type = 'password'
        ldap_section.ldap_default_authtok = ldap.bindpw

    sc[ldap_domain] = ldap_section
    sc['sssd'].add_domain(ldap_cookie)
    sc['sssd'].add_newline()


def add_activedirectory(sc):
    activedirectory = ActiveDirectory.objects.all()[0]
    ad = FreeNAS_ActiveDirectory(flags=FLAGS_DBINIT)
    use_ad_provider = False

    ad_cookie = ad.netbiosname
    ad_domain = 'domain/%s' % ad_cookie

    ad_section = None
    for key in sc.keys():
        if key == ad_domain:
            ad_section = sc[key]
            break

    if not ad_section:
        ad_section = SSSDSectionDomain(ad_domain)
        ad_section.description = ad_cookie
    if ad_section.description != ad_cookie:
        return

    ad_defaults = [
        { 'enumerate': 'true' },
        { 'id_provider': 'ldap'},
        { 'auth_provider': 'ldap' },
        { 'access_provider': 'ldap' },
        { 'chpass_provider': 'ldap' },
        { 'ldap_schema': 'rfc2307bis' },
        { 'ldap_user_object_class': 'person' },
        { 'ldap_user_name': 'msSFU30Name' },
        { 'ldap_user_uid_number': 'uidNumber' },
        { 'ldap_user_gid_number': 'gidNumber' },
        { 'ldap_user_home_directory': 'unixHomeDirectory' },
        { 'ldap_user_shell': 'loginShell' },
        { 'ldap_user_principal': 'userPrincipalName' },
        { 'ldap_group_object_class': 'group' },
        { 'ldap_group_name': 'msSFU30Name' },
        { 'ldap_group_gid_number': 'gidNumber' },
        { 'ldap_force_upper_case_realm': 'true' },
        { 'use_fully_qualified_names': 'true' }
    ]

    __, hostname, __ = os.uname()[0:3]

    if ad.keytab_name and ad.kerberos_realm and os.path.exists(ad.keytab_file):
        use_ad_provider = True

    if use_ad_provider:
        for d in ad_defaults:
            key = d.keys()[0]  
            if key.startswith("ldap_") and key in d:
                del d[key]
            elif key.endswith("_provider"):
                d[key] = 'ad'

        ad_section.ad_hostname = hostname
        ad_section.ad_domain = ad.domainname
        ad_section.ldap_id_mapping = False

    for d in ad_defaults:
        if not d: 
            continue
        key = d.keys()[0]  
        if not key in ad_section:
            setattr(ad_section, key, d[key])

    if activedirectory.ad_use_default_domain:
        ad_section.use_fully_qualified_names = 'false'

    try:
        shares = CIFS_Share.objects.all()
        for share in shares:  
            if share.cifs_home:
                if ad.use_default_domain:
                    homedir_path = "%s/%%u" % share.cifs_path
                else:
                    homedir_path = "%s/%%d/%%u" % share.cifs_path

                ad_section.override_homedir = homedir_path
        
    except Exception as e:
        pass

    if use_ad_provider:
        pass

#        ad_section.auth_provider = 'krb5'
#        ad_section.chpass_provider = 'krb5'
#        ad_section.ldap_sasl_mech = 'GSSAPI'
#        ad_section.ldap_sasl_authid = ad.keytab_principal
#        ad_section.krb5_server = ad.krb_kdc
#        ad_section.krb5_realm = ad.krb_realm
#        ad_section.krb5_canonicalize = 'false'

    else:
        ad_section.ldap_uri = "ldap://%s" % ad.dchost
        ad_section.ldap_search_base = ad.basedn

        ad_section.ldap_default_bind_dn = ad.binddn
        ad_section.ldap_default_authtok_type = 'password'
        ad_section.ldap_default_authtok = ad.bindpw

    sc[ad_domain] = ad_section
    sc['sssd'].add_domain(ad_cookie)
    sc['sssd'].add_newline()


def main():
    sssd_conf = None

    sssd_setup()
    if os.path.exists(SSSD_CONFIGFILE):
        sssd_conf = SSSD_CONFIGFILE

    def nullfunc(): pass
    sc = SSSDConf(path=sssd_conf, parse=nullfunc)
    if not sc['sssd']:
        sc['sssd'] = SSSDSectionSSSD()
        sc['sssd'].config_file_version = 2
    sc['sssd'].full_name_format = r"%2$s\%1$s"
    sc['sssd'].re_expression = r"(((?P<domain>[^\\]+)\\(?P<name>.+$))" \
        r"|((?P<name>[^@]+)@(?P<domain>.+$))|(^(?P<name>[^@\\]+)$))"

    if not sc['nss']:
        sc['nss'] = SSSDSectionNSS()
    sc['sssd'].add_service('nss')

    if not sc['pam']:
        sc['pam'] = SSSDSectionPAM()
    sc['sssd'].add_service('pam')
    
    if activedirectory_enabled() and activedirectory_has_unix_extensions():
        add_activedirectory(sc)
    if ldap_enabled():
        add_ldap(sc)

    sc.save(SSSD_CONFIGFILE)

if __name__ == '__main__':
    main()
