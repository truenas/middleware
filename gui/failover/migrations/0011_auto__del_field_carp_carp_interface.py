# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'CARP.carp_interface'
        db.delete_column('network_carp', 'carp_interface_id')


    def backwards(self, orm):

        # User chose to not deal with backwards NULL issues for 'CARP.carp_interface'
        raise RuntimeError("Cannot reverse this migration. 'CARP.carp_interface' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration        # Adding field 'CARP.carp_interface'
        db.add_column('network_carp', 'carp_interface',
                      self.gf('django.db.models.fields.related.ForeignKey')(to=orm['network.Interfaces'], unique=True),
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
            'Meta': {'unique_together': "(('volume', 'carp'),)", 'object_name': 'Failover', 'db_table': "'system_failover'"},
            'carp': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['failover.CARP']"}),
            'disabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ipaddress': ('freenasUI.contrib.IPAddressField.IPAddressField', [], {}),
            'master': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'secret': ('django.db.models.fields.CharField', [], {'default': "'99fcda23ac5b05b9580fa830923603779d0ebbd70a8dc93a496fec1580854a01'", 'max_length': '64'}),
            'timeout': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'volume': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['storage.Volume']"})
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

    complete_apps = ['failover']