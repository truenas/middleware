# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'bsdUsers'
        db.create_table('account_bsdusers', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('bsdusr_uid', self.gf('django.db.models.fields.IntegerField')(unique='True', max_length=10)),
            ('bsdusr_username', self.gf('django.db.models.fields.CharField')(unique=True, max_length=30)),
            ('bsdusr_password', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('bsdusr_home', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('bsdusr_shell', self.gf('django.db.models.fields.CharField')(default='csh', max_length=120)),
            ('bsdusr_full_name', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('account', ['bsdUsers'])

        # Adding M2M table for field bsdusr_gid on 'bsdUsers'
        db.create_table('account_bsdusers_bsdusr_gid', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('bsdusers', models.ForeignKey(orm['account.bsdusers'], null=False)),
            ('bsdgroups', models.ForeignKey(orm['account.bsdgroups'], null=False))
        ))
        db.create_unique('account_bsdusers_bsdusr_gid', ['bsdusers_id', 'bsdgroups_id'])

        # Adding model 'bsdGroups'
        db.create_table('account_bsdgroups', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('bsdgrp_gid', self.gf('django.db.models.fields.IntegerField')()),
            ('bsdgrp_group', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('account', ['bsdGroups'])


    def backwards(self, orm):
        
        # Deleting model 'bsdUsers'
        db.delete_table('account_bsdusers')

        # Removing M2M table for field bsdusr_gid on 'bsdUsers'
        db.delete_table('account_bsdusers_bsdusr_gid')

        # Deleting model 'bsdGroups'
        db.delete_table('account_bsdgroups')


    models = {
        'account.bsdgroups': {
            'Meta': {'object_name': 'bsdGroups'},
            'bsdgrp_gid': ('django.db.models.fields.IntegerField', [], {}),
            'bsdgrp_group': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'account.bsdusers': {
            'Meta': {'object_name': 'bsdUsers'},
            'bsdusr_full_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'bsdusr_gid': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['account.bsdGroups']", 'symmetrical': 'False'}),
            'bsdusr_home': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'bsdusr_password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'bsdusr_shell': ('django.db.models.fields.CharField', [], {'default': "'csh'", 'max_length': '120'}),
            'bsdusr_uid': ('django.db.models.fields.IntegerField', [], {'unique': "'True'", 'max_length': '10'}),
            'bsdusr_username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        }
    }

    complete_apps = ['account']
