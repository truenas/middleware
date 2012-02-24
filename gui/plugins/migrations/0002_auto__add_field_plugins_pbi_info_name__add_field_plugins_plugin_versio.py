# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'Plugins.pbi_info_name'
        db.add_column('plugins_plugins', 'pbi_info_name', self.gf('django.db.models.fields.CharField')(default='', max_length=120), keep_default=False)

        # Adding field 'Plugins.plugin_version'
        db.add_column('plugins_plugins', 'plugin_version', self.gf('django.db.models.fields.CharField')(default='', max_length=120), keep_default=False)

        # Adding field 'Plugins.plugin_arch'
        db.add_column('plugins_plugins', 'plugin_arch', self.gf('django.db.models.fields.CharField')(default='', max_length=120), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'Plugins.pbi_info_name'
        db.delete_column('plugins_plugins', 'pbi_info_name')

        # Deleting field 'Plugins.plugin_version'
        db.delete_column('plugins_plugins', 'plugin_version')

        # Deleting field 'Plugins.plugin_arch'
        db.delete_column('plugins_plugins', 'plugin_arch')


    models = {
        'plugins.plugins': {
            'Meta': {'object_name': 'Plugins'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'pbi_info_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_arch': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'plugin_icon': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_ip': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'plugin_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_path': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'plugin_port': ('django.db.models.fields.IntegerField', [], {'max_length': '120'}),
            'plugin_uname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_version': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_view': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        }
    }

    complete_apps = ['plugins']
