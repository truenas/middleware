# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Support'
        db.create_table('support_support', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('support_issue', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('support_type', self.gf('django.db.models.fields.CharField')(max_length=20)),
            ('support_description', self.gf('django.db.models.fields.TextField')()),
            ('support_email', self.gf('django.db.models.fields.CharField')(max_length=50)),
        ))
        db.send_create_signal('support', ['Support'])


    def backwards(self, orm):
        # Deleting model 'Support'
        db.delete_table('support_support')


    models = {
        'support.support': {
            'Meta': {'object_name': 'Support'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'support_description': ('django.db.models.fields.TextField', [], {}),
            'support_email': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'support_issue': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'support_type': ('django.db.models.fields.CharField', [], {'max_length': '20'})
        }
    }

    complete_apps = ['support']