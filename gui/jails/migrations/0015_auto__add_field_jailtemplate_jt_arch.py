# -*- coding: utf-8 -*-
import datetime
import platform
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        arch = platform.architecture()
        if arch[0] == '64bit':
            arch = 'x64'
        else:
            arch = 'x86'

        # Adding field 'JailTemplate.jt_arch'
        db.add_column(u'jails_jailtemplate', 'jt_arch',
                      self.gf('django.db.models.fields.CharField')(default=arch, max_length=120),
                      keep_default=False)

        db.execute("update jails_jailtemplate set jt_arch = 'x86' " \
            "where jt_name in ('centos-6.4', 'debian-7.1.0'," \
            "'gentoo-20130820', 'pluginjail-x86', 'portjail-x86'," \
            "'standard-x86', 'suse-12.3', 'ubuntu-13.04')")

    def backwards(self, orm):
        # Deleting field 'JailTemplate.jt_arch'
        db.delete_column(u'jails_jailtemplate', 'jt_arch')


    models = {
        u'jails.jails': {
            'Meta': {'object_name': 'Jails'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jail_alias_bridge_ipv4': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_alias_bridge_ipv6': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_alias_ipv4': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_alias_ipv6': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_autostart': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'max_length': '120'}),
            'jail_bridge_ipv4': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_bridge_ipv6': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_defaultrouter_ipv4': ('django.db.models.fields.IPAddressField', [], {'max_length': '15', 'null': 'True', 'blank': 'True'}),
            'jail_defaultrouter_ipv6': ('django.db.models.fields.GenericIPAddressField', [], {'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'jail_host': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jail_ipv4': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_ipv6': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_mac': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_nat': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'jail_status': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jail_type': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jail_vnet': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'max_length': '120'})
        },
        u'jails.jailsconfiguration': {
            'Meta': {'object_name': 'JailsConfiguration'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jc_collectionurl': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'jc_ipv4_network': ('freenasUI.freeadmin.models.fields.Network4Field', [], {'max_length': '18', 'blank': 'True'}),
            'jc_ipv4_network_end': ('freenasUI.freeadmin.models.fields.Network4Field', [], {'max_length': '18', 'blank': 'True'}),
            'jc_ipv4_network_start': ('freenasUI.freeadmin.models.fields.Network4Field', [], {'max_length': '18', 'blank': 'True'}),
            'jc_ipv6_network': ('freenasUI.freeadmin.models.fields.Network6Field', [], {'max_length': '43', 'blank': 'True'}),
            'jc_ipv6_network_end': ('freenasUI.freeadmin.models.fields.Network6Field', [], {'max_length': '43', 'blank': 'True'}),
            'jc_ipv6_network_start': ('freenasUI.freeadmin.models.fields.Network6Field', [], {'max_length': '43', 'blank': 'True'}),
            'jc_path': ('django.db.models.fields.CharField', [], {'max_length': '1024'})
        },
        u'jails.jailtemplate': {
            'Meta': {'object_name': 'JailTemplate'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jt_arch': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jt_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'jt_os': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jt_url': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        u'jails.nullmountpoint': {
            'Meta': {'object_name': 'NullMountPoint'},
            'destination': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jail': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'readonly': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'source': ('django.db.models.fields.CharField', [], {'max_length': '300'})
        }
    }

    complete_apps = ['jails']
