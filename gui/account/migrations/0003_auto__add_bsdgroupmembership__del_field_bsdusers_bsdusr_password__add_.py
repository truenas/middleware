# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'bsdGroupMembership'
        db.create_table('account_bsdgroupmembership', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('bsdgrpmember_group', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['account.bsdGroups'])),
            ('bsdgrpmember_user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['account.bsdUsers'])),
        ))
        db.send_create_signal('account', ['bsdGroupMembership'])

        # Deleting field 'bsdUsers.bsdusr_password'
        db.delete_column('account_bsdusers', 'bsdusr_password')

        # Adding field 'bsdUsers.bsdusr_unixhash'
        db.add_column('account_bsdusers', 'bsdusr_unixhash', self.gf('django.db.models.fields.CharField')(default='*', max_length=128, blank=True), keep_default=False)

        # Adding field 'bsdUsers.bsdusr_smbhash'
        db.add_column('account_bsdusers', 'bsdusr_smbhash', self.gf('django.db.models.fields.CharField')(default='*', max_length=128, blank=True), keep_default=False)

        # Adding field 'bsdUsers.bsdusr_group'
        db.add_column('account_bsdusers', 'bsdusr_group', self.gf('django.db.models.fields.related.ForeignKey')(default=-1, to=orm['account.bsdGroups']), keep_default=False)

        # Adding field 'bsdUsers.bsdusr_builtin'
        db.add_column('account_bsdusers', 'bsdusr_builtin', self.gf('django.db.models.fields.BooleanField')(default=0), keep_default=False)

        # Removing M2M table for field bsdusr_gid on 'bsdUsers'
        db.delete_table('account_bsdusers_bsdusr_gid')

        # Adding field 'bsdGroups.bsdgrp_builtin'
        db.add_column('account_bsdgroups', 'bsdgrp_builtin', self.gf('django.db.models.fields.BooleanField')(default=0), keep_default=False)


    def backwards(self, orm):
        
        # Deleting model 'bsdGroupMembership'
        db.delete_table('account_bsdgroupmembership')

        # We cannot add back in field 'bsdUsers.bsdusr_password'
        raise RuntimeError(
            "Cannot reverse this migration. 'bsdUsers.bsdusr_password' and its values cannot be restored.")

        # Deleting field 'bsdUsers.bsdusr_unixhash'
        db.delete_column('account_bsdusers', 'bsdusr_unixhash')

        # Deleting field 'bsdUsers.bsdusr_smbhash'
        db.delete_column('account_bsdusers', 'bsdusr_smbhash')

        # Deleting field 'bsdUsers.bsdusr_group'
        db.delete_column('account_bsdusers', 'bsdusr_group_id')

        # Deleting field 'bsdUsers.bsdusr_builtin'
        db.delete_column('account_bsdusers', 'bsdusr_builtin')

        # Adding M2M table for field bsdusr_gid on 'bsdUsers'
        db.create_table('account_bsdusers_bsdusr_gid', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('bsdusers', models.ForeignKey(orm['account.bsdusers'], null=False)),
            ('bsdgroups', models.ForeignKey(orm['account.bsdgroups'], null=False))
        ))
        db.create_unique('account_bsdusers_bsdusr_gid', ['bsdusers_id', 'bsdgroups_id'])

        # Deleting field 'bsdGroups.bsdgrp_builtin'
        db.delete_column('account_bsdgroups', 'bsdgrp_builtin')


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
            'bsdgrp_group': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'account.bsdusers': {
            'Meta': {'object_name': 'bsdUsers'},
            'bsdusr_builtin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bsdusr_full_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'bsdusr_group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['account.bsdGroups']"}),
            'bsdusr_home': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'bsdusr_shell': ('django.db.models.fields.CharField', [], {'default': "'/bin/csh'", 'max_length': '120'}),
            'bsdusr_smbhash': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '128', 'blank': 'True'}),
            'bsdusr_uid': ('django.db.models.fields.IntegerField', [], {'unique': "'True'", 'max_length': '10'}),
            'bsdusr_unixhash': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '128', 'blank': 'True'}),
            'bsdusr_username': ('django.db.models.fields.CharField', [], {'default': "'User &'", 'unique': 'True', 'max_length': '30'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        }
    }

    complete_apps = ['account']
