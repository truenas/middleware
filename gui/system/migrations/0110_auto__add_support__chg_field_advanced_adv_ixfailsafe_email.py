# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Support'
        db.create_table(u'system_support', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('enabled', self.gf('django.db.models.fields.NullBooleanField')(default=None, null=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=200, blank=True)),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=200, blank=True)),
            ('email', self.gf('django.db.models.fields.EmailField')(max_length=200, blank=True)),
            ('phone', self.gf('django.db.models.fields.CharField')(max_length=200, blank=True)),
            ('secondary_name', self.gf('django.db.models.fields.CharField')(max_length=200, blank=True)),
            ('secondary_title', self.gf('django.db.models.fields.CharField')(max_length=200, blank=True)),
            ('secondary_email', self.gf('django.db.models.fields.EmailField')(max_length=200, blank=True)),
            ('secondary_phone', self.gf('django.db.models.fields.CharField')(max_length=200, blank=True)),
        ))
        db.send_create_signal(u'system', ['Support'])

        if not db.dry_run:
            support = orm['system.Support'].objects.create()
            support.enabled = None
            adv = orm['system.Advanced'].objects.order_by('-id')
            if adv.exists():
                adv = adv[0]
                if adv.adv_ixalert:
                    support.enabled = adv.adv_ixalert
                if adv.adv_ixfailsafe_email:
                    support.secondary_email = adv.adv_ixfailsafe_email
            support.save()


        # Changing field 'Advanced.adv_ixfailsafe_email'
        db.alter_column(u'system_advanced', 'adv_ixfailsafe_email', self.gf('django.db.models.fields.EmailField')(max_length=75))

    def backwards(self, orm):
        # Deleting model 'Support'
        db.delete_table(u'system_support')


        # Changing field 'Advanced.adv_ixfailsafe_email'
        db.alter_column(u'system_advanced', 'adv_ixfailsafe_email', self.gf('django.db.models.fields.EmailField')())

    models = {
        u'system.advanced': {
            'Meta': {'object_name': 'Advanced'},
            'adv_advancedmode': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_anonstats': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'adv_anonstats_token': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'adv_autotune': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_boot_scrub': ('django.db.models.fields.IntegerField', [], {'default': '35'}),
            'adv_consolemenu': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_consolemsg': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'adv_consolescreensaver': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_debugkernel': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_fqdn_syslog': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'adv_graphite': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '120', 'blank': 'True'}),
            'adv_ixalert': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'adv_ixfailsafe_email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'adv_motd': ('django.db.models.fields.TextField', [], {'default': "'Welcome'", 'max_length': '1024'}),
            'adv_periodic_notifyuser': ('freenasUI.freeadmin.models.fields.UserField', [], {'default': "'root'", 'max_length': '120'}),
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
            'Meta': {'unique_together': "(('node', 'message_id'),)", 'object_name': 'Alert'},
            'dismiss': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'message_id': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'node': ('django.db.models.fields.CharField', [], {'default': "'A'", 'max_length': '100'}),
            'timestamp': ('django.db.models.fields.IntegerField', [], {'default': '1488388951'})
        },
        u'system.backup': {
            'Meta': {'object_name': 'Backup'},
            'bak_acknowledged': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bak_destination': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'bak_failed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bak_finished': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bak_finished_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'bak_started_at': ('django.db.models.fields.DateTimeField', [], {}),
            'bak_status': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'bak_worker_pid': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'system.certificate': {
            'Meta': {'object_name': 'Certificate'},
            'cert_CSR': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_certificate': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_chain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cert_city': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_common': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_country': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_digest_algorithm': ('django.db.models.fields.CharField', [], {'default': "'SHA256'", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_email': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_key_length': ('django.db.models.fields.IntegerField', [], {'default': '2048', 'null': 'True', 'blank': 'True'}),
            'cert_lifetime': ('django.db.models.fields.IntegerField', [], {'default': '3650', 'null': 'True', 'blank': 'True'}),
            'cert_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'cert_organization': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_privatekey': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_serial': ('django.db.models.fields.IntegerField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_signedby': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['system.CertificateAuthority']", 'null': 'True', 'blank': 'True'}),
            'cert_state': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_type': ('django.db.models.fields.IntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'system.certificateauthority': {
            'Meta': {'object_name': 'CertificateAuthority'},
            'cert_CSR': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_certificate': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_chain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cert_city': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_common': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_country': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_digest_algorithm': ('django.db.models.fields.CharField', [], {'default': "'SHA256'", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_email': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_key_length': ('django.db.models.fields.IntegerField', [], {'default': '2048', 'null': 'True', 'blank': 'True'}),
            'cert_lifetime': ('django.db.models.fields.IntegerField', [], {'default': '3650', 'null': 'True', 'blank': 'True'}),
            'cert_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'cert_organization': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_privatekey': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_serial': ('django.db.models.fields.IntegerField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_signedby': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['system.CertificateAuthority']", 'null': 'True', 'blank': 'True'}),
            'cert_state': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_type': ('django.db.models.fields.IntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'system.cloudcredentials': {
            'Meta': {'object_name': 'CloudCredentials'},
            'attributes': ('freenasUI.freeadmin.models.fields.DictField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'provider': ('django.db.models.fields.CharField', [], {'max_length': '50'})
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
        u'system.settings': {
            'Meta': {'object_name': 'Settings'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'stg_guiaddress': ('django.db.models.fields.CharField', [], {'default': "'0.0.0.0'", 'max_length': '120', 'blank': 'True'}),
            'stg_guicertificate': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['system.Certificate']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'stg_guihttpsport': ('django.db.models.fields.IntegerField', [], {'default': '443'}),
            'stg_guihttpsredirect': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'stg_guiport': ('django.db.models.fields.IntegerField', [], {'default': '80'}),
            'stg_guiprotocol': ('django.db.models.fields.CharField', [], {'default': "'http'", 'max_length': '120'}),
            'stg_guiv6address': ('django.db.models.fields.CharField', [], {'default': "'::'", 'max_length': '120', 'blank': 'True'}),
            'stg_kbdmap': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'stg_language': ('django.db.models.fields.CharField', [], {'default': "'en'", 'max_length': '120'}),
            'stg_pwenc_check': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'stg_sysloglevel': ('django.db.models.fields.CharField', [], {'default': "'f_info'", 'max_length': '120'}),
            'stg_syslogserver': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '120', 'blank': 'True'}),
            'stg_timezone': ('django.db.models.fields.CharField', [], {'default': "'America/Los_Angeles'", 'max_length': '120'}),
            'stg_wizardshown': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'system.support': {
            'Meta': {'object_name': 'Support'},
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '200', 'blank': 'True'}),
            'enabled': ('django.db.models.fields.NullBooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'phone': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'secondary_email': ('django.db.models.fields.EmailField', [], {'max_length': '200', 'blank': 'True'}),
            'secondary_name': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'secondary_phone': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'secondary_title': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'})
        },
        u'system.systemdataset': {
            'Meta': {'object_name': 'SystemDataset'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'sys_pool': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'sys_rrd_usedataset': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'sys_syslog_usedataset': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'sys_uuid': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'sys_uuid_b': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True', 'blank': 'True'})
        },
        u'system.tunable': {
            'Meta': {'ordering': "['tun_var']", 'object_name': 'Tunable'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'tun_comment': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'tun_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'tun_type': ('django.db.models.fields.CharField', [], {'default': "'loader'", 'max_length': '20'}),
            'tun_value': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'tun_var': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '50'})
        },
        u'system.update': {
            'Meta': {'object_name': 'Update'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'upd_autocheck': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'upd_train': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'})
        }
    }

    complete_apps = ['system']
