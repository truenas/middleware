# encoding: utf-8
import datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models
from freenasUI.common.system import get_sw_name

class Migration(DataMigration):

    def forwards(self, orm):
        
        # Adding model 'GlobalConfiguration'
        db.create_table('network_globalconfiguration', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('gc_hostname', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('gc_domain', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('gc_ipv4gateway', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('gc_ipv6gateway', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('gc_nameserver1', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('gc_nameserver2', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('gc_nameserver3', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
        ))
        db.send_create_signal('network', ['GlobalConfiguration'])

        # Adding model 'Interfaces'
        db.create_table('network_interfaces', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('int_interface', self.gf('django.db.models.fields.CharField')(max_length=300)),
            ('int_name', self.gf('django.db.models.fields.CharField')(max_length='120')),
            ('int_dhcp', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('int_ipv4address', self.gf('django.db.models.fields.CharField')(max_length=18, blank=True)),
            ('int_ipv6auto', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('int_ipv6address', self.gf('django.db.models.fields.CharField')(max_length=42, blank=True)),
            ('int_options', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
        ))
        db.send_create_signal('network', ['Interfaces'])

        # Adding model 'VLAN'
        db.create_table('network_vlan', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('vlan_vint', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('vlan_pint', self.gf('django.db.models.fields.CharField')(max_length=300)),
            ('vlan_tag', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('vlan_description', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
        ))
        db.send_create_signal('network', ['VLAN'])

        # Adding model 'LAGG'
        db.create_table('network_lagg', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('lagg_vint', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('lagg_ports', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('lagg_description', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
        ))
        db.send_create_signal('network', ['LAGG'])

        # Adding model 'StaticRoute'
        db.create_table('network_staticroute', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('sr_destination', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('sr_gateway', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('sr_description', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
        ))
        db.send_create_signal('network', ['StaticRoute'])

        gc = orm.GlobalConfiguration()
        gc.gc_hostname = get_sw_name().lower()
        gc.gc_domain = 'local'
        gc.save()

    def backwards(self, orm):
        
        # Deleting model 'GlobalConfiguration'
        db.delete_table('network_globalconfiguration')

        # Deleting model 'Interfaces'
        db.delete_table('network_interfaces')

        # Deleting model 'VLAN'
        db.delete_table('network_vlan')

        # Deleting model 'LAGG'
        db.delete_table('network_lagg')

        # Deleting model 'StaticRoute'
        db.delete_table('network_staticroute')


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
        'network.lagg': {
            'Meta': {'object_name': 'LAGG'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lagg_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'lagg_ports': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'lagg_vint': ('django.db.models.fields.CharField', [], {'max_length': '120'})
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
