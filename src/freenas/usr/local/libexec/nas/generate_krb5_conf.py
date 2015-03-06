#!/usr/local/bin/python

import os
import re
import sys
import string
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

from freenasUI.directoryservice.models import (
    KerberosRealm,
    KerberosSettings
)

class KerberosConfigBinding(object):
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __len__(self):
        return 0


class KerberosConfigBindingCollection(list):
    def __init__(self, name=None):
        super(KerberosConfigBindingCollection, self).__init__()
        self.name = name

    def __append(self, item, item_list):
        for i in item_list:
            if isinstance(i , KerberosConfigBinding):
                if i.name == item.name:
                    i.value = item.value
                    return False

            elif isinstance(i, KerberosConfigBindingCollection):
                self.__append(item, i)

        return True

    def append(self, item, item_list=None):
        if self.__append(item, self):
            super(KerberosConfigBindingCollection, self).append(item)

    def merge(self, item_list=None):
        for item in item_list:
            self.append(item)


class KerberosConfigSection(object):
    def __init__(self, section_name, bindings):
        self.section_name = section_name
        self.bindings = KerberosConfigBindingCollection()

        if bindings:
            self.bindings.append(bindings)

    def __len__(self):
        return len(self.bindings)

    def __iter__(self):
        for binding in self.bindings:
            yield binding

class KerberosConfigSectionCollection(list):
    pass

class KerberosConfig(object):
    def tokenize(self, code):
        token = ""
        tokens = []

        for c in code:
            if c == '=':
                if token:
                    tokens.append(token)
                    token = ""
                tokens.append(c)
            elif c == '{':
                tokens.append(c)
            elif c == '}':
                if token:
                    tokens.append(token)
                    token = ""
                tokens.append(c)
            elif c == '\n':
                if token:
                    tokens.append(token) 
                token = ""
            elif re.match('^\s+', c):
                if token:
                    tokens.append(token)
                    token = ""
            else:
                token += c

        return tokens

    def parse(self, section, code):
        if not section or not code:
            return

        pair = []
        stack = []

        bindings = []
        bindings = KerberosConfigBindingCollection()
        ptr = bindings

        tokens = self.tokenize(code)
        for tok in tokens:
            if not tok:
                continue

            tok = tok.strip()
            stack.append(tok)

            if tok == '=':
                try:
                    stack.pop()
                    pair.append(stack.pop())

                except:
                    print >> sys.stderr, "ERROR: syntax error near '='"
                    sys.exit(1)

            elif tok == '{':
                try:
                    stack.pop()
                    collection = KerberosConfigBindingCollection(
                        name=pair[0]
                    )

                except:
                    print >> sys.stderr, "ERROR: syntax error near '{'"
                    sys.exit(1)

                ptr.append(collection)
                ptr = collection
                pair = []

            elif tok == '}':
                try:
                    stack.pop()
                    ptr = ptr[len(ptr) - 1]

                except:
                    print >> sys.stderr, "ERROR: syntax error near '}'"
                    sys.exit(1)

            else:
                if len(pair) == 1:
                    try:
                        pair.append(stack.pop())
                        ptr.append(
                            KerberosConfigBinding(
                                name=pair[0], value=pair[1]
                            )
                        )

                    except:
                        print >> sys.stderr, "ERROR: syntax error"
                        sys.exit(1)

                    pair = []

             
        if bindings:
            section.merge(bindings)

    def create_default_config(self):
       sections = KerberosConfigSectionCollection()

       appdefaults_bindings = KerberosConfigBindingCollection()

       pam_appdefaults_bindings = KerberosConfigBindingCollection(name='pam')
       pam_appdefaults_bindings.append(
           KerberosConfigBinding(
               name='forwardable', value='true'
           )
       )
       pam_appdefaults_bindings.append(
           KerberosConfigBinding(
               name='ticket_lifetime', value='86400'
           )
       )
       pam_appdefaults_bindings.append(
           KerberosConfigBinding(
               name='renew_lifetime', value='86400'
           )
       )

       appdefaults_bindings.append(
           pam_appdefaults_bindings
       )
     
       sections.append(
           KerberosConfigSection(
               section_name='appdefaults',
               bindings=appdefaults_bindings
           )
       )

       self.parse(appdefaults_bindings, self.appdefaults_aux)

       libdefaults_bindings = KerberosConfigBindingCollection()
       libdefaults_bindings.append(
           KerberosConfigBinding(
               name='dns_lookup_realm', value='true'
           ) 
       )
       libdefaults_bindings.append(
           KerberosConfigBinding(
               name='dns_lookup_kdc', value='true'
           ) 
       )
       libdefaults_bindings.append(
           KerberosConfigBinding(
               name='ticket_lifetime', value='24h'
           ) 
       )
       libdefaults_bindings.append(
           KerberosConfigBinding(
               name='clockskew', value='300'
           ) 
       )
       libdefaults_bindings.append(
           KerberosConfigBinding(
               name='forwardable', value='yes'
           ) 
       )

       self.parse(libdefaults_bindings, self.libdefaults_aux)

       sections.append(
           KerberosConfigSection(
               section_name='libdefaults',
               bindings=libdefaults_bindings
           )
       )

       sections.append(KerberosConfigSection(
           section_name='domain_realm', bindings=[])
       )
       sections.append(KerberosConfigSection(
           section_name='realms', bindings=[])
        )
       sections.append(KerberosConfigSection(
           section_name='capaths', bindings=[])
       )

       logging_bindings = KerberosConfigBindingCollection()
       logging_bindings.append(
           KerberosConfigBinding(
               name='default', value='SYSLOG:INFO:LOCAL7' 
           )
       )

       sections.append(
           KerberosConfigSection(
               section_name='logging',
               bindings=logging_bindings
           )
       )

       sections.append(KerberosConfigSection(
           section_name='kdc', bindings=[])
       )
       sections.append(KerberosConfigSection(
           section_name='kadmin', bindings=[])
       )
       sections.append(KerberosConfigSection(
           section_name='password_quality', bindings=[])
       )

       self.sections = sections
  
    def __init__(self, *args, **kwargs):
        self.sections = None

 
        self.krb5_conf = "/etc/krb5.conf"
        if 'krb5_conf' in kwargs:
            self.krb5_conf = kwargs['krb5_conf']

        self.appdefaults_aux = None
        self.libdefaults_aux = None

        if 'settings' in kwargs:
            settings = kwargs['settings']
            if settings and settings.ks_appdefaults_aux:
                self.appdefaults_aux = settings.ks_appdefaults_aux 
            if settings and settings.ks_libdefaults_aux:
                self.libdefaults_aux = settings.ks_libdefaults_aux
            

    def get_section(self, section_name):
        if not section_name:
            return None

        section = None
        for s in self.sections:
            if s.section_name.lower() == section_name.lower():
                section = s
                break

        return section

    def __get_binding(self, item, bindings):
        if not item or bindings == None:
            return None 

        if bindings.name != None and \
            bindings.name.lower() == item.lower():
            return bindings

        if len(bindings) > 0:
            for binding in bindings:
                if binding.name != None and \
                    binding.name.lower() == item.lower():
                    return binding

        return None

    def get_binding(self, where, section=None):
        if section == None:
            section = self.get_section(where[0])

        if section == None:
            return None

        if len(where) == 1:
            return section

        bindings = section.bindings
        for item in where[1:]:
            found_binding = self.__get_binding(item, bindings)
            if found_binding == None:
                break

            bindings = found_binding

        return bindings

    def add_bindings(self, where, bindings):
        if not where:
            return

        section = None
        section_name = where[0] 
        for s in self.sections:
            if s.section_name.lower() == section_name.lower():
                section = s
                break

        if section == None:
            return 

        if len(where) > 1:
            i = 1
            while i < len(where):
                binding = where[i]
                i += 1 

        else:
            section.bindings.append(bindings)
    
    def generate_bindings(self, bindings, tab=4, stdout=sys.stdout):
        if len(bindings) != 0:
            if bindings.name != None:
                print >> stdout, "%s%s = {" % (
                    "".rjust(tab), bindings.name
                )
            for binding in bindings:
                self.generate_bindings(binding, tab + 4, stdout)
            if bindings.name != None:
                print >> stdout, "%s}" % "".rjust(tab)

        else:
            print >> stdout, "%s%s = %s" % (
                "".rjust(tab), bindings.name, bindings.value
            )

    def generate_section(self, section, tab=0, stdout=sys.stdout):
        print >> stdout, "%s[%s]" % (
            "".rjust(tab), section.section_name
        )
        self.generate_bindings(section.bindings, tab + 4, stdout)
        print >> stdout, ""

    def generate_krb5_conf(self, stdout=sys.stdout):
        for section in self.sections:
            if len(section) > 0: 
                self.generate_section(section, 0, stdout)
  

def main():
    realms = KerberosRealm.objects.all()

    try:
        settings = KerberosSettings.objects.all()[0]
    except:
        settings = None


    kc = KerberosConfig(settings=settings)
    kc.create_default_config()

    for kr in realms:
        if not kr.krb_realm:
            continue 

        bc = KerberosConfigBindingCollection(name=kr.krb_realm)
        bc.append(
            KerberosConfigBinding(
                name="kdc", value=kr.krb_kdc
            )
        )
        if kr.krb_admin_server: 
            bc.append(
                KerberosConfigBinding(
                    name="admin_server", value=kr.krb_admin_server
                )
            )
        if kr.krb_kpasswd_server:
            bc.append(
                KerberosConfigBinding(
                    name="kpasswd_server", value=kr.krb_kpasswd_server
                )
            )
        bc.append(
            KerberosConfigBinding(
                name="default_domain", value=kr.krb_realm
            )
        )

        kc.add_bindings(['realms'], bc)

        bc = KerberosConfigBindingCollection()
        bc.append(
            KerberosConfigBinding(
                name=kr.krb_realm.lower(), value=kr.krb_realm.upper()
            )
        )
        bc.append(
            KerberosConfigBinding(
                name=".%s" % kr.krb_realm.lower(), value=kr.krb_realm.upper()
            )
        )
        bc.append(
            KerberosConfigBinding(
                name=kr.krb_realm.upper(), value=kr.krb_realm.upper()
            )
        )
        bc.append(
            KerberosConfigBinding(
                name=".%s" % kr.krb_realm.upper(), value=kr.krb_realm.upper()
            )
        )

        kc.add_bindings(['domain_realm'], bc)

    fp = open("/etc/krb5.conf", "w+")
    kc.generate_krb5_conf(stdout=fp)
    fp.close()

if __name__ == '__main__':
    main()
