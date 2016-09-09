# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models


class Migration(DataMigration):

    depends_on = (
        ('services', '0190_dup_webdav'),
        ('tasks', '0004_populate_rsync_delayupdates'),
    )

    def forwards(self, orm):

        seen_idents = []
        id_map = {}
        for d in list(orm['storage.Disk'].objects.order_by('disk_enabled')):
            if d.disk_identifier in seen_idents:
                d.delete()
            else:
                seen_idents.append(d.disk_identifier)
                id_map[str(d.id)] = d.disk_identifier

        """
        Its possible tasks_smarttest_smarttest_disks will have an index called
        sqlite_auto_*, indexes with that kind of name pattern are for internal
        sqlite3 use, thus any table rename operation will lead to an error
        while trying to recreate the index.
        Because if that issue we have to rename the table and manually copy
        the data and create new index
        See #15860
        """
        db.rename_table('tasks_smarttest_smarttest_disks', 'tasks_smarttest_smarttest_disks_old')

        db.create_table('tasks_smarttest_smarttest_disks', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('smarttest', models.ForeignKey(orm['tasks.smarttest'], null=False)),
            ('disk_id', models.CharField(max_length=100, null=False))
        ))

        db._copy_data('tasks_smarttest_smarttest_disks_old', 'tasks_smarttest_smarttest_disks')

        db.create_unique('tasks_smarttest_smarttest_disks', ['smarttest_id', 'disk_id'])
        db.delete_table('tasks_smarttest_smarttest_disks_old')

        rows = db.execute("select id, disk_id from tasks_smarttest_smarttest_disks")
        if rows:
            for row in rows:
                disk_id = row[1]
                if disk_id in id_map:
                    db.execute("update tasks_smarttest_smarttest_disks set disk_id = %s where id = %s", [id_map[disk_id], row[0]])
                else:
                    db.execute("delete from tasks_smarttest_smarttest_disks where id = %s", [row[0]])

        try:
            # Workaround failed migration leaving table behind
            # See #14970
            db.execute("drop table _south_new_storage_encrypteddisk")
        except:
            pass

        db.alter_column(u'storage_encrypteddisk', 'encrypted_disk_id', self.gf('django.db.models.fields.CharField')(max_length=100, null=True))

        rows = db.execute("select id, encrypted_disk_id from storage_encrypteddisk")
        if rows:
            for row in rows:
                disk_id = row[1]
                if disk_id is None:
                    continue
                if disk_id in id_map:
                    db.execute("update storage_encrypteddisk set encrypted_disk_id = %s where id = %s", [id_map[disk_id], row[0]])
                else:
                    db.execute("delete from storage_encrypteddisk where id = %s", [row[0]])


        # Migrate iscsi device extents
        rows = db.execute("select id, iscsi_target_extent_path from services_iscsitargetextent where iscsi_target_extent_type = 'Disk'")
        if rows:
            for row in rows:
                disk_id = row[1]
                if disk_id in id_map:
                    db.execute("update services_iscsitargetextent set iscsi_target_extent_path = %s where id = %s", [id_map[disk_id], row[0]])


    def backwards(self, orm):

        for i, d in enumerate(orm['storage.Disk'].objects.all()):
            d.id = i + 1
            d.save()


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
