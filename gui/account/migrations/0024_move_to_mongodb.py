# -*- coding: utf-8 -*-
import os
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models

from datastore import get_default_datastore


def bsdusr_sshpubkey(user):
    keysfile = '%s/.ssh/authorized_keys' % user.bsdusr_home
    if not os.path.exists(keysfile):
        return ''
    try:
        with open(keysfile, 'r') as f:
            keys = f.read()
        return keys
    except:
        return ''

class Migration(DataMigration):

    def forwards(self, orm):

        # Skip for install time, we only care for upgrades here
        if 'FREENAS_INSTALL' in os.environ:
            return

        ds = get_default_datastore()

        for g in orm['account.bsdGroups'].objects.filter(bsdgrp_builtin=False):
            ds.insert('groups', {
                'id': g.bsdgrp_gid,
                'name': g.bsdgrp_group,
                'bultin': False,
                'sudo': g.bsdgrp_sudo,
            })

        for u in orm['account.bsdUsers'].objects.filter(bsdusr_builtin=False):
            groups = []
            for bgm in orm['account.bsdGroupMembership'].objects.filter(bsdgrpmember_user=u):
                groups.append(bgm.bsdgrpmember_group.bsdgrp_gid)

            ds.insert('users', {
                'id': u.bsdusr_uid,
                'username': u.bsdusr_username,
                'unixhash': u.bsdusr_unixhash,
                'smbhash': u.bsdusr_smbhash,
                'group': u.bsdusr_group.bsdgrp_gid,
                'home': u.bsdusr_home,
                'shell': u.bsdusr_shell,
                'full_name': u.bsdusr_full_name,
                'builtin': False,
                'email': u.bsdusr_email,
                'password_disabled': u.bsdusr_password_disabled,
                'locked': u.bsdusr_locked,
                'sudo': u.bsdusr_sudo,
                'sshpubkey': bsdusr_sshpubkey(u),
                'groups': groups,
            })

        ds.collection_record_migration('groups', 'freenas9_migration')
        ds.collection_record_migration('users', 'freenas9_migration')

    def backwards(self, orm):
        "Write your backwards methods here."

    models = {
        u'account.bsdgroupmembership': {
            'Meta': {'object_name': 'bsdGroupMembership'},
            'bsdgrpmember_group': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['account.bsdGroups']"}),
            'bsdgrpmember_user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['account.bsdUsers']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'account.bsdgroups': {
            'Meta': {'ordering': "['bsdgrp_builtin', 'bsdgrp_group']", 'object_name': 'bsdGroups'},
            'bsdgrp_builtin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bsdgrp_gid': ('django.db.models.fields.IntegerField', [], {}),
            'bsdgrp_group': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'bsdgrp_sudo': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'account.bsdusers': {
            'Meta': {'ordering': "['bsdusr_builtin', 'bsdusr_username']", 'object_name': 'bsdUsers'},
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
    symmetrical = True
