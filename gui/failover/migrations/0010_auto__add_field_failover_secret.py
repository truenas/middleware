# -*- coding: utf-8 -*-
import hashlib
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    depends_on = (
        ('account', '0023_auto__add_field_bsdusers_bsdusr_microsoft_account'),
    )

    def forwards(self, orm):

        # Workaround sqlite3 reserved name bug #8184
        db.delete_unique('system_failover', ['carp_id', 'volume_id'])

        # Adding field 'Failover.secret'
        db.add_column('system_failover', 'secret',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=64),
                      keep_default=False)

        # Workaround sqlite3 reserved name bug #8184
        db.create_unique('system_failover', ['carp_id', 'volume_id'])

        if not db.dry_run:
            failovers = orm['failover.Failover'].objects.all()
            user = orm['account.bsdUsers'].objects.filter(bsdusr_uid=0)
            if failovers.exists() and user.exists():
                user = user[0]
                orm['failover.Failover'].objects.all().update(
                    secret=hashlib.sha256(str(user.bsdusr_unixhash)).hexdigest(),
                )

    def backwards(self, orm):
        # Deleting field 'Failover.secret'
        db.delete_column('system_failover', 'secret')


    models = {
        u'account.bsdgroupmembership': {
            'Meta': {'object_name': 'bsdGroupMembership'},
            'bsdgrpmember_group': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['account.bsdGroups']"}),
            'bsdgrpmember_user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['account.bsdUsers']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'account.bsdgroups': {
            'Meta': {'ordering': "['bsdgrp_builtin']", 'object_name': 'bsdGroups'},
            'bsdgrp_builtin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bsdgrp_gid': ('django.db.models.fields.IntegerField', [], {}),
            'bsdgrp_group': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'bsdgrp_sudo': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'account.bsdusers': {
            'Meta': {'ordering': "['bsdusr_builtin']", 'object_name': 'bsdUsers'},
            'bsdusr_builtin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bsdusr_email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'bsdusr_full_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'bsdusr_group': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['account.bsdGroups']"}),
            'bsdusr_home': ('freenasUI.freeadmin.models.fields.PathField', [], {'default': "'/nonexistent'", 'max_length': '255'}),
            'bsdusr_locked': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bsdusr_microsoft_account': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bsdusr_password_disabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bsdusr_shell': ('django.db.models.fields.CharField', [], {'default': "'/bin/csh'", 'max_length': '120'}),
            'bsdusr_smbhash': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '128', 'blank': 'True'}),
            'bsdusr_sudo': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bsdusr_sudo': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bsdusr_uid': ('django.db.models.fields.IntegerField', [], {}),
            'bsdusr_unixhash': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '128', 'blank': 'True'}),
            'bsdusr_username': ('django.db.models.fields.CharField', [], {'default': "u'User &'", 'unique': 'True', 'max_length': '16'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'failover.carp': {
            'Meta': {'object_name': 'CARP', 'db_table': "'network_carp'"},
            'carp_critical': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'carp_group': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'carp_interface': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['network.Interfaces']", 'unique': 'True'}),
            'carp_number': ('django.db.models.fields.PositiveIntegerField', [], {'unique': 'True'}),
            'carp_pass': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'carp_skew': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0', 'null': 'True', 'blank': 'True'}),
            'carp_vhid': ('django.db.models.fields.PositiveIntegerField', [], {'unique': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'failover.failover': {
            'Meta': {'unique_together': "(('volume', 'carp'),)", 'object_name': 'Failover', 'db_table': "'system_failover'"},
            'carp': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['failover.CARP']"}),
            'disabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ipaddress': ('freenasUI.contrib.IPAddressField.IPAddressField', [], {}),
            'master': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'secret': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'timeout': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'volume': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['storage.Volume']"})
        },
        u'network.interfaces': {
            'Meta': {'ordering': "['int_interface']", 'object_name': 'Interfaces'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'int_dhcp': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'int_interface': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
            'int_ipv4address': ('freenasUI.contrib.IPAddressField.IPAddressField', [], {'default': "''", 'blank': 'True'}),
            'int_ipv6address': ('freenasUI.contrib.IPAddressField.IPAddressField', [], {'default': "''", 'blank': 'True'}),
            'int_ipv6auto': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'int_name': ('django.db.models.fields.CharField', [], {'max_length': "'120'"}),
            'int_options': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'int_v4netmaskbit': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '3', 'blank': 'True'}),
            'int_v6netmaskbit': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '4', 'blank': 'True'})
        },
        u'storage.volume': {
            'Meta': {'object_name': 'Volume'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'vol_encrypt': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'vol_encryptkey': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'vol_fstype': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'vol_guid': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'vol_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'})
        }
    }

    complete_apps = ['account', 'failover']
