# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'Task.task_excludesystemdataset'
        db.delete_column(u'storage_task', 'task_excludesystemdataset')


    def backwards(self, orm):
        # Adding field 'Task.task_excludesystemdataset'
        db.add_column(u'storage_task', 'task_excludesystemdataset',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)


    models = {
        u'storage.disk': {
            'Meta': {'ordering': "['disk_subsystem', 'disk_number']", 'object_name': 'Disk'},
            'disk_acousticlevel': ('django.db.models.fields.CharField', [], {'default': "'Disabled'", 'max_length': '120'}),
            'disk_advpowermgmt': ('django.db.models.fields.CharField', [], {'default': "'Disabled'", 'max_length': '120'}),
            'disk_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'disk_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'disk_hddstandby': ('django.db.models.fields.CharField', [], {'default': "'Always On'", 'max_length': '120'}),
            'disk_identifier': ('django.db.models.fields.CharField', [], {'max_length': '42'}),
            'disk_multipath_member': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'disk_multipath_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'disk_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'disk_number': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'disk_serial': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'disk_size': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'disk_smartoptions': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'disk_subsystem': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '10'}),
            'disk_togglesmart': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'disk_transfermode': ('django.db.models.fields.CharField', [], {'default': "'Auto'", 'max_length': '120'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'storage.encrypteddisk': {
            'Meta': {'object_name': 'EncryptedDisk'},
            'encrypted_disk': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['storage.Disk']", 'null': 'True', 'on_delete': 'models.SET_NULL'}),
            'encrypted_provider': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'encrypted_volume': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['storage.Volume']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'storage.mountpoint': {
            'Meta': {'object_name': 'MountPoint'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mp_options': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True'}),
            'mp_path': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'mp_volume': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['storage.Volume']"})
        },
        u'storage.replication': {
            'Meta': {'ordering': "['repl_filesystem']", 'object_name': 'Replication'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'repl_begin': ('django.db.models.fields.TimeField', [], {'default': 'datetime.time(0, 0)'}),
            'repl_compression': ('django.db.models.fields.CharField', [], {'default': "'lz4'", 'max_length': '5'}),
            'repl_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'repl_end': ('django.db.models.fields.TimeField', [], {'default': 'datetime.time(23, 59)'}),
            'repl_filesystem': ('django.db.models.fields.CharField', [], {'max_length': '150', 'blank': 'True'}),
            'repl_lastsnapshot': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'repl_limit': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'repl_remote': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['storage.ReplRemote']"}),
            'repl_resetonce': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'repl_userepl': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'repl_zfs': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        u'storage.replremote': {
            'Meta': {'object_name': 'ReplRemote'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ssh_cipher': ('django.db.models.fields.CharField', [], {'default': "'standard'", 'max_length': '20'}),
            'ssh_remote_dedicateduser': ('freenasUI.freeadmin.models.fields.UserField', [], {'default': "''", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ssh_remote_dedicateduser_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ssh_remote_hostkey': ('django.db.models.fields.CharField', [], {'max_length': '2048'}),
            'ssh_remote_hostname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ssh_remote_port': ('django.db.models.fields.IntegerField', [], {'default': '22'})
        },
        u'storage.scrub': {
            'Meta': {'ordering': "['scrub_volume__vol_name']", 'object_name': 'Scrub'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'scrub_daymonth': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '100'}),
            'scrub_dayweek': ('django.db.models.fields.CharField', [], {'default': "'7'", 'max_length': '100'}),
            'scrub_description': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'scrub_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'scrub_hour': ('django.db.models.fields.CharField', [], {'default': "'00'", 'max_length': '100'}),
            'scrub_minute': ('django.db.models.fields.CharField', [], {'default': "'00'", 'max_length': '100'}),
            'scrub_month': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '100'}),
            'scrub_threshold': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '35'}),
            'scrub_volume': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['storage.Volume']", 'unique': 'True'})
        },
        u'storage.task': {
            'Meta': {'ordering': "['task_filesystem']", 'object_name': 'Task'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'task_begin': ('django.db.models.fields.TimeField', [], {'default': 'datetime.time(9, 0)'}),
            'task_byweekday': ('django.db.models.fields.CharField', [], {'default': "'1,2,3,4,5'", 'max_length': '120', 'blank': 'True'}),
            'task_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'task_end': ('django.db.models.fields.TimeField', [], {'default': 'datetime.time(18, 0)'}),
            'task_filesystem': ('django.db.models.fields.CharField', [], {'max_length': '150'}),
            'task_interval': ('django.db.models.fields.PositiveIntegerField', [], {'default': '60', 'max_length': '120'}),
            'task_recursive': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'task_repeat_unit': ('django.db.models.fields.CharField', [], {'default': "'weekly'", 'max_length': '120'}),
            'task_ret_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '2'}),
            'task_ret_unit': ('django.db.models.fields.CharField', [], {'default': "'week'", 'max_length': '120'})
        },
        u'storage.vmwareplugin': {
            'Meta': {'object_name': 'VMWarePlugin'},
            'datastore': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'filesystem': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'hostname': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '200'})
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

    complete_apps = ['storage']