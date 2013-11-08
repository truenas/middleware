# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Kmod'
        db.create_table(u'plugins_kmod', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('plugin', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['plugins.Plugins'])),
            ('module', self.gf('django.db.models.fields.CharField')(max_length=400)),
            ('within_pbi', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('order', self.gf('django.db.models.fields.IntegerField')(default=1)),
        ))
        db.send_create_signal(u'plugins', ['Kmod'])


    def backwards(self, orm):
        # Deleting model 'Kmod'
        db.delete_table(u'plugins_kmod')


    models = {
        u'plugins.configuration': {
            'Meta': {'object_name': 'Configuration'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'repourl': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'})
        },
        u'plugins.kmod': {
            'Meta': {'object_name': 'Kmod'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'module': ('django.db.models.fields.CharField', [], {'max_length': '400'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'plugin': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['plugins.Plugins']"}),
            'within_pbi': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
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