# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting model 'APIClient'
        db.delete_table(u'api_apiclient')


    def backwards(self, orm):
        # Adding model 'APIClient'
        db.create_table(u'api_apiclient', (
            ('secret', self.gf('django.db.models.fields.CharField')(max_length=1024)),
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=100, unique=True)),
        ))
        db.send_create_signal(u'api', ['APIClient'])


    models = {
        
    }

    complete_apps = ['api']