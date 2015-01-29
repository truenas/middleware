# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'Support.support_email'
        db.add_column('support_support', 'support_email', self.gf('django.db.models.fields.CharField')(default='', max_length=120), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'Support.support_email'
        db.delete_column('support_support', 'support_email')


    models = {
        'support.support': {
            'Meta': {'object_name': 'Support'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'support_description': ('django.db.models.fields.TextField', [], {}),
            'support_email': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '120'}),
            'support_subject': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        }
    }

    complete_apps = ['support']
