# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'JailsConfiguration.jc_ipv4_network_start'
        db.add_column(u'jails_jailsconfiguration', 'jc_ipv4_network_start',
                      self.gf('freenasUI.freeadmin.models.fields.Network4Field')(default='', max_length=18, blank=True),
                      keep_default=False)

        # Adding field 'JailsConfiguration.jc_ipv4_network_end'
        db.add_column(u'jails_jailsconfiguration', 'jc_ipv4_network_end',
                      self.gf('freenasUI.freeadmin.models.fields.Network4Field')(default='', max_length=18, blank=True),
                      keep_default=False)

        # Adding field 'JailsConfiguration.jc_ipv6_network_start'
        db.add_column(u'jails_jailsconfiguration', 'jc_ipv6_network_start',
                      self.gf('freenasUI.freeadmin.models.fields.Network6Field')(default='', max_length=43, blank=True),
                      keep_default=False)

        # Adding field 'JailsConfiguration.jc_ipv6_network_end'
        db.add_column(u'jails_jailsconfiguration', 'jc_ipv6_network_end',
                      self.gf('freenasUI.freeadmin.models.fields.Network6Field')(default='', max_length=43, blank=True),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'JailsConfiguration.jc_ipv4_network_start'
        db.delete_column(u'jails_jailsconfiguration', 'jc_ipv4_network_start')

        # Deleting field 'JailsConfiguration.jc_ipv4_network_end'
        db.delete_column(u'jails_jailsconfiguration', 'jc_ipv4_network_end')

        # Deleting field 'JailsConfiguration.jc_ipv6_network_start'
        db.delete_column(u'jails_jailsconfiguration', 'jc_ipv6_network_start')

        # Deleting field 'JailsConfiguration.jc_ipv6_network_end'
        db.delete_column(u'jails_jailsconfiguration', 'jc_ipv6_network_end')


    models = {
        u'jails.jails': {
            'Meta': {'object_name': 'Jails'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jail_alias_bridge_ipv4': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_alias_bridge_ipv6': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_alias_ipv4': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_alias_ipv6': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_autostart': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_bridge_ipv4': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_bridge_ipv6': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_defaultrouter_ipv4': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_defaultrouter_ipv6': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_host': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jail_ipv4': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_ipv6': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_nat': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_status': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jail_type': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jail_vnet': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'})
        },
        u'jails.jailsconfiguration': {
            'Meta': {'object_name': 'JailsConfiguration'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jc_ipv4_network': ('freenasUI.freeadmin.models.fields.Network4Field', [], {'max_length': '18', 'blank': 'True'}),
            'jc_ipv4_network_end': ('freenasUI.freeadmin.models.fields.Network4Field', [], {'max_length': '18', 'blank': 'True'}),
            'jc_ipv4_network_start': ('freenasUI.freeadmin.models.fields.Network4Field', [], {'max_length': '18', 'blank': 'True'}),
            'jc_ipv6_network': ('freenasUI.freeadmin.models.fields.Network6Field', [], {'max_length': '43', 'blank': 'True'}),
            'jc_ipv6_network_end': ('freenasUI.freeadmin.models.fields.Network6Field', [], {'max_length': '43', 'blank': 'True'}),
            'jc_ipv6_network_start': ('freenasUI.freeadmin.models.fields.Network6Field', [], {'max_length': '43', 'blank': 'True'}),
            'jc_path': ('django.db.models.fields.CharField', [], {'max_length': '1024'})
        },
        u'jails.mkdir': {
            'Meta': {'object_name': 'Mkdir'},
            'directory': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jail': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'path': ('django.db.models.fields.CharField', [], {'max_length': '300'})
        },
        u'jails.nullmountpoint': {
            'Meta': {'object_name': 'NullMountPoint'},
            'destination': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jail': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'source': ('django.db.models.fields.CharField', [], {'max_length': '300'})
        }
    }

    complete_apps = ['jails']
