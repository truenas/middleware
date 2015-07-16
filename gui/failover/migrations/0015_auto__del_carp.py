# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting model 'CARP'
        db.delete_table('network_carp')


    def backwards(self, orm):
        # Adding model 'CARP'
        db.create_table('network_carp', (
            ('carp_number', self.gf('django.db.models.fields.PositiveIntegerField')(unique=True)),
            ('carp_skew', self.gf('django.db.models.fields.PositiveIntegerField')(default=0, null=True, blank=True)),
            ('carp_critical', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('carp_group', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('carp_vhid', self.gf('django.db.models.fields.PositiveIntegerField')(unique=True)),
            ('carp_pass', self.gf('django.db.models.fields.CharField')(max_length=100)),
        ))
        db.send_create_signal(u'failover', ['CARP'])


    models = {
        u'failover.failover': {
            'Meta': {'object_name': 'Failover', 'db_table': "'system_failover'"},
            'disabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'master': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'timeout': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        }
    }

    complete_apps = ['failover']