# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'Task.task_repeat_unit'
        db.add_column('storage_task', 'task_repeat_unit', self.gf('django.db.models.fields.CharField')(default='weekly', max_length=120), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'Task.task_repeat_unit'
        db.delete_column('storage_task', 'task_repeat_unit')


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
            'mp_ischild': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'mp_options': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True'}),
            'mp_path': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'mp_volume': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['storage.Volume']"})
        },
        'storage.task': {
            'Meta': {'object_name': 'Task'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'task_begin': ('django.db.models.fields.TimeField', [], {'default': "'9:00'"}),
            'task_bymonth': ('django.db.models.fields.CharField', [], {'default': "'1,2,3,4,5,6,7,8,9,a,b,c'", 'max_length': '120', 'blank': 'True'}),
            'task_bymonthday': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'task_byweekday': ('django.db.models.fields.CharField', [], {'default': "'1,2,3,4,5'", 'max_length': '120', 'blank': 'True'}),
            'task_end': ('django.db.models.fields.TimeField', [], {'default': "'18:00'"}),
            'task_interval': ('django.db.models.fields.PositiveIntegerField', [], {'default': '90', 'max_length': '120'}),
            'task_mountpoint': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['storage.MountPoint']"}),
            'task_recursive': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'task_repeat_unit': ('django.db.models.fields.CharField', [], {'default': "'weekly'", 'max_length': '120'}),
            'task_ret_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '2'}),
            'task_ret_unit': ('django.db.models.fields.CharField', [], {'default': "'week'", 'max_length': '120'})
        },
        'storage.volume': {
            'Meta': {'object_name': 'Volume'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'vol_fstype': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'vol_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'})
        }
    }

    complete_apps = ['storage']
