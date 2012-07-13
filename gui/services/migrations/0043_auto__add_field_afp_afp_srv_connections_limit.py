# encoding: utf-8
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'AFP.afp_srv_connections_limit'
        db.add_column('services_afp', 'afp_srv_connections_limit', self.gf('django.db.models.fields.IntegerField')(default=50, max_length=120), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'AFP.afp_srv_connections_limit'
        db.delete_column('services_afp', 'afp_srv_connections_limit')


    models = {
        'services.afp': {
            'Meta': {'object_name': 'AFP'},
            'afp_srv_connections_limit': ('django.db.models.fields.IntegerField', [], {'default': '50', 'max_length': '120'}),
            'afp_srv_guest': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_srv_guest_user': ('freenasUI.freeadmin.models.UserField', [], {'default': "'nobody'", 'max_length': '120'}),
            'afp_srv_local': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_srv_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
    }

    complete_apps = ['services']
