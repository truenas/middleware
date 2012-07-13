# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'Loader'
        db.create_table('system_loader', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('ldr_var', self.gf('django.db.models.fields.CharField')(unique=True, max_length=50)),
            ('ldr_value', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('ldr_comment', self.gf('django.db.models.fields.CharField')(max_length=100, blank=True)),
        ))
        db.send_create_signal('system', ['Loader'])


    def backwards(self, orm):
        
        # Deleting model 'Loader'
        db.delete_table('system_loader')


    models = {
        'storage.disk': {
            'Meta': {'object_name': 'Disk'},
            'disk_acousticlevel': ('django.db.models.fields.CharField', [], {'default': "'Disabled'", 'max_length': '120'}),
            'disk_advpowermgmt': ('django.db.models.fields.CharField', [], {'default': "'Disabled'", 'max_length': '120'}),
            'disk_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'disk_group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['storage.DiskGroup']"}),
            'disk_hddstandby': ('django.db.models.fields.CharField', [], {'default': "'Always On'", 'max_length': '120'}),
            'disk_identifier': ('django.db.models.fields.CharField', [], {'max_length': '42'}),
            'disk_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
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
        'storage.volume': {
            'Meta': {'object_name': 'Volume'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'vol_fstype': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'vol_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'})
        },
        'system.advanced': {
            'Meta': {'object_name': 'Advanced'},
            'adv_consolemenu': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_consolemsg': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'adv_consolescreensaver': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_firmwarevc': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_motd': ('django.db.models.fields.TextField', [], {'max_length': '1024'}),
            'adv_powerdaemon': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_serialconsole': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_swapondrive': ('django.db.models.fields.IntegerField', [], {'default': '2'}),
            'adv_systembeep': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_traceback': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_tuning': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_zeroconfbonjour': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'system.cronjob': {
            'Meta': {'object_name': 'CronJob'},
            'cron_command': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'cron_daymonth': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'cron_dayweek': ('django.db.models.fields.CharField', [], {'default': "'1,2,3,4,5,6,7'", 'max_length': '100'}),
            'cron_description': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'cron_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cron_hour': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'cron_minute': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'cron_month': ('django.db.models.fields.CharField', [], {'default': "'1,2,3,4,5,6,7,8,9,10,a,b,c'", 'max_length': '100'}),
            'cron_user': ('freenasUI.freeadmin.models.UserField', [], {'max_length': '60'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'system.email': {
            'Meta': {'object_name': 'Email'},
            'em_fromemail': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'em_outgoingserver': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'em_pass': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'em_port': ('django.db.models.fields.IntegerField', [], {'default': '25'}),
            'em_security': ('django.db.models.fields.CharField', [], {'default': "'plain'", 'max_length': '120'}),
            'em_smtp': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'em_user': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'system.loader': {
            'Meta': {'object_name': 'Loader'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ldr_comment': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'ldr_value': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'ldr_var': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '50'})
        },
        'system.rsync': {
            'Meta': {'object_name': 'Rsync'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'rsync_archive': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rsync_compress': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'rsync_daymonth': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'rsync_dayweek': ('django.db.models.fields.CharField', [], {'default': "'1,2,3,4,5,6,7'", 'max_length': '100'}),
            'rsync_delete': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rsync_desc': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'rsync_extra': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'rsync_hour': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'rsync_minute': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'rsync_month': ('django.db.models.fields.CharField', [], {'default': "'1,2,3,4,5,6,7,8,9,10,a,b,c'", 'max_length': '100'}),
            'rsync_path': ('freenasUI.freeadmin.models.PathField', [], {'max_length': '255'}),
            'rsync_preserveattr': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rsync_preserveperm': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rsync_quiet': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rsync_recursive': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'rsync_remotehost': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'rsync_remotemodule': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'rsync_times': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'rsync_user': ('freenasUI.freeadmin.models.UserField', [], {'max_length': '60'})
        },
        'system.settings': {
            'Meta': {'object_name': 'Settings'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'stg_guiaddress': ('django.db.models.fields.CharField', [], {'default': "'0.0.0.0'", 'max_length': '120', 'blank': 'True'}),
            'stg_guiport': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '120', 'blank': 'True'}),
            'stg_guiprotocol': ('django.db.models.fields.CharField', [], {'default': "'http'", 'max_length': '120'}),
            'stg_language': ('django.db.models.fields.CharField', [], {'default': "'en'", 'max_length': '120'}),
            'stg_ntpserver1': ('django.db.models.fields.CharField', [], {'default': "'0.freebsd.pool.ntp.org iburst maxpoll 9'", 'max_length': '120'}),
            'stg_ntpserver2': ('django.db.models.fields.CharField', [], {'default': "'1.freebsd.pool.ntp.org iburst maxpoll 9'", 'max_length': '120', 'blank': 'True'}),
            'stg_ntpserver3': ('django.db.models.fields.CharField', [], {'default': "'2.freebsd.pool.ntp.org iburst maxpoll 9'", 'max_length': '120', 'blank': 'True'}),
            'stg_syslogserver': ('freenasUI.contrib.IPAddressField.IPAddressField', [], {'default': "''", 'blank': 'True'}),
            'stg_timezone': ('django.db.models.fields.CharField', [], {'default': "'America/Los_Angeles'", 'max_length': '120'})
        },
        'system.smarttest': {
            'Meta': {'unique_together': "(('smarttest_disk', 'smarttest_type'),)", 'object_name': 'SMARTTest'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'smarttest_daymonth': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'smarttest_dayweek': ('django.db.models.fields.CharField', [], {'default': "'1,2,3,4,5,6,7'", 'max_length': '100'}),
            'smarttest_desc': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'smarttest_disk': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['storage.Disk']"}),
            'smarttest_hour': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'smarttest_month': ('django.db.models.fields.CharField', [], {'default': "'1,2,3,4,5,6,7,8,9,10,a,b,c'", 'max_length': '100'}),
            'smarttest_type': ('django.db.models.fields.CharField', [], {'max_length': '2', 'blank': 'True'})
        },
        'system.ssl': {
            'Meta': {'object_name': 'SSL'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ssl_certfile': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'ssl_city': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ssl_common': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ssl_country': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ssl_email': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ssl_org': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ssl_state': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ssl_unit': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'})
        },
        'system.sysctl': {
            'Meta': {'object_name': 'Sysctl'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'sysctl_comment': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'sysctl_mib': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '50'}),
            'sysctl_value': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        }
    }

    complete_apps = ['system']
