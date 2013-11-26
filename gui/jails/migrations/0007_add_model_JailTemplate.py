# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

from freenasUI.jails.utils import get_jails_index

class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'JailTemplate'
        db.create_table(u'jails_jailtemplate', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('jt_name', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('jt_url', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal(u'jails', ['JailTemplate'])

        #
        # The standard jail types
        #
        db.execute("insert into jails_jailtemplate (jt_name, jt_url) "
            "values ('pluginjail', '%s/freenas-pluginjail.tgz')" % get_jails_index())
        db.execute("insert into jails_jailtemplate (jt_name, jt_url) "
            "values ('portjail', '%s/freenas-portjail.tgz')" % get_jails_index())
        db.execute("insert into jails_jailtemplate (jt_name, jt_url) "
            "values ('standard', '%s/freenas-standard.tgz')" % get_jails_index())

        #
        # And... some Linux jail templates
        #
        db.execute("insert into jails_jailtemplate (jt_name, jt_url) "
            "values ('debian-7.1.0', '%s/linux-debian-7.1.0.tgz')" % get_jails_index())
        db.execute("insert into jails_jailtemplate (jt_name, jt_url) "
            "values ('gentoo-20130820', '%s/linux-gentoo-20130820.tgz')" % get_jails_index())
        db.execute("insert into jails_jailtemplate (jt_name, jt_url) "
            "values ('ubuntu-13.04', '%s/linux-ubuntu-13.04.tgz')" % get_jails_index())
        db.execute("insert into jails_jailtemplate (jt_name, jt_url) "
            "values ('centos-6.4', '%s/linux-centos-6.4.tgz')" % get_jails_index())
        db.execute("insert into jails_jailtemplate (jt_name, jt_url) "
            "values ('suse-12.3', '%s/linux-suse-12.3.tgz')" % get_jails_index())


    def backwards(self, orm):
        # Deleting model 'JailTemplate'
        db.delete_table(u'jails_jailtemplate')


    models = {
        u'jails.jails': {
            'Meta': {'object_name': 'Jails'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jail_alias_bridge_ipv4': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_alias_bridge_ipv6': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_alias_ipv4': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_alias_ipv6': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_autostart': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_bridge_ipv4': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_bridge_ipv6': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_defaultrouter_ipv4': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_defaultrouter_ipv6': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_host': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jail_ipv4': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_ipv6': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_mac': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_nat': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_status': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jail_type': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jail_vnet': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'})
        },
        u'jails.jailsconfiguration': {
            'Meta': {'object_name': 'JailsConfiguration'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jc_collectionurl': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'jc_ipv4_network': ('freenasUI.freeadmin.models.Network4Field', [], {'max_length': '18', 'blank': 'True'}),
            'jc_ipv4_network_end': ('freenasUI.freeadmin.models.Network4Field', [], {'max_length': '18', 'blank': 'True'}),
            'jc_ipv4_network_start': ('freenasUI.freeadmin.models.Network4Field', [], {'max_length': '18', 'blank': 'True'}),
            'jc_ipv6_network': ('freenasUI.freeadmin.models.Network6Field', [], {'max_length': '43', 'blank': 'True'}),
            'jc_ipv6_network_end': ('freenasUI.freeadmin.models.Network6Field', [], {'max_length': '43', 'blank': 'True'}),
            'jc_ipv6_network_start': ('freenasUI.freeadmin.models.Network6Field', [], {'max_length': '43', 'blank': 'True'}),
            'jc_path': ('django.db.models.fields.CharField', [], {'max_length': '1024'})
        },
        u'jails.jailtemplate': {
            'Meta': {'object_name': 'JailTemplate'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jt_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jt_url': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        u'jails.nullmountpoint': {
            'Meta': {'object_name': 'NullMountPoint'},
            'destination': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jail': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'source': ('django.db.models.fields.CharField', [], {'max_length': '300'})
        }
    }

    complete_apps = ['jails']
