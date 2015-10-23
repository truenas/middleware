# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'VcenterConfiguration'
        db.create_table(u'vcp_vcenterconfiguration', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('vc_management_ip', self.gf('django.db.models.fields.CharField')(default='1', max_length=120)),
            ('vc_ip', self.gf('django.db.models.fields.CharField')(default='', max_length=120)),
            ('vc_port', self.gf('django.db.models.fields.CharField')(default='443', max_length=5)),
            ('vc_username', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('vc_password', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('vc_version', self.gf('django.db.models.fields.CharField')(max_length=120, null=True, blank=True)),
        ))
        db.send_create_signal(u'vcp', ['VcenterConfiguration'])


    def backwards(self, orm):
        # Deleting model 'VcenterConfiguration'
        db.delete_table(u'vcp_vcenterconfiguration')


    models = {
        u'vcp.vcenterauxsettings': {
            'Meta': {'object_name': 'VcenterAuxSettings'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'vc_enable_https': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'vcp.vcenterconfiguration': {
            'Meta': {'object_name': 'VcenterConfiguration'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'vc_ip': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '120'}),
            'vc_management_ip': ('django.db.models.fields.CharField', [], {'default': "'1'", 'max_length': '120'}),
            'vc_password': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'vc_port': ('django.db.models.fields.CharField', [], {'default': "'443'", 'max_length': '5'}),
            'vc_username': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'vc_version': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['vcp']