# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Deleting field 'Plugins.pbi_info_name'
        db.delete_column('plugins_plugins', 'pbi_info_name')

        # Adding field 'Plugins.plugin_pbiname'
        db.add_column('plugins_plugins', 'plugin_pbiname', self.gf('django.db.models.fields.CharField')(default='', max_length=120), keep_default=False)


    def backwards(self, orm):
        
        # User chose to not deal with backwards NULL issues for 'Plugins.pbi_info_name'
        raise RuntimeError("Cannot reverse this migration. 'Plugins.pbi_info_name' and its values cannot be restored.")

        # Deleting field 'Plugins.plugin_pbiname'
        db.delete_column('plugins_plugins', 'plugin_pbiname')


    models = {
        'plugins.plugins': {
            'Meta': {'object_name': 'Plugins'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'plugin_arch': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'plugin_icon': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_ip': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'plugin_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_path': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'plugin_pbiname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_port': ('django.db.models.fields.IntegerField', [], {'max_length': '120'}),
            'plugin_uname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_version': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_view': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        }
    }

    complete_apps = ['plugins']
