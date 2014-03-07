# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'AFP_Share.afp_sharepw'
        db.delete_column(u'sharing_afp_share', 'afp_sharepw')

    def backwards(self, orm):
        # Adding field 'AFP_Share.afp_sharepw'
        db.add_column(u'sharing_afp_share', 'afp_sharepw',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=120, blank=True),
                      keep_default=False)


    models = {
        u'sharing.afp_share': {
            'Meta': {'ordering': "['afp_name']", 'object_name': 'AFP_Share'},
            'afp_allow': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_dbpath': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_deny': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_dperm': ('django.db.models.fields.CharField', [], {'default': "'644'", 'max_length': '3'}),
            'afp_fperm': ('django.db.models.fields.CharField', [], {'default': "'755'", 'max_length': '3'}),
            'afp_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'afp_nodev': ('django.db.models.fields.BooleanField', [], {}),
            'afp_nostat': ('django.db.models.fields.BooleanField', [], {}),
            'afp_path': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255'}),
            'afp_ro': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_rw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_timemachine': ('django.db.models.fields.BooleanField', [], {}),
            'afp_upriv': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'afp_umask': ('django.db.models.fields.CharField', [], {'default': "'022'", 'max_length': '3'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'sharing.cifs_share': {
            'Meta': {'ordering': "['cifs_name']", 'object_name': 'CIFS_Share'},
            'cifs_auxsmbconf': ('django.db.models.fields.TextField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_browsable': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cifs_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_guestok': ('django.db.models.fields.BooleanField', [], {}),
            'cifs_guestonly': ('django.db.models.fields.BooleanField', [], {}),
            'cifs_hostsallow': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'cifs_hostsdeny': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'cifs_inheritowner': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_inheritperms': ('django.db.models.fields.BooleanField', [], {}),
            'cifs_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'cifs_path': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255'}),
            'cifs_recyclebin': ('django.db.models.fields.BooleanField', [], {}),
            'cifs_ro': ('django.db.models.fields.BooleanField', [], {}),
            'cifs_showhiddenfiles': ('django.db.models.fields.BooleanField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'sharing.nfs_share': {
            'Meta': {'object_name': 'NFS_Share'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nfs_alldirs': ('django.db.models.fields.BooleanField', [], {}),
            'nfs_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'nfs_hosts': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'nfs_mapall_group': ('freenasUI.freeadmin.models.fields.GroupField', [], {'default': "''", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'nfs_mapall_user': ('freenasUI.freeadmin.models.fields.UserField', [], {'default': "''", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'nfs_maproot_group': ('freenasUI.freeadmin.models.fields.GroupField', [], {'default': "''", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'nfs_maproot_user': ('freenasUI.freeadmin.models.fields.UserField', [], {'default': "''", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'nfs_network': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'nfs_quiet': ('django.db.models.fields.BooleanField', [], {}),
            'nfs_ro': ('django.db.models.fields.BooleanField', [], {})
        },
        u'sharing.nfs_share_path': {
            'Meta': {'object_name': 'NFS_Share_Path'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'path': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255'}),
            'share': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'paths'", 'to': u"orm['sharing.NFS_Share']"})
        }
    }

    complete_apps = ['sharing']
