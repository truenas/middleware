# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'Plugins'
        db.create_table('plugins_plugins', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('plugin_name', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('plugin_uname', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('plugin_view', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('plugin_icon', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('plugin_enabled', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('plugin_ip', self.gf('django.db.models.fields.IPAddressField')(max_length=15)),
            ('plugin_port', self.gf('django.db.models.fields.IntegerField')(max_length=120)),
            ('plugin_path', self.gf('django.db.models.fields.CharField')(max_length=1024)),
        ))
        db.send_create_signal('plugins', ['Plugins'])


    def backwards(self, orm):
        
        # Deleting model 'Plugins'
        db.delete_table('plugins_plugins')


    models = {
        'plugins.plugins': {
            'Meta': {'object_name': 'Plugins'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'plugin_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'plugin_icon': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_ip': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'plugin_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_path': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'plugin_port': ('django.db.models.fields.IntegerField', [], {'max_length': '120'}),
            'plugin_uname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_view': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        }
    }

    complete_apps = ['plugins']
