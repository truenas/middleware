# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    depends_on = (
        ('storage', '0047_auto__add_field_replremote_ssh_no_cipher'),
    )

    def forwards(self, orm):
        # Adding field 'Settings.stg_wizardshown'
        db.add_column(u'system_settings', 'stg_wizardshown',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)

        if not db.dry_run:
            volumes = orm['storage.Volume'].objects.all().count()
            if volumes > 0:
                orm['system.Settings'].objects.all().update(stg_wizardshown=True)
            else:
                orm['system.Settings'].objects.all().update(stg_wizardshown=False)


    def backwards(self, orm):
        # Deleting field 'Settings.stg_wizardshown'
        db.delete_column(u'system_settings', 'stg_wizardshown')


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
            'ssh_fast_cipher': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ssh_no_cipher': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
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
        u'storage.volume': {
            'Meta': {'object_name': 'Volume'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'vol_encrypt': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'vol_encryptkey': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'vol_fstype': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'vol_guid': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'vol_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'})
        },
        u'system.advanced': {
            'Meta': {'object_name': 'Advanced'},
            'adv_advancedmode': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_anonstats': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'adv_anonstats_token': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'adv_autotune': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_consolemenu': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_consolemsg': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'adv_consolescreensaver': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_debugkernel': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_motd': ('django.db.models.fields.TextField', [], {'default': "'Welcome'", 'max_length': '1024'}),
            'adv_powerdaemon': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_serialconsole': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_serialport': ('django.db.models.fields.CharField', [], {'default': "'0x2f8'", 'max_length': '120'}),
            'adv_serialspeed': ('django.db.models.fields.CharField', [], {'default': "'9600'", 'max_length': '120'}),
            'adv_swapondrive': ('django.db.models.fields.IntegerField', [], {'default': '2'}),
            'adv_traceback': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'adv_uploadcrash': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'system.alert': {
            'Meta': {'object_name': 'Alert'},
            'dismiss': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'message_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'})
        },
        u'system.email': {
            'Meta': {'object_name': 'Email'},
            'em_fromemail': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '120'}),
            'em_outgoingserver': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'em_pass': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'em_port': ('django.db.models.fields.IntegerField', [], {'default': '25'}),
            'em_security': ('django.db.models.fields.CharField', [], {'default': "'plain'", 'max_length': '120'}),
            'em_smtp': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'em_user': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'system.ntpserver': {
            'Meta': {'ordering': "['ntp_address']", 'object_name': 'NTPServer'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ntp_address': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ntp_burst': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ntp_iburst': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'ntp_maxpoll': ('django.db.models.fields.IntegerField', [], {'default': '10'}),
            'ntp_minpoll': ('django.db.models.fields.IntegerField', [], {'default': '6'}),
            'ntp_prefer': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'system.registration': {
            'Meta': {'object_name': 'Registration'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'reg_address': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'reg_cellphone': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'reg_city': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'reg_company': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'reg_email': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'reg_firstname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'reg_homephone': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'reg_lastname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'reg_state': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'reg_workphone': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'reg_zip': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'})
        },
        u'system.settings': {
            'Meta': {'object_name': 'Settings'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'stg_guiaddress': ('django.db.models.fields.CharField', [], {'default': "'0.0.0.0'", 'max_length': '120', 'blank': 'True'}),
            'stg_guihttpsport': ('django.db.models.fields.IntegerField', [], {'default': '443'}),
            'stg_guihttpsredirect': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'stg_guiport': ('django.db.models.fields.IntegerField', [], {'default': '80'}),
            'stg_guiprotocol': ('django.db.models.fields.CharField', [], {'default': "'http'", 'max_length': '120'}),
            'stg_guiv6address': ('django.db.models.fields.CharField', [], {'default': "'::'", 'max_length': '120', 'blank': 'True'}),
            'stg_kbdmap': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'stg_language': ('django.db.models.fields.CharField', [], {'default': "'en'", 'max_length': '120'}),
            'stg_syslogserver': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '120', 'blank': 'True'}),
            'stg_timezone': ('django.db.models.fields.CharField', [], {'default': "'America/Los_Angeles'", 'max_length': '120'}),
            'stg_wizardshown': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'system.ssl': {
            'Meta': {'object_name': 'SSL'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ssl_certfile': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'ssl_city': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ssl_common': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ssl_country': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ssl_email': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ssl_org': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ssl_passphrase': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ssl_state': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ssl_unit': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'})
        },
        u'system.systemdataset': {
            'Meta': {'object_name': 'SystemDataset'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'sys_pool': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'sys_rrd_usedataset': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'sys_syslog_usedataset': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'system.tunable': {
            'Meta': {'ordering': "['tun_var']", 'object_name': 'Tunable'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'tun_comment': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'tun_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'tun_type': ('django.db.models.fields.CharField', [], {'default': "'loader'", 'max_length': '20'}),
            'tun_value': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'tun_var': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '50'})
        },
    }

    complete_apps = ['storage', 'system']
