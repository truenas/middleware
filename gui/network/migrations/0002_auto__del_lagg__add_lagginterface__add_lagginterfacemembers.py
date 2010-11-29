# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Deleting model 'LAGG'
        db.delete_table('network_lagg')

        # Adding model 'LAGGInterface'
        db.create_table('network_lagginterface', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('lagg_interface', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['network.Interfaces'], unique=True)),
            ('lagg_protocol', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('network', ['LAGGInterface'])

        # Adding model 'LAGGInterfaceMembers'
        db.create_table('network_lagginterfacemembers', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('lagg_interfacegroup', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['network.LAGGInterface'])),
            ('lagg_ordernum', self.gf('django.db.models.fields.IntegerField')()),
            ('lagg_physnic', self.gf('django.db.models.fields.CharField')(unique=True, max_length=120)),
            ('lagg_deviceoptions', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('network', ['LAGGInterfaceMembers'])


    def backwards(self, orm):
        
        # Adding model 'LAGG'
        db.create_table('network_lagg', (
            ('lagg_description', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('lagg_ports', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('lagg_vint', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('network', ['LAGG'])

        # Deleting model 'LAGGInterface'
        db.delete_table('network_lagginterface')

        # Deleting model 'LAGGInterfaceMembers'
        db.delete_table('network_lagginterfacemembers')


    models = {
        'network.globalconfiguration': {
            'Meta': {'object_name': 'GlobalConfiguration'},
            'gc_domain': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'gc_hostname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'gc_ipv4gateway': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'gc_ipv6gateway': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'gc_nameserver1': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'gc_nameserver2': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'gc_nameserver3': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'network.interfaces': {
            'Meta': {'object_name': 'Interfaces'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'int_dhcp': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'int_interface': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
            'int_ipv4address': ('django.db.models.fields.CharField', [], {'max_length': '18', 'blank': 'True'}),
            'int_ipv6address': ('django.db.models.fields.CharField', [], {'max_length': '42', 'blank': 'True'}),
            'int_ipv6auto': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'int_name': ('django.db.models.fields.CharField', [], {'max_length': "'120'"}),
            'int_options': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'})
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
