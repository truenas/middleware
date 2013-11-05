# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models


class Migration(DataMigration):

    def forwards(self, orm):
        # Removing unique constraint on 'bsdUsers', fields ['bsdusr_uid']
        db.delete_unique(u'account_bsdusers', ['bsdusr_uid'])

        # Adding field 'bsdUsers.bsdusr_sudo'
        db.add_column(u'account_bsdusers', 'bsdusr_sudo',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)


        # Changing field 'bsdUsers.bsdusr_username'
        db.alter_column(u'account_bsdusers', 'bsdusr_username', self.gf('django.db.models.fields.CharField')(unique=True, max_length=16))

        # Changing field 'bsdUsers.bsdusr_uid'
        db.alter_column(u'account_bsdusers', 'bsdusr_uid', self.gf('django.db.models.fields.IntegerField')())

        # Changing field 'bsdUsers.bsdusr_home'
        db.alter_column(u'account_bsdusers', 'bsdusr_home', self.gf('freenasUI.freeadmin.models.fields.PathField')(max_length=255))
        # Adding field 'bsdGroups.bsdgrp_sudo'
        db.add_column(u'account_bsdgroups', 'bsdgrp_sudo',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)

        # Workaround south bug
        orm['account.bsdUsers'].objects.update(bsdusr_sudo=False)
        orm['account.bsdGroups'].objects.update(bsdgrp_sudo=False)


    def backwards(self, orm):
        # Deleting field 'bsdUsers.bsdusr_sudo'
        db.delete_column(u'account_bsdusers', 'bsdusr_sudo')


        # Changing field 'bsdUsers.bsdusr_username'
        db.alter_column(u'account_bsdusers', 'bsdusr_username', self.gf('django.db.models.fields.CharField')(max_length=30, unique=True))

        # Changing field 'bsdUsers.bsdusr_uid'
        db.alter_column(u'account_bsdusers', 'bsdusr_uid', self.gf('django.db.models.fields.IntegerField')(max_length=10, unique='True'))
        # Adding unique constraint on 'bsdUsers', fields ['bsdusr_uid']
        db.create_unique(u'account_bsdusers', ['bsdusr_uid'])


        # Changing field 'bsdUsers.bsdusr_home'
        db.alter_column(u'account_bsdusers', 'bsdusr_home', self.gf('django.db.models.fields.CharField')(max_length=120))
        # Deleting field 'bsdGroups.bsdgrp_sudo'
        db.delete_column(u'account_bsdgroups', 'bsdgrp_sudo')


    models = {
        u'account.bsdgroupmembership': {
            'Meta': {'object_name': 'bsdGroupMembership'},
            'bsdgrpmember_group': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['account.bsdGroups']"}),
            'bsdgrpmember_user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['account.bsdUsers']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'account.bsdgroups': {
            'Meta': {'object_name': 'bsdGroups'},
            'bsdgrp_builtin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bsdgrp_gid': ('django.db.models.fields.IntegerField', [], {}),
            'bsdgrp_group': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'bsdgrp_sudo': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'account.bsdusers': {
            'Meta': {'object_name': 'bsdUsers'},
            'bsdusr_builtin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bsdusr_email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'bsdusr_full_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'bsdusr_group': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['account.bsdGroups']"}),
            'bsdusr_home': ('freenasUI.freeadmin.models.fields.PathField', [], {'default': "'/nonexistent'", 'max_length': '255'}),
            'bsdusr_locked': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bsdusr_password_disabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bsdusr_shell': ('django.db.models.fields.CharField', [], {'default': "'/bin/csh'", 'max_length': '120'}),
            'bsdusr_smbhash': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '128', 'blank': 'True'}),
            'bsdusr_sudo': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bsdusr_uid': ('django.db.models.fields.IntegerField', [], {}),
            'bsdusr_unixhash': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '128', 'blank': 'True'}),
            'bsdusr_username': ('django.db.models.fields.CharField', [], {'default': "u'User &'", 'unique': 'True', 'max_length': '16'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        }
    }

    complete_apps = ['account']
