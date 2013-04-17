# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting model 'NullMountPoint'
        db.delete_table(u'plugins_nullmountpoint')

        # Adding field 'Plugins.plugin_jail'
        db.add_column(u'plugins_plugins', 'plugin_jail',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=120),
                      keep_default=False)


        # Changing field 'Plugins.plugin_secret'
        db.alter_column(u'plugins_plugins', 'plugin_secret_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['services.RPCToken'], on_delete=models.PROTECT))

    def backwards(self, orm):
        # Adding model 'NullMountPoint'
        db.create_table(u'plugins_nullmountpoint', (
            ('destination', self.gf('django.db.models.fields.CharField')(max_length=300)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('source', self.gf('django.db.models.fields.CharField')(max_length=300)),
        ))
        db.send_create_signal('plugins', ['NullMountPoint'])

        # Deleting field 'Plugins.plugin_jail'
        db.delete_column(u'plugins_plugins', 'plugin_jail')


        # Changing field 'Plugins.plugin_secret'
        db.alter_column(u'plugins_plugins', 'plugin_secret_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['services.RPCToken']))

    models = {
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