# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'Transmission'
        db.create_table('freenas_transmission', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('enable', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('watch_dir', self.gf('django.db.models.fields.CharField')(max_length=500, blank=True)),
            ('conf_dir', self.gf('django.db.models.fields.CharField')(max_length=500, blank=True)),
            ('download_dir', self.gf('django.db.models.fields.CharField')(max_length=500, blank=True)),
            ('allowed', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('blocklist', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('logfile', self.gf('django.db.models.fields.CharField')(max_length=500, blank=True)),
            ('rpc_port', self.gf('django.db.models.fields.IntegerField')(default=9091, blank=True)),
            ('rpc_auth', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('rpc_username', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('rpc_password', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('rpc_whitelist', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('dht', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('lpd', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('utp', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('peer_port', self.gf('django.db.models.fields.IntegerField')(default=51413, blank=True)),
            ('portmap', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('peerlimit_global', self.gf('django.db.models.fields.IntegerField')(default=240)),
            ('peerlimit_torrent', self.gf('django.db.models.fields.IntegerField')(default=60)),
            ('encryption_required', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('encryption_preferred', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('encryption_tolerated', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('global_seedratio', self.gf('django.db.models.fields.IntegerField')(default=2)),
        ))
        db.send_create_signal('freenas', ['Transmission'])


    def backwards(self, orm):
        
        # Deleting model 'Transmission'
        db.delete_table('freenas_transmission')


    models = {
        'freenas.transmission': {
            'Meta': {'object_name': 'Transmission'},
            'allowed': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'blocklist': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'conf_dir': ('django.db.models.fields.CharField', [], {'max_length': '500', 'blank': 'True'}),
            'dht': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'download_dir': ('django.db.models.fields.CharField', [], {'max_length': '500', 'blank': 'True'}),
            'enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'encryption_preferred': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'encryption_required': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'encryption_tolerated': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'global_seedratio': ('django.db.models.fields.IntegerField', [], {'default': '2'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'logfile': ('django.db.models.fields.CharField', [], {'max_length': '500', 'blank': 'True'}),
            'lpd': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'peer_port': ('django.db.models.fields.IntegerField', [], {'default': '51413', 'blank': 'True'}),
            'peerlimit_global': ('django.db.models.fields.IntegerField', [], {'default': '240'}),
            'peerlimit_torrent': ('django.db.models.fields.IntegerField', [], {'default': '60'}),
            'portmap': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'rpc_auth': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'rpc_password': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'rpc_port': ('django.db.models.fields.IntegerField', [], {'default': '9091', 'blank': 'True'}),
            'rpc_username': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'rpc_whitelist': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'utp': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'watch_dir': ('django.db.models.fields.CharField', [], {'max_length': '500', 'blank': 'True'})
        }
    }

    complete_apps = ['freenas']
