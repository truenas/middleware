# -*- coding: utf-8 -*-
import os
import sys

from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models

from freenasUI.services.models import (
    ActiveDirectory,
    LDAP,
    NIS,
    NT4
)

class Migration(DataMigration):

    no_dry_run = True

    def forwards(self, orm):
        "Write your forwards methods here."
        # Note: Don't use "from appname.models import ModelName". 
        # Use orm.ModelName to refer to models in this application,
        # and orm['appname.ModelName'] for models in other applications.

 
        try:
            activedirectory = ActiveDirectory.objects.all()[0]

            orm_activedirectory = orm.ActiveDirectory()
            orm_activedirectory.ad_domainname = activedirectory.ad_domainname
            orm_activedirectory.ad_bindname = activedirectory.ad_bindname
            orm_activedirectory.ad_bindpw = activedirectory.ad_bindpw
            orm_activedirectory.ad_netbiosname = activedirectory.ad_netbiosname
            orm_activedirectory.ad_use_keytab = activedirectory.ad_use_keytab
            orm_activedirectory.ad_keytab = activedirectory.ad_keytab
            orm_activedirectory.ad_ssl = activedirectory.ad_ssl
            orm_activedirectory.ad_certfile = activedirectory.ad_certfile
            orm_activedirectory.ad_verbose_logging = activedirectory.ad_verbose_logging
            orm_activedirectory.ad_unix_extensions = activedirectory.ad_unix_extensions
            orm_activedirectory.ad_allow_trusted_doms = activedirectory.ad_allow_trusted_doms
            orm_activedirectory.ad_use_default_domain = activedirectory.ad_use_default_domain
            orm_activedirectory.ad_dcname = activedirectory.ad_dcname
            orm_activedirectory.ad_gcname = activedirectory.ad_gcname
            orm_activedirectory.ad_krbname = activedirectory.ad_krbname
            orm_activedirectory.ad_kpwdname = activedirectory.ad_kpwdname
            orm_activedirectory.ad_timeout = activedirectory.ad_timeout
            orm_activedirectory.ad_dns_timeout = activedirectory.ad_dns_timeout
            orm_activedirectory.save()

        except Exception as e:
            print >> sys.stderr, "FAIL: ActiveDirectory migration: %s" % e
            activedirectory = orm.ActiveDirectory.objects.create()

        try:
            ldap = LDAP.objects.all()[0]

            orm_ldap = orm.LDAP()
            orm_ldap.ldap_hostname = ldap.ldap_hostname
            orm_ldap.ldap_basedn = ldap.ldap_basedn
            orm_ldap.ldap_anonbind = ldap.ldap_anonbind
            orm_ldap.ldap_binddn = ldap.ldap_rootbasedn
            orm_ldap.ldap_bindpw = ldap.ldap_rootbindpw
            orm_ldap.ldap_usersuffix = ldap.ldap_usersuffix
            orm_ldap.ldap_groupsuffix = ldap.ldap_groupsuffix
            orm_ldap.ldap_passwordsuffix = ldap.ldap_passwordsuffix
            orm_ldap.ldap_machinesuffix = ldap.ldap_machinesuffix
            orm_ldap.ldap_ssl = ldap.ldap_ssl

            if os.path.exists(ldap.ldap_tls_cacertfile):
                new_certfile = "/data/ldap_certfile"
                os.rename(ldap.ldap_tls_cacertfile, new_certfile)
                os.chmod(new_certfile, 0400)
                orm_ldap.ldap_certfile = new_certfile

            orm_ldap.save()

        except Exception as e:
            print >> sys.stderr, "FAIL: LDAP migration: %s" % e
            ldap = orm.LDAP.objects.create()


        try:
            nis = NIS.objects.all()[0]

            orm_nis = orm.NIS()
            orm_nis.nis_domain = nis.nis_domain
            orm_nis.nis_servers = nis.nis_servers
            orm_nis.nis_secure_mode = nis.nis_secure_mode
            orm_nis.nis_manycast = nis.nis_manycast
            orm_nis.save()

        except Exception as e:
            print >> sys.stderr, "FAIL: NIS migration: %s" % e
            nis = orm.NIS.objects.create()


        try:
            nt4 = NT4.objects.all()[0]

            orm_nt4 = orm.NT4()
            orm_nt4.nt4_dcname = nt4.nt4_dcname
            orm_nt4.nt4_netbiosname = nt4.nt4_netbiosname
            orm_nt4.nt4_workgroup = nt4.nt4_workgroup
            orm_nt4.nt4_adminname = nt4.nt4_adminname
            orm_nt4.nt4_adminpw = nt4.nt4_adminpw
            orm_nt4.save()

        except Exception as e:
            print >> sys.stderr, "FAIL: NT4 migration: %s" % e
            nt4 = orm.NT4.objects.create()
          



    def backwards(self, orm):
        pass

    models = {
        u'directoryservice.activedirectory': {
            'Meta': {'object_name': 'ActiveDirectory'},
            'ad_allow_trusted_doms': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_bindname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_bindpw': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_certfile': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ad_dcname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_dns_timeout': ('django.db.models.fields.IntegerField', [], {'default': '10'}),
            'ad_domainname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_gcname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_keytab': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'ad_kpwdname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_krbname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_netbiosname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_ssl': ('django.db.models.fields.CharField', [], {'default': "'off'", 'max_length': '120'}),
            'ad_timeout': ('django.db.models.fields.IntegerField', [], {'default': '10'}),
            'ad_unix_extensions': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_use_default_domain': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'ad_use_keytab': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_verbose_logging': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'directoryservice.ldap': {
            'Meta': {'object_name': 'LDAP'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ldap_anonbind': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ldap_basedn': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_binddn': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_bindpw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_certfile': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ldap_groupsuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_hostname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_machinesuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_passwordsuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_ssl': ('django.db.models.fields.CharField', [], {'default': "'off'", 'max_length': '120'}),
            'ldap_usersuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'})
        },
        u'directoryservice.nis': {
            'Meta': {'object_name': 'NIS'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nis_domain': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'nis_manycast': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nis_secure_mode': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nis_servers': ('django.db.models.fields.CharField', [], {'max_length': '8192', 'blank': 'True'})
        },
        u'directoryservice.nt4': {
            'Meta': {'object_name': 'NT4'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nt4_adminname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'nt4_adminpw': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'nt4_dcname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'nt4_netbiosname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'nt4_workgroup': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        }
    }

    complete_apps = ['directoryservice']
    symmetrical = True
