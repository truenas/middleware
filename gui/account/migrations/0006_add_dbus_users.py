# encoding: utf-8
import datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models

class Migration(DataMigration):

    def forwards(self, orm):
        group = orm.bsdgroups()
        group.bsdgrp_builtin = True
        group.bsdgrp_gid = "200"
        group.bsdgrp_group = "avahi"
        group.save()
        user = orm.bsdusers()
        user.bsdusr_builtin = True
        user.bsdusr_full_name = "avahi user"
        user.bsdusr_group = group
        user.bsdusr_home = "/nonexistent"
        user.bsdusr_shell = "/usr/sbin/nologin"
        user.bsdusr_smbhash = "*"
        user.bsdusr_unixhash = "*"
        user.bsdusr_uid = "200"
        user.bsdusr_username = "avahi"
        user.save()
        group = orm.bsdgroups()
        group.bsdgrp_builtin = True
        group.bsdgrp_gid = "201"
        group.bsdgrp_group = "messagebus"
        group.save()
        user = orm.bsdusers()
        user.bsdusr_builtin = True
        user.bsdusr_full_name = "messagebus user"
        user.bsdusr_group = group
        user.bsdusr_home = "/nonexistent"
        user.bsdusr_shell = "/usr/sbin/nologin"
        user.bsdusr_smbhash = "*"
        user.bsdusr_unixhash = "*"
        user.bsdusr_uid = "201"
        user.bsdusr_username = "messagebus"
        user.save()

    def backwards(self, orm):
        pass


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
            'bsdusr_full_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'bsdusr_group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['account.bsdGroups']"}),
            'bsdusr_home': ('django.db.models.fields.CharField', [], {'default': "'/nonexistent'", 'max_length': '120'}),
            'bsdusr_shell': ('django.db.models.fields.CharField', [], {'default': "'/bin/csh'", 'max_length': '120'}),
            'bsdusr_smbhash': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '128', 'blank': 'True'}),
            'bsdusr_uid': ('django.db.models.fields.IntegerField', [], {'unique': "'True'", 'max_length': '10'}),
            'bsdusr_unixhash': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '128', 'blank': 'True'}),
            'bsdusr_username': ('django.db.models.fields.CharField', [], {'default': "u'User &'", 'unique': 'True', 'max_length': '30'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        }
    }

    complete_apps = ['account']
