# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Firefly'
        db.create_table('freenas_firefly', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('enable', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('port', self.gf('django.db.models.fields.IntegerField')(default=3689)),
            ('servername', self.gf('django.db.models.fields.CharField')(default='Firefly %v on %h', max_length=500, blank=True)),
            ('extensions', self.gf('django.db.models.fields.CharField')(default='.mp3,.m4a,.m4p,.ogg,.flac', max_length=500, blank=True)),
            ('logfile', self.gf('django.db.models.fields.CharField')(default='/var/log/mt-daapd.log', max_length=500)),
            ('process_playlists', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('process_itunes', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('process_m3u', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal('freenas', ['Firefly'])

    def backwards(self, orm):
        # Deleting model 'Firefly'
        db.delete_table('freenas_firefly')

    models = {
        'freenas.firefly': {
            'Meta': {'object_name': 'Firefly'},
            'enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'extensions': ('django.db.models.fields.CharField', [], {'default': "'.mp3,.m4a,.m4p,.ogg,.flac'", 'max_length': '500', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'logfile': ('django.db.models.fields.CharField', [], {'default': "'/var/log/mt-daapd.log'", 'max_length': '500'}),
            'port': ('django.db.models.fields.IntegerField', [], {'default': '3689'}),
            'process_itunes': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'process_m3u': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'process_playlists': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'servername': ('django.db.models.fields.CharField', [], {'default': "'Firefly %v on %h'", 'max_length': '500', 'blank': 'True'})
        }
    }

    complete_apps = ['freenas']