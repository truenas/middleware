# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Changing field 'Interfaces.int_v6netmaskbit'
        db.alter_column('network_interfaces', 'int_v6netmaskbit', self.gf('django.db.models.fields.CharField')(max_length=4))

        # Changing field 'Interfaces.int_ipv4address'
        db.alter_column('network_interfaces', 'int_ipv4address', self.gf('freenasUI.contrib.IPAddressField.IPAddressField')())

        # Changing field 'Interfaces.int_ipv6address'
        db.alter_column('network_interfaces', 'int_ipv6address', self.gf('freenasUI.contrib.IPAddressField.IPAddressField')())

        # Changing field 'Interfaces.int_v4netmaskbit'
        db.alter_column('network_interfaces', 'int_v4netmaskbit', self.gf('django.db.models.fields.CharField')(max_length=3))

        # Changing field 'GlobalConfiguration.gc_ipv4gateway'
        db.alter_column('network_globalconfiguration', 'gc_ipv4gateway', self.gf('freenasUI.contrib.IPAddressField.IP4AddressField')())

        # Changing field 'GlobalConfiguration.gc_ipv6gateway'
        db.alter_column('network_globalconfiguration', 'gc_ipv6gateway', self.gf('freenasUI.contrib.IPAddressField.IP6AddressField')())

        # Changing field 'GlobalConfiguration.gc_nameserver1'
        db.alter_column('network_globalconfiguration', 'gc_nameserver1', self.gf('freenasUI.contrib.IPAddressField.IPAddressField')())

        # Changing field 'GlobalConfiguration.gc_nameserver3'
        db.alter_column('network_globalconfiguration', 'gc_nameserver3', self.gf('freenasUI.contrib.IPAddressField.IPAddressField')())

        # Changing field 'GlobalConfiguration.gc_nameserver2'
        db.alter_column('network_globalconfiguration', 'gc_nameserver2', self.gf('freenasUI.contrib.IPAddressField.IPAddressField')())


    def backwards(self, orm):
        
        # Changing field 'Interfaces.int_v6netmaskbit'
        db.alter_column('network_interfaces', 'int_v6netmaskbit', self.gf('django.db.models.fields.CharField')(max_length=4, null=True))

        # Changing field 'Interfaces.int_ipv4address'
        db.alter_column('network_interfaces', 'int_ipv4address', self.gf('freenasUI.contrib.IPAddressField.IPAddressField')(null=True))

        # Changing field 'Interfaces.int_ipv6address'
        db.alter_column('network_interfaces', 'int_ipv6address', self.gf('freenasUI.contrib.IPAddressField.IPAddressField')(null=True))

        # Changing field 'Interfaces.int_v4netmaskbit'
        db.alter_column('network_interfaces', 'int_v4netmaskbit', self.gf('django.db.models.fields.CharField')(max_length=3, null=True))

        # Changing field 'GlobalConfiguration.gc_ipv4gateway'
        db.alter_column('network_globalconfiguration', 'gc_ipv4gateway', self.gf('freenasUI.contrib.IPAddressField.IP4AddressField')(null=True))

        # Changing field 'GlobalConfiguration.gc_ipv6gateway'
        db.alter_column('network_globalconfiguration', 'gc_ipv6gateway', self.gf('freenasUI.contrib.IPAddressField.IP6AddressField')(null=True))

        # Changing field 'GlobalConfiguration.gc_nameserver1'
        db.alter_column('network_globalconfiguration', 'gc_nameserver1', self.gf('freenasUI.contrib.IPAddressField.IPAddressField')(null=True))

        # Changing field 'GlobalConfiguration.gc_nameserver3'
        db.alter_column('network_globalconfiguration', 'gc_nameserver3', self.gf('freenasUI.contrib.IPAddressField.IPAddressField')(null=True))

        # Changing field 'GlobalConfiguration.gc_nameserver2'
        db.alter_column('network_globalconfiguration', 'gc_nameserver2', self.gf('freenasUI.contrib.IPAddressField.IPAddressField')(null=True))


    models = {
        'network.globalconfiguration': {
            'Meta': {'object_name': 'GlobalConfiguration'},
            'gc_domain': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'gc_hostname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'gc_ipv4gateway': ('freenasUI.contrib.IPAddressField.IP4AddressField', [], {'default': "''", 'blank': 'True'}),
            'gc_ipv6gateway': ('freenasUI.contrib.IPAddressField.IP6AddressField', [], {'default': "''", 'blank': 'True'}),
            'gc_nameserver1': ('freenasUI.contrib.IPAddressField.IPAddressField', [], {'default': "''", 'blank': 'True'}),
            'gc_nameserver2': ('freenasUI.contrib.IPAddressField.IPAddressField', [], {'default': "''", 'blank': 'True'}),
            'gc_nameserver3': ('freenasUI.contrib.IPAddressField.IPAddressField', [], {'default': "''", 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'network.interfaces': {
            'Meta': {'object_name': 'Interfaces'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
        'network.lagginterface': {
            'Meta': {'object_name': 'LAGGInterface'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lagg_interface': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['network.Interfaces']", 'unique': 'True'}),
            'lagg_protocol': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'network.lagginterfacemembers': {
            'Meta': {'object_name': 'LAGGInterfaceMembers'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lagg_deviceoptions': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'lagg_interfacegroup': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['network.LAGGInterface']"}),
            'lagg_ordernum': ('django.db.models.fields.IntegerField', [], {}),
            'lagg_physnic': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'})
        },
        'network.staticroute': {
            'Meta': {'object_name': 'StaticRoute'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'sr_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'sr_destination': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'sr_gateway': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'network.vlan': {
            'Meta': {'object_name': 'VLAN'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'vlan_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'vlan_pint': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
            'vlan_tag': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'vlan_vint': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        }
    }

    complete_apps = ['network']
