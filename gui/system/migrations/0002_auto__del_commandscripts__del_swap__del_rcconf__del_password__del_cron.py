# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Deleting model 'CommandScripts'
        db.delete_table('system_commandscripts')

        # Deleting model 'Swap'
        db.delete_table('system_swap')

        # Deleting model 'rcconf'
        db.delete_table('system_rcconf')

        # Deleting model 'Password'
        db.delete_table('system_password')

        # Deleting model 'CronJob'
        db.delete_table('system_cronjob')

        # Deleting model 'sysctl'
        db.delete_table('system_sysctl')

        # Deleting model 'Email'
        db.delete_table('system_email')

        # Deleting model 'Proxy'
        db.delete_table('system_proxy')

        # Deleting field 'Settings.stg_username'
        db.delete_column('system_settings', 'stg_username')


    def backwards(self, orm):
        
        # Adding model 'CommandScripts'
        db.create_table('system_commandscripts', (
            ('cmds_commandtype', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('cmds_command', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('system', ['CommandScripts'])

        # Adding model 'Swap'
        db.create_table('system_swap', (
            ('swap_memory', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('swap_type', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('swap_mountpoint', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('swap_size', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('system', ['Swap'])

        # Adding model 'rcconf'
        db.create_table('system_rcconf', (
            ('rcc_varname', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('rcc_varcomment', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('rcc_varvalue', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('system', ['rcconf'])

        # Adding model 'Password'
        db.create_table('system_password', (
            ('pw_newpw2', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('pw_currentpw', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('pw_newpw', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('system', ['Password'])

        # Adding model 'CronJob'
        db.create_table('system_cronjob', (
            ('cron_Days1', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_Days2', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_Days3', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('cron_description', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('cron_ToggleWeekdays', self.gf('django.db.models.fields.CharField')(default='Selected', max_length=120)),
            ('cron_Hours2', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_Hours1', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_command', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('cron_ToggleHours', self.gf('django.db.models.fields.CharField')(default='Selected', max_length=120)),
            ('cron_ToggleMonths', self.gf('django.db.models.fields.CharField')(default='Selected', max_length=120)),
            ('cron_ToggleMinutes', self.gf('django.db.models.fields.CharField')(default='Selected', max_length=120)),
            ('cron_Minutes4', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_Minutes3', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_ToggleDays', self.gf('django.db.models.fields.CharField')(default='Selected', max_length=120)),
            ('cron_Minutes1', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_Minutes2', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_Weekdays', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_who', self.gf('django.db.models.fields.CharField')(default='root', max_length=120)),
            ('cron_Months', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_enable', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('system', ['CronJob'])

        # Adding model 'sysctl'
        db.create_table('system_sysctl', (
            ('sctl_MIBcomment', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('sctl_MIBname', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('sctl_MIBvalue', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('system', ['sysctl'])

        # Adding model 'Email'
        db.create_table('system_email', (
            ('em_fromemail', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('em_security', self.gf('django.db.models.fields.CharField')(default='none', max_length=120)),
            ('em_smtp', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('em_outgoingserver', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('em_port', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('system', ['Email'])

        # Adding model 'Proxy'
        db.create_table('system_proxy', (
            ('pxy_ftpproxyaddress', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('pxy_httpproxyport', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('pxy_ftpproxy', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('pxy_httpproxy', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('pxy_httpproxyaddress', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('pxy_ftpproxyport', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('pxy_httpproxyauth', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('pxy_ftpproxyauth', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('system', ['Proxy'])

        # Adding field 'Settings.stg_username'
        db.add_column('system_settings', 'stg_username', self.gf('django.db.models.fields.CharField')(default='admin', max_length=120), keep_default=False)


    models = {
        'system.advanced': {
            'Meta': {'object_name': 'Advanced'},
            'adv_consolemenu': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_consolescreensaver': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_firmwarevc': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_motd': ('django.db.models.fields.TextField', [], {'max_length': '1024'}),
            'adv_powerdaemon': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_serialconsole': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_systembeep': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_tuning': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_zeroconfbonjour': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'system.settings': {
            'Meta': {'object_name': 'Settings'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'stg_guiprotocol': ('django.db.models.fields.CharField', [], {'default': "'http'", 'max_length': '120'}),
            'stg_language': ('django.db.models.fields.CharField', [], {'default': "'english'", 'max_length': '120'}),
            'stg_ntpserver1': ('django.db.models.fields.CharField', [], {'default': "'0.freebsd.pool.ntp.org iburst maxpoll 9'", 'max_length': '120'}),
            'stg_ntpserver2': ('django.db.models.fields.CharField', [], {'default': "'1.freebsd.pool.ntp.org iburst maxpoll 9'", 'max_length': '120', 'blank': 'True'}),
            'stg_ntpserver3': ('django.db.models.fields.CharField', [], {'default': "'2.freebsd.pool.ntp.org iburst maxpoll 9'", 'max_length': '120', 'blank': 'True'}),
            'stg_timezone': ('django.db.models.fields.CharField', [], {'default': "'America/Los_Angeles'", 'max_length': '120'})
        }
    }

    complete_apps = ['system']
