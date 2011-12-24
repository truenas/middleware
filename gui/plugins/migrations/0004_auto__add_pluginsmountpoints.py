# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'PluginsMountPoints'
        db.create_table('plugins_pluginsmountpoints', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('pm_plugin', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['plugins.Plugins'])),
            ('pm_path', self.gf('django.db.models.fields.CharField')(max_length=1024)),
        ))
        db.send_create_signal('plugins', ['PluginsMountPoints'])


    def backwards(self, orm):
        
        # Deleting model 'PluginsMountPoints'
        db.delete_table('plugins_pluginsmountpoints')


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
        },
        'plugins.pluginsmountpoints': {
            'Meta': {'object_name': 'PluginsMountPoints'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'pm_path': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'pm_plugin': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['plugins.Plugins']"})
        }
    }

    complete_apps = ['plugins']
