# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models
from freenasUI.plugins.models import PLUGINS_REPO


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'Configuration.collectionurl'
        db.delete_column(u'plugins_configuration', 'collectionurl')

        # Adding field 'Configuration.repourl'
        db.add_column(u'plugins_configuration', 'repourl',
                      self.gf('django.db.models.fields.CharField')(default=PLUGINS_REPO, max_length=255, blank=True),
                      keep_default=False)


    def backwards(self, orm):
        # Adding field 'Configuration.collectionurl'
        db.add_column(u'plugins_configuration', 'collectionurl',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=255, blank=True),
                      keep_default=False)

        # Deleting field 'Configuration.repourl'
        db.delete_column(u'plugins_configuration', 'repourl')


    models = {
        u'plugins.configuration': {
            'Meta': {'object_name': 'Configuration'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'repourl': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'})
        },
        u'plugins.plugins': {
            'Meta': {'object_name': 'Plugins'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'plugin_api_version': ('django.db.models.fields.CharField', [], {'default': "'1'", 'max_length': '20'}),
            'plugin_arch': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'plugin_ip': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'plugin_jail': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_path': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'plugin_pbiname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'plugin_port': ('django.db.models.fields.IntegerField', [], {'max_length': '120'}),
            'plugin_secret': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['services.RPCToken']", 'on_delete': 'models.PROTECT'}),
            'plugin_version': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        u'services.rpctoken': {
            'Meta': {'object_name': 'RPCToken'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'secret': ('django.db.models.fields.CharField', [], {'max_length': '1024'})
        }
    }

    complete_apps = ['plugins']
