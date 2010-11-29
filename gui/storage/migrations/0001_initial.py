# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'Volume'
        db.create_table('storage_volume', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('vol_name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=120)),
            ('vol_fstype', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('storage', ['Volume'])

        # Adding model 'DiskGroup'
        db.create_table('storage_diskgroup', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('group_name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=120)),
            ('group_type', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('group_volume', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['storage.Volume'])),
        ))
        db.send_create_signal('storage', ['DiskGroup'])

        # Adding model 'Disk'
        db.create_table('storage_disk', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('disk_name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=120)),
            ('disk_disks', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('disk_description', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('disk_transfermode', self.gf('django.db.models.fields.CharField')(default='Auto', max_length=120)),
            ('disk_hddstandby', self.gf('django.db.models.fields.CharField')(default='Always On', max_length=120)),
            ('disk_advpowermgmt', self.gf('django.db.models.fields.CharField')(default='Disabled', max_length=120)),
            ('disk_acousticlevel', self.gf('django.db.models.fields.CharField')(default='Disabled', max_length=120)),
            ('disk_togglesmart', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('disk_smartoptions', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('disk_group', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['storage.DiskGroup'])),
        ))
        db.send_create_signal('storage', ['Disk'])

        # Adding model 'MountPoint'
        db.create_table('storage_mountpoint', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('mp_volume', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['storage.Volume'])),
            ('mp_path', self.gf('django.db.models.fields.CharField')(unique=True, max_length=120)),
            ('mp_options', self.gf('django.db.models.fields.CharField')(max_length=120, null=True)),
        ))
        db.send_create_signal('storage', ['MountPoint'])


    def backwards(self, orm):
        
        # Deleting model 'Volume'
        db.delete_table('storage_volume')

        # Deleting model 'DiskGroup'
        db.delete_table('storage_diskgroup')

        # Deleting model 'Disk'
        db.delete_table('storage_disk')

        # Deleting model 'MountPoint'
        db.delete_table('storage_mountpoint')


    models = {
        'storage.disk': {
            'Meta': {'object_name': 'Disk'},
            'disk_acousticlevel': ('django.db.models.fields.CharField', [], {'default': "'Disabled'", 'max_length': '120'}),
            'disk_advpowermgmt': ('django.db.models.fields.CharField', [], {'default': "'Disabled'", 'max_length': '120'}),
            'disk_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'disk_disks': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'disk_group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['storage.DiskGroup']"}),
            'disk_hddstandby': ('django.db.models.fields.CharField', [], {'default': "'Always On'", 'max_length': '120'}),
            'disk_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'disk_smartoptions': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'disk_togglesmart': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'disk_transfermode': ('django.db.models.fields.CharField', [], {'default': "'Auto'", 'max_length': '120'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'storage.diskgroup': {
            'Meta': {'object_name': 'DiskGroup'},
            'group_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'group_type': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'group_volume': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['storage.Volume']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'storage.mountpoint': {
            'Meta': {'object_name': 'MountPoint'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mp_options': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True'}),
            'mp_path': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'mp_volume': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['storage.Volume']"})
        },
        'storage.volume': {
            'Meta': {'object_name': 'Volume'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'vol_fstype': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'vol_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'})
        }
    }

    complete_apps = ['storage']
