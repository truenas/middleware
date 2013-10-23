# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    depends_on = (
        ('network', '0014_auto__add_field_globalconfiguration_gc_netwait_enabled__add_field_glob'),
        ('system', '0056_auto__del_field_advanced_adv_systembeep__del_field_advanced_adv_zeroco'),
    )

    def forwards(self, orm):
        # Adding model 'CARP'

        try:
            db.execute("select * from network_carp")
            db.execute("select * from system_failover")
            return
        except:
            pass

        db.create_table('network_carp', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('carp_vhid', self.gf('django.db.models.fields.PositiveIntegerField')(unique=True)),
            ('carp_pass', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('carp_v4address', self.gf('freenasUI.contrib.IPAddressField.IP4AddressField')(default='', blank=True)),
            ('carp_v4netmaskbit', self.gf('django.db.models.fields.CharField')(default='', max_length=3, blank=True)),
            ('carp_skew', self.gf('django.db.models.fields.PositiveIntegerField')(default=0, null=True, blank=True)),
        ))
        db.send_create_signal(u'failover', ['CARP'])

        # Adding model 'Failover'
        db.create_table('system_failover', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('volume', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['storage.Volume'])),
            ('carp', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['failover.CARP'])),
            ('ipaddress', self.gf('freenasUI.contrib.IPAddressField.IPAddressField')()),
        ))
        db.send_create_signal(u'failover', ['Failover'])

        # Adding unique constraint on 'Failover', fields ['volume', 'carp']
        db.create_unique('system_failover', ['volume_id', 'carp_id'])


    def backwards(self, orm):
        # Removing unique constraint on 'Failover', fields ['volume', 'carp']
        db.delete_unique('system_failover', ['volume_id', 'carp_id'])

        # Deleting model 'CARP'
        db.delete_table('network_carp')

        # Deleting model 'Failover'
        db.delete_table('system_failover')


    models = {
        u'failover.carp': {
            'Meta': {'object_name': 'CARP', 'db_table': "'network_carp'"},
            'carp_pass': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'carp_skew': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0', 'null': 'True', 'blank': 'True'}),
            'carp_v4address': ('freenasUI.contrib.IPAddressField.IP4AddressField', [], {'default': "''", 'blank': 'True'}),
            'carp_v4netmaskbit': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '3', 'blank': 'True'}),
            'carp_vhid': ('django.db.models.fields.PositiveIntegerField', [], {'unique': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'failover.failover': {
            'Meta': {'unique_together': "(('volume', 'carp'),)", 'object_name': 'Failover', 'db_table': "'system_failover'"},
            'carp': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['failover.CARP']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ipaddress': ('freenasUI.contrib.IPAddressField.IPAddressField', [], {}),
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
