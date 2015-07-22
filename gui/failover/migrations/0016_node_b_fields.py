# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models

from freenasUI.middleware.notifier import notifier


class Migration(DataMigration):

    depends_on = (
        ('directoryservice', '0045_auto__add_field_activedirectory_ad_netbiosname_b'),
        ('network', '0018_auto__add_field_alias_alias_vip__add_field_alias_alias_v4address_b__ad'),
        ('system', '0096_auto__add_field_systemdataset_sys_uuid_b'),
    )

    def forwards(self, orm):
        node = notifier().failover_node()
        if node == 'B':
            for ad in orm['directoryservice.ActiveDirectory'].objects.all():
                if ad.ad_netbiosname:
                    ad.ad_netbiosname_b = ad.ad_netbiosname
                    ad.save()

            for iface in orm['network.Interfaces'].objects.all():
                if iface.int_ipv4address:
                    iface.int_ipv4address_b = iface.int_ipv4address
                    iface.save()

            for obj in orm['network.GlobalConfiguration'].objects.all():
                if obj.gc_hostname:
                    obj.gc_hostname_b = obj.gc_hostname
                    obj.save()

            for sys in orm['system.SystemDataset'].objects.all():
                if sys.sys_uuid:
                    sys.sys_uuid_b = sys.sys_uuid
                    sys.save()

            for alias in orm['network.Alias'].objects.all():
                if alias.alias_v4address:
                    alias.alias_v4address_b = alias.alias_v4address
                    alias.save()
                if alias.alias_v6address:
                    alias.alias_v6address_b = alias.alias_v6address
                    alias.save()

            try:
                open('/data/sync_fields_to_peer', 'w').close()
            except:
                pass
        elif node == 'A':
            try:
                open('/data/sync_fields_from_peer', 'w').close()
            except:
                pass


    def backwards(self, orm):
        "Write your backwards methods here."

    models = {
        u'directoryservice.activedirectory': {
            'Meta': {'object_name': 'ActiveDirectory'},
            'ad_allow_trusted_doms': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_bindname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_bindpw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_certificate': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['system.CertificateAuthority']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'ad_dcname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ad_dns_timeout': ('django.db.models.fields.IntegerField', [], {'default': '10'}),
            'ad_domainname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_gcname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ad_idmap_backend': ('django.db.models.fields.CharField', [], {'default': "'rid'", 'max_length': '120'}),
            'ad_kerberos_keytab': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['directoryservice.KerberosKeytab']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'ad_kerberos_realm': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['directoryservice.KerberosRealm']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'ad_ldap_sasl_wrapping': ('django.db.models.fields.CharField', [], {'default': "'plain'", 'max_length': '120'}),
            'ad_netbiosname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_netbiosname_b': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ad_nss_info': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ad_site': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ad_ssl': ('django.db.models.fields.CharField', [], {'default': "'off'", 'max_length': '120'}),
            'ad_timeout': ('django.db.models.fields.IntegerField', [], {'default': '10'}),
            'ad_unix_extensions': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_use_default_domain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
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
        u'directoryservice.idmap_adex': {
            'Meta': {'object_name': 'idmap_adex'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_adex_range_high': ('django.db.models.fields.IntegerField', [], {'default': '90000000'}),
            'idmap_adex_range_low': ('django.db.models.fields.IntegerField', [], {'default': '10000'}),
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
            'idmap_ldap_certificate': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['system.CertificateAuthority']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'idmap_ldap_ldap_base_dn': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'idmap_ldap_ldap_url': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'idmap_ldap_ldap_user_dn': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'idmap_ldap_range_high': ('django.db.models.fields.IntegerField', [], {'default': '90000000'}),
            'idmap_ldap_range_low': ('django.db.models.fields.IntegerField', [], {'default': '10000'}),
            'idmap_ldap_ssl': ('django.db.models.fields.CharField', [], {'default': "'off'", 'max_length': '120'})
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
            'idmap_rfc2307_certificate': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['system.CertificateAuthority']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'idmap_rfc2307_cn_realm': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'idmap_rfc2307_ldap_domain': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'idmap_rfc2307_ldap_realm': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'idmap_rfc2307_ldap_server': ('django.db.models.fields.CharField', [], {'default': "'ad'", 'max_length': '120'}),
            'idmap_rfc2307_ldap_url': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'idmap_rfc2307_ldap_user_dn': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'idmap_rfc2307_range_high': ('django.db.models.fields.IntegerField', [], {'default': '90000000'}),
            'idmap_rfc2307_range_low': ('django.db.models.fields.IntegerField', [], {'default': '10000'}),
            'idmap_rfc2307_ssl': ('django.db.models.fields.CharField', [], {'default': "'off'", 'max_length': '120'}),
            'idmap_rfc2307_user_cn': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'directoryservice.idmap_rid': {
            'Meta': {'object_name': 'idmap_rid'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'idmap_rid_range_high': ('django.db.models.fields.IntegerField', [], {'default': '90000000'}),
            'idmap_rid_range_low': ('django.db.models.fields.IntegerField', [], {'default': '20000'})
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
            'keytab_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'keytab_principal': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        u'directoryservice.kerberosrealm': {
            'Meta': {'object_name': 'KerberosRealm'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'krb_admin_server': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'krb_kdc': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'krb_kpasswd_server': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'krb_realm': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'})
        },
        u'directoryservice.kerberossettings': {
            'Meta': {'object_name': 'KerberosSettings'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ks_appdefaults_aux': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ks_libdefaults_aux': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        u'directoryservice.ldap': {
            'Meta': {'object_name': 'LDAP'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ldap_anonbind': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ldap_auxiliary_parameters': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ldap_basedn': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_binddn': ('django.db.models.fields.CharField', [], {'max_length': '256', 'blank': 'True'}),
            'ldap_bindpw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_certificate': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['system.CertificateAuthority']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'ldap_dns_timeout': ('django.db.models.fields.IntegerField', [], {'default': '10'}),
            'ldap_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ldap_groupsuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_has_samba_schema': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ldap_hostname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_idmap_backend': ('django.db.models.fields.CharField', [], {'default': "'ldap'", 'max_length': '120'}),
            'ldap_kerberos_keytab': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['directoryservice.KerberosKeytab']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'ldap_kerberos_realm': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['directoryservice.KerberosRealm']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'ldap_machinesuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_passwordsuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_schema': ('django.db.models.fields.CharField', [], {'default': "'rfc2307'", 'max_length': '120'}),
            'ldap_ssl': ('django.db.models.fields.CharField', [], {'default': "'off'", 'max_length': '120'}),
            'ldap_sudosuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_timeout': ('django.db.models.fields.IntegerField', [], {'default': '10'}),
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
        },
        u'failover.failover': {
            'Meta': {'object_name': 'Failover', 'db_table': "'system_failover'"},
            'disabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'master': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'timeout': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'network.alias': {
            'Meta': {'object_name': 'Alias'},
            'alias_interface': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['network.Interfaces']"}),
            'alias_v4address': ('freenasUI.contrib.IPAddressField.IP4AddressField', [], {'default': "''", 'blank': 'True'}),
            'alias_v4netmaskbit': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '3', 'blank': 'True'}),
            'alias_v6address': ('freenasUI.contrib.IPAddressField.IP6AddressField', [], {'default': "''", 'blank': 'True'}),
            'alias_v6netmaskbit': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '3', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'network.globalconfiguration': {
            'Meta': {'object_name': 'GlobalConfiguration'},
            'gc_domain': ('django.db.models.fields.CharField', [], {'default': "'local'", 'max_length': '120'}),
            'gc_hostname': ('django.db.models.fields.CharField', [], {'default': "'nas'", 'max_length': '120'}),
            'gc_hostname_b': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'gc_hosts': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'gc_httpproxy': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'gc_ipv4gateway': ('freenasUI.contrib.IPAddressField.IP4AddressField', [], {'default': "''", 'blank': 'True'}),
            'gc_ipv6gateway': ('freenasUI.contrib.IPAddressField.IP6AddressField', [], {'default': "''", 'blank': 'True'}),
            'gc_nameserver1': ('freenasUI.contrib.IPAddressField.IPAddressField', [], {'default': "''", 'blank': 'True'}),
            'gc_nameserver2': ('freenasUI.contrib.IPAddressField.IPAddressField', [], {'default': "''", 'blank': 'True'}),
            'gc_nameserver3': ('freenasUI.contrib.IPAddressField.IPAddressField', [], {'default': "''", 'blank': 'True'}),
            'gc_netwait_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'gc_netwait_ip': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'network.interfaces': {
            'Meta': {'ordering': "['int_interface']", 'object_name': 'Interfaces'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'int_carp': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'int_critical': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'int_dhcp': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'int_group': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'int_interface': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
            'int_ipv4address': ('freenasUI.contrib.IPAddressField.IPAddressField', [], {'default': "''", 'blank': 'True'}),
            'int_ipv4address_b': ('freenasUI.contrib.IPAddressField.IPAddressField', [], {'default': "''", 'blank': 'True'}),
            'int_ipv6address': ('freenasUI.contrib.IPAddressField.IPAddressField', [], {'default': "''", 'blank': 'True'}),
            'int_ipv6auto': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'int_name': ('django.db.models.fields.CharField', [], {'max_length': "'120'"}),
            'int_options': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'int_pass': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'int_v4netmaskbit': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '3', 'blank': 'True'}),
            'int_v6netmaskbit': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '4', 'blank': 'True'}),
            'int_vhid': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'int_vip': ('freenasUI.contrib.IPAddressField.IPAddressField', [], {'null': 'True', 'blank': 'True'})
        },
        u'network.lagginterface': {
            'Meta': {'ordering': "['lagg_interface']", 'object_name': 'LAGGInterface'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lagg_interface': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['network.Interfaces']", 'unique': 'True'}),
            'lagg_protocol': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        u'network.lagginterfacemembers': {
            'Meta': {'ordering': "['lagg_interfacegroup']", 'object_name': 'LAGGInterfaceMembers'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lagg_deviceoptions': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'lagg_interfacegroup': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['network.LAGGInterface']"}),
            'lagg_ordernum': ('django.db.models.fields.IntegerField', [], {}),
            'lagg_physnic': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'})
        },
        u'network.staticroute': {
            'Meta': {'ordering': "['sr_destination', 'sr_gateway']", 'object_name': 'StaticRoute'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'sr_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'sr_destination': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'sr_gateway': ('freenasUI.contrib.IPAddressField.IP4AddressField', [], {'max_length': '120'})
        },
        u'network.vlan': {
            'Meta': {'ordering': "['vlan_vint']", 'object_name': 'VLAN'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'vlan_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'vlan_pint': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
            'vlan_tag': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'vlan_vint': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        u'system.advanced': {
            'Meta': {'object_name': 'Advanced'},
            'adv_advancedmode': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_anonstats': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'adv_anonstats_token': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'adv_autotune': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_boot_scrub': ('django.db.models.fields.IntegerField', [], {'default': '35'}),
            'adv_consolemenu': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_consolemsg': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'adv_consolescreensaver': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_debugkernel': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_motd': ('django.db.models.fields.TextField', [], {'default': "'Welcome'", 'max_length': '1024'}),
            'adv_periodic_notifyuser': ('freenasUI.freeadmin.models.fields.UserField', [], {'default': "'root'", 'max_length': '120'}),
            'adv_powerdaemon': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_serialconsole': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_serialport': ('django.db.models.fields.CharField', [], {'default': "'0x2f8'", 'max_length': '120'}),
            'adv_serialspeed': ('django.db.models.fields.CharField', [], {'default': "'9600'", 'max_length': '120'}),
            'adv_swapondrive': ('django.db.models.fields.IntegerField', [], {'default': '2'}),
            'adv_traceback': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'adv_uploadcrash': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'system.alert': {
            'Meta': {'object_name': 'Alert'},
            'dismiss': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'message_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'})
        },
        u'system.backup': {
            'Meta': {'object_name': 'Backup'},
            'bak_acknowledged': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bak_destination': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'bak_failed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bak_finished': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bak_finished_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'bak_started_at': ('django.db.models.fields.DateTimeField', [], {}),
            'bak_status': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'bak_worker_pid': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'system.certificate': {
            'Meta': {'object_name': 'Certificate'},
            'cert_CSR': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_certificate': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_city': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_common': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_country': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_digest_algorithm': ('django.db.models.fields.CharField', [], {'default': "'SHA256'", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_email': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_key_length': ('django.db.models.fields.IntegerField', [], {'default': '2048', 'null': 'True', 'blank': 'True'}),
            'cert_lifetime': ('django.db.models.fields.IntegerField', [], {'default': '3650', 'null': 'True', 'blank': 'True'}),
            'cert_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'cert_organization': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_privatekey': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_serial': ('django.db.models.fields.IntegerField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_signedby': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['system.CertificateAuthority']", 'null': 'True', 'blank': 'True'}),
            'cert_state': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_type': ('django.db.models.fields.IntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'system.certificateauthority': {
            'Meta': {'object_name': 'CertificateAuthority'},
            'cert_CSR': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_certificate': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_city': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_common': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_country': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_digest_algorithm': ('django.db.models.fields.CharField', [], {'default': "'SHA256'", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_email': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_key_length': ('django.db.models.fields.IntegerField', [], {'default': '2048', 'null': 'True', 'blank': 'True'}),
            'cert_lifetime': ('django.db.models.fields.IntegerField', [], {'default': '3650', 'null': 'True', 'blank': 'True'}),
            'cert_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'cert_organization': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_privatekey': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_serial': ('django.db.models.fields.IntegerField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_signedby': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['system.CertificateAuthority']", 'null': 'True', 'blank': 'True'}),
            'cert_state': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_type': ('django.db.models.fields.IntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'system.email': {
            'Meta': {'object_name': 'Email'},
            'em_fromemail': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '120'}),
            'em_outgoingserver': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'em_pass': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'em_port': ('django.db.models.fields.IntegerField', [], {'default': '25'}),
            'em_security': ('django.db.models.fields.CharField', [], {'default': "'plain'", 'max_length': '120'}),
            'em_smtp': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'em_user': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'system.ntpserver': {
            'Meta': {'ordering': "['ntp_address']", 'object_name': 'NTPServer'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ntp_address': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ntp_burst': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ntp_iburst': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'ntp_maxpoll': ('django.db.models.fields.IntegerField', [], {'default': '10'}),
            'ntp_minpoll': ('django.db.models.fields.IntegerField', [], {'default': '6'}),
            'ntp_prefer': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'system.registration': {
            'Meta': {'object_name': 'Registration'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'reg_address': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'reg_cellphone': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'reg_city': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'reg_company': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'reg_email': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'reg_firstname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'reg_homephone': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'reg_lastname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'reg_state': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'reg_workphone': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'reg_zip': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'})
        },
        u'system.settings': {
            'Meta': {'object_name': 'Settings'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'stg_guiaddress': ('django.db.models.fields.CharField', [], {'default': "'0.0.0.0'", 'max_length': '120', 'blank': 'True'}),
            'stg_guicertificate': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['system.Certificate']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'stg_guihttpsport': ('django.db.models.fields.IntegerField', [], {'default': '443'}),
            'stg_guihttpsredirect': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'stg_guiport': ('django.db.models.fields.IntegerField', [], {'default': '80'}),
            'stg_guiprotocol': ('django.db.models.fields.CharField', [], {'default': "'http'", 'max_length': '120'}),
            'stg_guiv6address': ('django.db.models.fields.CharField', [], {'default': "'::'", 'max_length': '120', 'blank': 'True'}),
            'stg_kbdmap': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'stg_language': ('django.db.models.fields.CharField', [], {'default': "'en'", 'max_length': '120'}),
            'stg_pwenc_check': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'stg_syslogserver': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '120', 'blank': 'True'}),
            'stg_timezone': ('django.db.models.fields.CharField', [], {'default': "'America/Los_Angeles'", 'max_length': '120'}),
            'stg_wizardshown': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'system.systemdataset': {
            'Meta': {'object_name': 'SystemDataset'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'sys_pool': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'sys_rrd_usedataset': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'sys_syslog_usedataset': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'sys_uuid': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'sys_uuid_b': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True', 'blank': 'True'})
        },
        u'system.tunable': {
            'Meta': {'ordering': "['tun_var']", 'object_name': 'Tunable'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'tun_comment': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'tun_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'tun_type': ('django.db.models.fields.CharField', [], {'default': "'loader'", 'max_length': '20'}),
            'tun_value': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'tun_var': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '50'})
        },
        u'system.update': {
            'Meta': {'object_name': 'Update'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'upd_autocheck': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'upd_train': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'})
        }
    }

    complete_apps = ['network', 'system', 'directoryservice', 'failover']
    symmetrical = True
