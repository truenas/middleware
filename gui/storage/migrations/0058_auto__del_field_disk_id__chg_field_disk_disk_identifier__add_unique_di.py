# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):

        # Deleting field 'Disk.id'
        db.delete_column(u'storage_disk', u'id')

        db.alter_column(u'tasks_smarttest_smarttest_disks', 'disk_id', self.gf('django.db.models.fields.CharField')(max_length=100))

        # Changing field 'Disk.disk_identifier'
        db.alter_column(u'storage_disk', 'disk_identifier', self.gf('django.db.models.fields.CharField')(max_length=42, primary_key=True))
        # Adding unique constraint on 'Disk', fields ['disk_identifier']
        db.create_unique(u'storage_disk', ['disk_identifier'])


    def backwards(self, orm):
        # Removing unique constraint on 'Disk', fields ['disk_identifier']
        db.delete_unique(u'storage_disk', ['disk_identifier'])

        # The following code is provided here to aid in writing a correct migration        # Adding field 'Disk.id'
        db.add_column(u'storage_disk', u'id',
                      self.gf('django.db.models.fields.IntegerField')(null=True),
                      keep_default=False)

        if not db.dry_run:
            for i, d in enumerate(orm['storage.Disk'].objects.all()):
                d.id = i + 1
                d.save()

        # Changing field 'Disk.disk_identifier'
        db.alter_column(u'storage_disk', 'disk_identifier', self.gf('django.db.models.fields.CharField')(max_length=42))


    models = {
        u'storage.disk': {
            'Meta': {'ordering': "['disk_subsystem', 'disk_number']", 'object_name': 'Disk'},
            'disk_acousticlevel': ('django.db.models.fields.CharField', [], {'default': "'Disabled'", 'max_length': '120'}),
            'disk_advpowermgmt': ('django.db.models.fields.CharField', [], {'default': "'Disabled'", 'max_length': '120'}),
            'disk_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'disk_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'disk_hddstandby': ('django.db.models.fields.CharField', [], {'default': "'Always On'", 'max_length': '120'}),
            'disk_identifier': ('django.db.models.fields.CharField', [], {'max_length': '42', 'primary_key': 'True'}),
            'disk_multipath_member': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'disk_multipath_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'disk_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'disk_number': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'disk_serial': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'disk_size': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'disk_smartoptions': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'disk_subsystem': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '10'}),
            'disk_togglesmart': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'disk_transfermode': ('django.db.models.fields.CharField', [], {'default': "'Auto'", 'max_length': '120'})
        },
        u'storage.encrypteddisk': {
            'Meta': {'object_name': 'EncryptedDisk'},
            'encrypted_disk': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['storage.Disk']", 'null': 'True', 'on_delete': 'models.SET_NULL'}),
            'encrypted_provider': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'encrypted_volume': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['storage.Volume']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'storage.replication': {
            'Meta': {'ordering': "['repl_filesystem']", 'object_name': 'Replication'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'repl_begin': ('django.db.models.fields.TimeField', [], {'default': 'datetime.time(0, 0)'}),
            'repl_compression': ('django.db.models.fields.CharField', [], {'default': "'lz4'", 'max_length': '5'}),
            'repl_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'repl_end': ('django.db.models.fields.TimeField', [], {'default': 'datetime.time(23, 59)'}),
            'repl_filesystem': ('django.db.models.fields.CharField', [], {'max_length': '150', 'blank': 'True'}),
            'repl_followdelete': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'repl_lastsnapshot': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'repl_limit': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'repl_remote': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['storage.ReplRemote']"}),
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
        },
        u'tasks.cronjob': {
            'Meta': {'ordering': "['cron_description', 'cron_user']", 'object_name': 'CronJob'},
            'cron_command': ('django.db.models.fields.TextField', [], {}),
            'cron_daymonth': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '100'}),
            'cron_dayweek': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '100'}),
            'cron_description': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'cron_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cron_hour': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '100'}),
            'cron_minute': ('django.db.models.fields.CharField', [], {'default': "'00'", 'max_length': '100'}),
            'cron_month': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '100'}),
            'cron_stderr': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cron_stdout': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cron_user': ('freenasUI.freeadmin.models.fields.UserField', [], {'max_length': '60'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'tasks.initshutdown': {
            'Meta': {'object_name': 'InitShutdown'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ini_command': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'}),
            'ini_script': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'ini_type': ('django.db.models.fields.CharField', [], {'default': "'command'", 'max_length': '15'}),
            'ini_when': ('django.db.models.fields.CharField', [], {'max_length': '15'})
        },
        u'tasks.rsync': {
            'Meta': {'ordering': "['rsync_path', 'rsync_desc']", 'object_name': 'Rsync'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'rsync_archive': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rsync_compress': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'rsync_daymonth': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '100'}),
            'rsync_dayweek': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '100'}),
            'rsync_delayupdates': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'rsync_delete': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rsync_desc': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'rsync_direction': ('django.db.models.fields.CharField', [], {'default': "'push'", 'max_length': '10'}),
            'rsync_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'rsync_extra': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'rsync_hour': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '100'}),
            'rsync_minute': ('django.db.models.fields.CharField', [], {'default': "'00'", 'max_length': '100'}),
            'rsync_mode': ('django.db.models.fields.CharField', [], {'default': "'module'", 'max_length': '20'}),
            'rsync_month': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '100'}),
            'rsync_path': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255'}),
            'rsync_preserveattr': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rsync_preserveperm': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rsync_quiet': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rsync_recursive': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'rsync_remotehost': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'rsync_remotemodule': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'rsync_remotepath': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'rsync_remoteport': ('django.db.models.fields.SmallIntegerField', [], {'default': '22'}),
            'rsync_times': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'rsync_user': ('freenasUI.freeadmin.models.fields.UserField', [], {'max_length': '60'})
        },
        u'tasks.smarttest': {
            'Meta': {'ordering': "['smarttest_type']", 'object_name': 'SMARTTest'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'smarttest_daymonth': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '100'}),
            'smarttest_dayweek': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '100'}),
            'smarttest_desc': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'smarttest_disks': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['storage.Disk']", 'symmetrical': 'False'}),
            'smarttest_hour': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '100'}),
            'smarttest_month': ('django.db.models.fields.CharField', [], {'default': "'*'", 'max_length': '100'}),
            'smarttest_type': ('django.db.models.fields.CharField', [], {'max_length': '2'})
        }
    }

    complete_apps = ['storage', 'tasks']
    symmetrical = True
