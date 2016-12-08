# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'VM'
        db.create_table(u'vm_vm', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=150)),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=250)),
            ('vcpus', self.gf('django.db.models.fields.IntegerField')(default=1)),
            ('memory', self.gf('django.db.models.fields.IntegerField')()),
            ('bootloader', self.gf('django.db.models.fields.CharField')(default='GRUB', max_length=50)),
        ))
        db.send_create_signal(u'vm', ['VM'])

        # Adding model 'Device'
        db.create_table(u'vm_device', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('vm', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['vm.VM'])),
            ('dtype', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('attributes', self.gf('freenasUI.freeadmin.models.fields.DictField')()),
        ))
        db.send_create_signal(u'vm', ['Device'])


    def backwards(self, orm):
        # Deleting model 'VM'
        db.delete_table(u'vm_vm')

        # Deleting model 'Device'
        db.delete_table(u'vm_device')


    models = {
        u'vm.device': {
            'Meta': {'object_name': 'Device'},
            'attributes': ('freenasUI.freeadmin.models.fields.DictField', [], {}),
            'dtype': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'vm': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['vm.VM']"})
        },
        u'vm.vm': {
            'Meta': {'object_name': 'VM'},
            'bootloader': ('django.db.models.fields.CharField', [], {'default': "'GRUB'", 'max_length': '50'}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '250'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'memory': ('django.db.models.fields.IntegerField', [], {}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '150'}),
            'vcpus': ('django.db.models.fields.IntegerField', [], {'default': '1'})
        }
    }

    complete_apps = ['vm']