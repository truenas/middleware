# encoding: utf-8
import datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models
from freenasUI.common.system import get_sw_name


class Migration(DataMigration):

    def forwards(self, orm):
        
        # Adding model 'Email'
        db.create_table('system_email', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('em_fromemail', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('em_outgoingserver', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('em_port', self.gf('django.db.models.fields.IntegerField')(default=25)),
            ('em_security', self.gf('django.db.models.fields.CharField')(default='plain', max_length=120)),
            ('em_smtp', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('em_user', self.gf('django.db.models.fields.CharField')(max_length=120, null=True, blank=True)),
            ('em_pass', self.gf('django.db.models.fields.CharField')(max_length=120, null=True, blank=True)),
        ))
        db.send_create_signal('system', ['Email'])

        em = orm.Email()
        em.em_fromemail = 'root@%s.local' % (get_sw_name().lower(), )
        em.em_port = 25
        em.em_smtp = False
        em.save()

    def backwards(self, orm):
        
        # Deleting model 'Email'
        db.delete_table('system_email')


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
