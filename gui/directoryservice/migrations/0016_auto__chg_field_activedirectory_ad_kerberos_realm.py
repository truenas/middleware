# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):

        # Changing field 'ActiveDirectory.ad_kerberos_realm'
        db.alter_column(u'directoryservice_activedirectory', 'ad_kerberos_realm_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['directoryservice.KerberosRealm'], null=True, on_delete=models.SET_NULL))

    def backwards(self, orm):

        # Changing field 'ActiveDirectory.ad_kerberos_realm'
        db.alter_column(u'directoryservice_activedirectory', 'ad_kerberos_realm_id', self.gf('django.db.models.fields.related.ForeignKey')(default='', to=orm['directoryservice.KerberosRealm'], on_delete=models.DO_NOTHING))

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
            'ad_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_gcname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_idmap_backend': ('django.db.models.fields.CharField', [], {'default': "'rid'", 'max_length': '120'}),
            'ad_kerberos_keytab': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['directoryservice.KerberosKeytab']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'ad_kerberos_realm': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['directoryservice.KerberosRealm']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'ad_netbiosname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_ssl': ('django.db.models.fields.CharField', [], {'default': "'off'", 'max_length': '120'}),
            'ad_timeout': ('django.db.models.fields.IntegerField', [], {'default': '10'}),
            'ad_unix_extensions': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_use_default_domain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_use_keytab': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_verbose_logging': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'directoryservice.idmap_ad': {
            'Meta': {'object_name': 'idmap_ad'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_ad_range_high': ('django.db.models.fields.IntegerField', [], {'default': '90000000'}),
            'idmap_ad_range_low': ('django.db.models.fields.IntegerField', [], {'default': '10000'}),
            'idmap_ad_schema_mode': ('django.db.models.fields.CharField', [], {'default': "'rfc2307'", 'max_length': '120'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'})
        },
        u'directoryservice.idmap_autorid': {
            'Meta': {'object_name': 'idmap_autorid'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_autorid_ignore_builtin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'idmap_autorid_range_high': ('django.db.models.fields.IntegerField', [], {'default': '90000000'}),
            'idmap_autorid_range_low': ('django.db.models.fields.IntegerField', [], {'default': '10000'}),
            'idmap_autorid_rangesize': ('django.db.models.fields.IntegerField', [], {'default': '100000'}),
            'idmap_autorid_readonly': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'})
        },
        u'directoryservice.idmap_hash': {
            'Meta': {'object_name': 'idmap_hash'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'idmap_hash_range_high': ('django.db.models.fields.IntegerField', [], {'default': '100000000'}),
            'idmap_hash_range_low': ('django.db.models.fields.IntegerField', [], {'default': '90000001'}),
            'idmap_hash_range_name_map': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255'})
        },
        u'directoryservice.idmap_ldap': {
            'Meta': {'object_name': 'idmap_ldap'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'idmap_ldap_ldap_base_dn': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'idmap_ldap_ldap_url': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'idmap_ldap_ldap_user_dn': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'idmap_ldap_range_high': ('django.db.models.fields.IntegerField', [], {'default': '90000000'}),
            'idmap_ldap_range_low': ('django.db.models.fields.IntegerField', [], {'default': '10000'})
        },
        u'directoryservice.idmap_nss': {
            'Meta': {'object_name': 'idmap_nss'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'idmap_nss_range_high': ('django.db.models.fields.IntegerField', [], {'default': '90000000'}),
            'idmap_nss_range_low': ('django.db.models.fields.IntegerField', [], {'default': '10000'})
        },
        u'directoryservice.idmap_rfc2307': {
            'Meta': {'object_name': 'idmap_rfc2307'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'idmap_rfc2307_bind_path_group': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'idmap_rfc2307_bind_path_user': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'idmap_rfc2307_cn_realm': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'idmap_rfc2307_ldap_domain': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'idmap_rfc2307_ldap_realm': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'idmap_rfc2307_ldap_server': ('django.db.models.fields.CharField', [], {'default': "'ad'", 'max_length': '120'}),
            'idmap_rfc2307_ldap_url': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'idmap_rfc2307_ldap_user_dn': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'idmap_rfc2307_range_high': ('django.db.models.fields.IntegerField', [], {'default': '90000000'}),
            'idmap_rfc2307_range_low': ('django.db.models.fields.IntegerField', [], {'default': '10000'}),
            'idmap_rfc2307_user_cn': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'directoryservice.idmap_rid': {
            'Meta': {'object_name': 'idmap_rid'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'idmap_rid_range_high': ('django.db.models.fields.IntegerField', [], {'default': '90000000'}),
            'idmap_rid_range_low': ('django.db.models.fields.IntegerField', [], {'default': '10000'})
        },
        u'directoryservice.idmap_tdb': {
            'Meta': {'object_name': 'idmap_tdb'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'idmap_tdb_range_high': ('django.db.models.fields.IntegerField', [], {'default': '100000000'}),
            'idmap_tdb_range_low': ('django.db.models.fields.IntegerField', [], {'default': '90000001'})
        },
        u'directoryservice.idmap_tdb2': {
            'Meta': {'object_name': 'idmap_tdb2'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'idmap_tdb2_range_high': ('django.db.models.fields.IntegerField', [], {'default': '100000000'}),
            'idmap_tdb2_range_low': ('django.db.models.fields.IntegerField', [], {'default': '90000001'}),
            'idmap_tdb2_script': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255'})
        },
        u'directoryservice.kerberoskeytab': {
            'Meta': {'object_name': 'KerberosKeytab'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'keytab_file': ('django.db.models.fields.TextField', [], {}),
            'keytab_principal': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        u'directoryservice.kerberosrealm': {
            'Meta': {'object_name': 'KerberosRealm'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'krb_admin_server': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'krb_kdc': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'krb_kpasswd_server': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'krb_realm': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        u'directoryservice.ldap': {
            'Meta': {'object_name': 'LDAP'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ldap_anonbind': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ldap_basedn': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_binddn': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_bindpw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_certfile': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ldap_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ldap_groupsuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_hostname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_idmap_backend': ('django.db.models.fields.CharField', [], {'default': "'ldap'", 'max_length': '120'}),
            'ldap_kerberos_keytab': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['directoryservice.KerberosKeytab']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'ldap_kerberos_realm': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['directoryservice.KerberosRealm']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'ldap_machinesuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_passwordsuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_ssl': ('django.db.models.fields.CharField', [], {'default': "'off'", 'max_length': '120'}),
            'ldap_use_default_domain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ldap_usersuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'})
        },
        u'directoryservice.nis': {
            'Meta': {'object_name': 'NIS'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nis_domain': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'nis_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
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
            'nt4_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nt4_idmap_backend': ('django.db.models.fields.CharField', [], {'default': "'rid'", 'max_length': '120'}),
            'nt4_netbiosname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'nt4_use_default_domain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nt4_workgroup': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        }
    }

    complete_apps = ['directoryservice']