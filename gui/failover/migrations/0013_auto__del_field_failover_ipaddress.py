# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'Failover.ipaddress'
        db.delete_column('system_failover', 'ipaddress')


    def backwards(self, orm):

        # User chose to not deal with backwards NULL issues for 'Failover.ipaddress'
        raise RuntimeError("Cannot reverse this migration. 'Failover.ipaddress' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration        # Adding field 'Failover.ipaddress'
        db.add_column('system_failover', 'ipaddress',
                      self.gf('freenasUI.contrib.IPAddressField.IPAddressField')(blank=True),
                      keep_default=False)


    models = {
        u'failover.carp': {
            'Meta': {'object_name': 'CARP', 'db_table': "'network_carp'"},
            'carp_critical': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'carp_group': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'carp_number': ('django.db.models.fields.PositiveIntegerField', [], {'unique': 'True'}),
            'carp_pass': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'carp_skew': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0', 'null': 'True', 'blank': 'True'}),
            'carp_vhid': ('django.db.models.fields.PositiveIntegerField', [], {'unique': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'failover.failover': {
            'Meta': {'object_name': 'Failover', 'db_table': "'system_failover'"},
            'disabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'master': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'timeout': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        }
    }

    complete_apps = ['failover']