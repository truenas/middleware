# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Changing field 'Transmission.global_seedratio'
        db.alter_column('freenas_transmission', 'global_seedratio', self.gf('django.db.models.fields.DecimalField')(max_digits=6, decimal_places=2))


    def backwards(self, orm):
        
        # Changing field 'Transmission.global_seedratio'
        db.alter_column('freenas_transmission', 'global_seedratio', self.gf('django.db.models.fields.IntegerField')())


    models = {
        'freenas.transmission': {
            'Meta': {'object_name': 'Transmission'},
            'allowed': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'blocklist': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'conf_dir': ('django.db.models.fields.CharField', [], {'default': "'/usr/pbi/transmission-amd64/etc/transmission/home'", 'max_length': '500'}),
            'dht': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'download_dir': ('django.db.models.fields.CharField', [], {'default': "'/usr/pbi/transmission-amd64/etc/transmission/home/Downloads'", 'max_length': '500'}),
            'enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'encryption': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'global_seedratio': ('django.db.models.fields.DecimalField', [], {'default': '2', 'max_digits': '6', 'decimal_places': '2'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'logfile': ('django.db.models.fields.CharField', [], {'max_length': '500', 'blank': 'True'}),
            'lpd': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'peer_port': ('django.db.models.fields.IntegerField', [], {'default': '51413', 'blank': 'True'}),
            'peerlimit_global': ('django.db.models.fields.IntegerField', [], {'default': '240'}),
            'peerlimit_torrent': ('django.db.models.fields.IntegerField', [], {'default': '60'}),
            'portmap': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'rpc_auth': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'rpc_auth_required': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rpc_password': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'rpc_port': ('django.db.models.fields.IntegerField', [], {'default': '9091', 'blank': 'True'}),
            'rpc_username': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'rpc_whitelist': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'rpc_whitelist_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'utp': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'watch_dir': ('django.db.models.fields.CharField', [], {'default': "'/usr/pbi/transmission-amd64/etc/transmission/home/Downloads'", 'max_length': '500'})
        }
    }

    complete_apps = ['freenas']
