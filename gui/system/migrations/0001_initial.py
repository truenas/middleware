# encoding: utf-8
import datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models
from freenasUI.common.system import get_sw_name

class Migration(DataMigration):

    def forwards(self, orm):
        
        # Adding model 'Settings'
        db.create_table('system_settings', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('stg_username', self.gf('django.db.models.fields.CharField')(default='admin', max_length=120)),
            ('stg_guiprotocol', self.gf('django.db.models.fields.CharField')(default='http', max_length=120)),
            ('stg_language', self.gf('django.db.models.fields.CharField')(default='english', max_length=120)),
            ('stg_timezone', self.gf('django.db.models.fields.CharField')(default='america-los_angeles', max_length=120)),
            ('stg_ntpserver1', self.gf('django.db.models.fields.CharField')(default='0.freebsd.pool.ntp.org iburst maxpoll 10', max_length=120)),
            ('stg_ntpserver2', self.gf('django.db.models.fields.CharField')(default='1.freebsd.pool.ntp.org iburst maxpoll 10', max_length=120, blank=True)),
            ('stg_ntpserver3', self.gf('django.db.models.fields.CharField')(default='2.freebsd.pool.ntp.org iburst maxpoll 10', max_length=120, blank=True)),
        ))
        db.send_create_signal('system', ['Settings'])

        # Adding model 'Password'
        db.create_table('system_password', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('pw_currentpw', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('pw_newpw', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('pw_newpw2', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('system', ['Password'])

        # Adding model 'Advanced'
        db.create_table('system_advanced', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('adv_consolemenu', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('adv_serialconsole', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('adv_consolescreensaver', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('adv_firmwarevc', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('adv_systembeep', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('adv_tuning', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('adv_powerdaemon', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('adv_zeroconfbonjour', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('adv_motd', self.gf('django.db.models.fields.TextField')(max_length=1024)),
        ))
        db.send_create_signal('system', ['Advanced'])

        # Adding model 'Email'
        db.create_table('system_email', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('em_fromemail', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('em_outgoingserver', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('em_port', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('em_security', self.gf('django.db.models.fields.CharField')(default='none', max_length=120)),
            ('em_smtp', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('system', ['Email'])

        # Adding model 'Proxy'
        db.create_table('system_proxy', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('pxy_httpproxy', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('pxy_httpproxyaddress', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('pxy_httpproxyport', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('pxy_httpproxyauth', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('pxy_ftpproxy', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('pxy_ftpproxyaddress', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('pxy_ftpproxyport', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('pxy_ftpproxyauth', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('system', ['Proxy'])

        # Adding model 'Swap'
        db.create_table('system_swap', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('swap_memory', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('swap_type', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('swap_mountpoint', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('swap_size', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('system', ['Swap'])

        # Adding model 'CommandScripts'
        db.create_table('system_commandscripts', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('cmds_command', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('cmds_commandtype', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('system', ['CommandScripts'])

        # Adding model 'CronJob'
        db.create_table('system_cronjob', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('cron_enable', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('cron_command', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('cron_who', self.gf('django.db.models.fields.CharField')(default='root', max_length=120)),
            ('cron_description', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('cron_ToggleMinutes', self.gf('django.db.models.fields.CharField')(default='Selected', max_length=120)),
            ('cron_Minutes1', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_Minutes2', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_Minutes3', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_Minutes4', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_ToggleHours', self.gf('django.db.models.fields.CharField')(default='Selected', max_length=120)),
            ('cron_Hours1', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_Hours2', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_ToggleDays', self.gf('django.db.models.fields.CharField')(default='Selected', max_length=120)),
            ('cron_Days1', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_Days2', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_Days3', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_ToggleMonths', self.gf('django.db.models.fields.CharField')(default='Selected', max_length=120)),
            ('cron_Months', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('cron_ToggleWeekdays', self.gf('django.db.models.fields.CharField')(default='Selected', max_length=120)),
            ('cron_Weekdays', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
        ))
        db.send_create_signal('system', ['CronJob'])

        # Adding model 'rcconf'
        db.create_table('system_rcconf', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('rcc_varname', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('rcc_varvalue', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('rcc_varcomment', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('system', ['rcconf'])

        # Adding model 'sysctl'
        db.create_table('system_sysctl', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('sctl_MIBname', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('sctl_MIBvalue', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('sctl_MIBcomment', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('system', ['sysctl'])

        stg = orm.Settings()
        stg.stg_guiprotocol='http'
        stg.stg_language='en'
        stg.stg_timezone='America/Los_Angeles'
        stg.stg_ntpserver1='0.freebsd.pool.ntp.org iburst maxpoll 10'
        stg.stg_ntpserver2='1.freebsd.pool.ntp.org iburst maxpoll 10'
        stg.stg_ntpserver3='2.freebsd.pool.ntp.org iburst maxpoll 10'
        stg.save()

        adv = orm.Advanced()
        adv.adv_consolemenu=1
        adv.adv_serialconsole=0
        adv.adv_consolescreensaver=0
        adv.adv_firmwarevc=1
        adv.adv_systembeep=1
        adv.adv_tuning=0
        adv.adv_powerdaemon=0
        adv.adv_zeroconfbonjour=1
        adv.adv_motd='Welcome to %s' % (get_sw_name(), )
        adv.adv_swapondrive=2
        adv.save()

    def backwards(self, orm):
        
        # Deleting model 'Settings'
        db.delete_table('system_settings')

        # Deleting model 'Password'
        db.delete_table('system_password')

        # Deleting model 'Advanced'
        db.delete_table('system_advanced')

        # Deleting model 'Email'
        db.delete_table('system_email')

        # Deleting model 'Proxy'
        db.delete_table('system_proxy')

        # Deleting model 'Swap'
        db.delete_table('system_swap')

        # Deleting model 'CommandScripts'
        db.delete_table('system_commandscripts')

        # Deleting model 'CronJob'
        db.delete_table('system_cronjob')

        # Deleting model 'rcconf'
        db.delete_table('system_rcconf')

        # Deleting model 'sysctl'
        db.delete_table('system_sysctl')


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
        'system.commandscripts': {
            'Meta': {'object_name': 'CommandScripts'},
            'cmds_command': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'cmds_commandtype': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'system.cronjob': {
            'Meta': {'object_name': 'CronJob'},
            'cron_Days1': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'cron_Days2': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'cron_Days3': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'cron_Hours1': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'cron_Hours2': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'cron_Minutes1': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'cron_Minutes2': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'cron_Minutes3': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'cron_Minutes4': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'cron_Months': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'cron_ToggleDays': ('django.db.models.fields.CharField', [], {'default': "'Selected'", 'max_length': '120'}),
            'cron_ToggleHours': ('django.db.models.fields.CharField', [], {'default': "'Selected'", 'max_length': '120'}),
            'cron_ToggleMinutes': ('django.db.models.fields.CharField', [], {'default': "'Selected'", 'max_length': '120'}),
            'cron_ToggleMonths': ('django.db.models.fields.CharField', [], {'default': "'Selected'", 'max_length': '120'}),
            'cron_ToggleWeekdays': ('django.db.models.fields.CharField', [], {'default': "'Selected'", 'max_length': '120'}),
            'cron_Weekdays': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'cron_command': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'cron_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cron_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cron_who': ('django.db.models.fields.CharField', [], {'default': "'root'", 'max_length': '120'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'system.email': {
            'Meta': {'object_name': 'Email'},
            'em_fromemail': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'em_outgoingserver': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'em_port': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'em_security': ('django.db.models.fields.CharField', [], {'default': "'none'", 'max_length': '120'}),
            'em_smtp': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'system.password': {
            'Meta': {'object_name': 'Password'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'pw_currentpw': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'pw_newpw': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'pw_newpw2': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'system.proxy': {
            'Meta': {'object_name': 'Proxy'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'pxy_ftpproxy': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'pxy_ftpproxyaddress': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'pxy_ftpproxyauth': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'pxy_ftpproxyport': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'pxy_httpproxy': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'pxy_httpproxyaddress': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'pxy_httpproxyauth': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'pxy_httpproxyport': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'system.rcconf': {
            'Meta': {'object_name': 'rcconf'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'rcc_varcomment': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'rcc_varname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'rcc_varvalue': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'system.settings': {
            'Meta': {'object_name': 'Settings'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'stg_guiprotocol': ('django.db.models.fields.CharField', [], {'default': "'http'", 'max_length': '120'}),
            'stg_language': ('django.db.models.fields.CharField', [], {'default': "'english'", 'max_length': '120'}),
            'stg_ntpserver1': ('django.db.models.fields.CharField', [], {'default': "'0.freebsd.pool.ntp.org iburst maxpoll 9'", 'max_length': '120'}),
            'stg_ntpserver2': ('django.db.models.fields.CharField', [], {'default': "'1.freebsd.pool.ntp.org iburst maxpoll 9'", 'max_length': '120', 'blank': 'True'}),
            'stg_ntpserver3': ('django.db.models.fields.CharField', [], {'default': "'2.freebsd.pool.ntp.org iburst maxpoll 9'", 'max_length': '120', 'blank': 'True'}),
            'stg_timezone': ('django.db.models.fields.CharField', [], {'default': "'america-los_angeles'", 'max_length': '120'}),
            'stg_username': ('django.db.models.fields.CharField', [], {'default': "'admin'", 'max_length': '120'})
        },
        'system.swap': {
            'Meta': {'object_name': 'Swap'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'swap_memory': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'swap_mountpoint': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'swap_size': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'swap_type': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'system.sysctl': {
            'Meta': {'object_name': 'sysctl'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'sctl_MIBcomment': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'sctl_MIBname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'sctl_MIBvalue': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        }
    }

    complete_apps = ['system']
