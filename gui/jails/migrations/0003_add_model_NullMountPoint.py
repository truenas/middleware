# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'NullMountPoint'
        db.create_table(u'jails_nullmountpoint', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('source', self.gf('django.db.models.fields.CharField')(max_length=300)),
            ('destination', self.gf('django.db.models.fields.CharField')(max_length=300)),
        ))
        db.send_create_signal(u'jails', ['NullMountPoint'])


    def backwards(self, orm):
        # Deleting model 'NullMountPoint'
        db.delete_table(u'jails_nullmountpoint')


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
            'jail_status': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jail_type': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        u'jails.jailsconfiguration': {
            'Meta': {'object_name': 'JailsConfiguration'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jc_ipv4_network': ('django.db.models.fields.CharField', [], {'default': "'192.168.99.0/24'", 'max_length': '120', 'blank': 'True'}),
            'jc_ipv6_network': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'jc_path': ('django.db.models.fields.CharField', [], {'max_length': '1024'})
        },
        u'jails.nullmountpoint': {
            'Meta': {'object_name': 'NullMountPoint'},
            'destination': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source': ('django.db.models.fields.CharField', [], {'max_length': '300'})
        }
    }

    complete_apps = ['jails']