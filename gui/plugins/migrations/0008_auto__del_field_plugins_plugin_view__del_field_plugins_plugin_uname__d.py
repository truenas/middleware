# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Deleting field 'Plugins.plugin_view'
        db.delete_column('plugins_plugins', 'plugin_view')

        # Deleting field 'Plugins.plugin_uname'
        db.delete_column('plugins_plugins', 'plugin_uname')

        # Deleting field 'Plugins.plugin_icon'
        db.delete_column('plugins_plugins', 'plugin_icon')


    def backwards(self, orm):
        
        # User chose to not deal with backwards NULL issues for 'Plugins.plugin_view'
        raise RuntimeError("Cannot reverse this migration. 'Plugins.plugin_view' and its values cannot be restored.")

        # User chose to not deal with backwards NULL issues for 'Plugins.plugin_uname'
        raise RuntimeError("Cannot reverse this migration. 'Plugins.plugin_uname' and its values cannot be restored.")

        # User chose to not deal with backwards NULL issues for 'Plugins.plugin_icon'
        raise RuntimeError("Cannot reverse this migration. 'Plugins.plugin_icon' and its values cannot be restored.")


    models = {
        'plugins.nullmountpoint': {
            'Meta': {'object_name': 'NullMountPoint'},
            'destination': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source': ('django.db.models.fields.CharField', [], {'max_length': '300'})
        },
        'plugins.plugins': {
            'Meta': {'object_name': 'Plugins'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'plugin_arch': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'plugin_ip': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'plugin_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_path': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'plugin_pbiname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_port': ('django.db.models.fields.IntegerField', [], {'max_length': '120'}),
            'plugin_secret': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['services.RPCToken']"}),
            'plugin_version': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'services.rpctoken': {
            'Meta': {'object_name': 'RPCToken'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'secret': ('django.db.models.fields.CharField', [], {'max_length': '1024'})
        }
    }

    complete_apps = ['plugins']
