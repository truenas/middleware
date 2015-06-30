# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Removing unique constraint on 'Failover', fields ['volume', 'carp']
        db.delete_unique('system_failover', ['volume_id', 'carp_id'])

        # Deleting field 'Failover.volume'
        db.delete_column('system_failover', 'volume_id')

        # Deleting field 'Failover.secret'
        db.delete_column('system_failover', 'secret')

        # Deleting field 'Failover.carp'
        db.delete_column('system_failover', 'carp_id')


    def backwards(self, orm):

        # User chose to not deal with backwards NULL issues for 'Failover.volume'
        raise RuntimeError("Cannot reverse this migration. 'Failover.volume' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration        # Adding field 'Failover.volume'
        db.add_column('system_failover', 'volume',
                      self.gf('django.db.models.fields.related.ForeignKey')(to=orm['storage.Volume']),
                      keep_default=False)

        # Adding field 'Failover.secret'
        db.add_column('system_failover', 'secret',
                      self.gf('django.db.models.fields.CharField')(default='99fcda23ac5b05b9580fa830923603779d0ebbd70a8dc93a496fec1580854a01', max_length=64),
                      keep_default=False)


        # User chose to not deal with backwards NULL issues for 'Failover.carp'
        raise RuntimeError("Cannot reverse this migration. 'Failover.carp' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration        # Adding field 'Failover.carp'
        db.add_column('system_failover', 'carp',
                      self.gf('django.db.models.fields.related.ForeignKey')(to=orm['failover.CARP']),
                      keep_default=False)

        # Adding unique constraint on 'Failover', fields ['volume', 'carp']
        db.create_unique('system_failover', ['volume_id', 'carp_id'])


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
            'ipaddress': ('freenasUI.contrib.IPAddressField.IPAddressField', [], {'blank': 'True'}),
            'master': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'timeout': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        }
    }

    complete_apps = ['failover']