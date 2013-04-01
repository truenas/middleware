# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'JailsConfiguration.jc_ipv4_network'
        db.add_column('jails_jailsconfiguration', 'jc_ipv4_network',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=120),
                      keep_default=False)

        # Adding field 'JailsConfiguration.jc_ipv6_network'
        db.add_column('jails_jailsconfiguration', 'jc_ipv6_network',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=120),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'JailsConfiguration.jc_ipv4_network'
        db.delete_column('jails_jailsconfiguration', 'jc_ipv4_network')

        # Deleting field 'JailsConfiguration.jc_ipv6_network'
        db.delete_column('jails_jailsconfiguration', 'jc_ipv6_network')


    models = {
        'jails.jails': {
            'Meta': {'object_name': 'Jails'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jail_autostart': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jail_host': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jail_ip': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'jail_status': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jail_type': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'jails.jailsconfiguration': {
            'Meta': {'object_name': 'JailsConfiguration'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jc_ipv4_network': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jc_ipv6_network': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jc_path': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        }
    }

    complete_apps = ['jails']