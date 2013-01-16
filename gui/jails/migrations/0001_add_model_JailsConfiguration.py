# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'JailsConfiguration'
        db.create_table('jails_jailsconfiguration', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('jc_path', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('jails', ['JailsConfiguration'])


    def backwards(self, orm):
        # Deleting model 'JailsConfiguration'
        db.delete_table('jails_jailsconfiguration')


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
            'jc_path': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        }
    }

    complete_apps = ['jails']