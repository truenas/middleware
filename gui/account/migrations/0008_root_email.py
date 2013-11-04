# encoding: utf-8
import datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models

class Migration(DataMigration):

    def forwards(self, orm):
        # Deprecated migration
        pass

    def backwards(self, orm):
        "Write your backwards methods here."


    models = {
        'account.bsdgroupmembership': {
            'Meta': {'object_name': 'bsdGroupMembership'},
            'bsdgrpmember_group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['account.bsdGroups']"}),
            'bsdgrpmember_user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['account.bsdUsers']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'account.bsdgroups': {
            'Meta': {'object_name': 'bsdGroups'},
            'bsdgrp_builtin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bsdgrp_gid': ('django.db.models.fields.IntegerField', [], {}),
            'bsdgrp_group': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'account.bsdusers': {
            'Meta': {'object_name': 'bsdUsers'},
            'bsdusr_builtin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bsdusr_email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'bsdusr_full_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'bsdusr_group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['account.bsdGroups']"}),
            'bsdusr_home': ('django.db.models.fields.CharField', [], {'default': "'/nonexistent'", 'max_length': '120'}),
            'bsdusr_shell': ('django.db.models.fields.CharField', [], {'default': "'/bin/csh'", 'max_length': '120'}),
            'bsdusr_smbhash': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '128', 'blank': 'True'}),
            'bsdusr_uid': ('django.db.models.fields.IntegerField', [], {'unique': "'True'", 'max_length': '10'}),
            'bsdusr_unixhash': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '128', 'blank': 'True'}),
            'bsdusr_username': ('django.db.models.fields.CharField', [], {'default': "u'User &'", 'unique': 'True', 'max_length': '30'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.message': {
            'Meta': {'object_name': 'Message'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'message': ('django.db.models.fields.TextField', [], {}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'_message_set'", 'to': "orm['auth.User']"})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        }
    }

    complete_apps = ['auth', 'account']
