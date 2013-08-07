# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'Support.support_type'
        db.delete_column(u'support_support', 'support_type')

        # Deleting field 'Support.support_issue'
        db.delete_column(u'support_support', 'support_issue')

        # Deleting field 'Support.support_email'
        db.delete_column(u'support_support', 'support_email')

        # Adding field 'Support.support_subject'
        db.add_column(u'support_support', 'support_subject',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=50),
                      keep_default=False)


    def backwards(self, orm):
        # Adding field 'Support.support_type'
        db.add_column(u'support_support', 'support_type',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=20),
                      keep_default=False)

        # Adding field 'Support.support_issue'
        db.add_column(u'support_support', 'support_issue',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=50),
                      keep_default=False)

        # Adding field 'Support.support_email'
        db.add_column(u'support_support', 'support_email',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=50),
                      keep_default=False)

        # Deleting field 'Support.support_subject'
        db.delete_column(u'support_support', 'support_subject')


    models = {
        u'support.support': {
            'Meta': {'object_name': 'Support'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'support_description': ('django.db.models.fields.TextField', [], {}),
            'support_subject': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        }
    }

    complete_apps = ['support']