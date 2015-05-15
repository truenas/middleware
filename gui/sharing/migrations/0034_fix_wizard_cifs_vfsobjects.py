# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models

import re

class Migration(DataMigration):

    def forwards(self, orm):
        for share in orm.CIFS_Share.objects.all():
            if not share.cifs_vfsobjects:
                continue

            if share.cifs_vfsobjects[0].startswith('['):
                cifs_vfsobjects = []
                for vfsobject in share.cifs_vfsobjects:
                    vfsobject = re.sub("\s+|\[|\]|'", '', vfsobject)
                    cifs_vfsobjects.append(vfsobject)

                if cifs_vfsobjects:
                    share.cifs_vfsobjects = ','.join(cifs_vfsobjects)
                    share.save() 

    def backwards(self, orm):
        "Write your backwards methods here."

    models = {
        u'sharing.afp_share': {
            'Meta': {'ordering': "['afp_name']", 'object_name': 'AFP_Share'},
            'afp_allow': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_deny': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_dperm': ('django.db.models.fields.CharField', [], {'default': "'755'", 'max_length': '3'}),
            'afp_fperm': ('django.db.models.fields.CharField', [], {'default': "'644'", 'max_length': '3'}),
            'afp_hostsallow': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_hostsdeny': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'afp_nodev': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_nostat': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_path': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255'}),
            'afp_ro': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_rw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_timemachine': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_umask': ('django.db.models.fields.CharField', [], {'default': "'000'", 'max_length': '3', 'blank': 'True'}),
            'afp_upriv': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'sharing.cifs_share': {
            'Meta': {'ordering': "['cifs_name']", 'object_name': 'CIFS_Share'},
            'cifs_auxsmbconf': ('django.db.models.fields.TextField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_browsable': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cifs_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_default_permissions': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cifs_guestok': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_guestonly': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_home': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_hostsallow': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'cifs_hostsdeny': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'cifs_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'cifs_path': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'cifs_recyclebin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_ro': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_showhiddenfiles': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_storage_task': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['storage.Task']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'cifs_vfsobjects': ('freenasUI.freeadmin.models.fields.MultiSelectField', [], {'default': "['aio_pthread', 'streams_xattr']", 'max_length': '255', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'sharing.nfs_share': {
            'Meta': {'object_name': 'NFS_Share'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nfs_alldirs': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nfs_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'nfs_hosts': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'nfs_mapall_group': ('freenasUI.freeadmin.models.fields.GroupField', [], {'default': "''", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'nfs_mapall_user': ('freenasUI.freeadmin.models.fields.UserField', [], {'default': "''", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'nfs_maproot_group': ('freenasUI.freeadmin.models.fields.GroupField', [], {'default': "''", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'nfs_maproot_user': ('freenasUI.freeadmin.models.fields.UserField', [], {'default': "''", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'nfs_network': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'nfs_quiet': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nfs_ro': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nfs_security': ('freenasUI.freeadmin.models.fields.MultiSelectField', [], {'max_length': '200', 'blank': 'True'})
        },
        u'sharing.nfs_share_path': {
            'Meta': {'ordering': "['path']", 'object_name': 'NFS_Share_Path'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'path': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255'}),
            'share': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'paths'", 'to': u"orm['sharing.NFS_Share']"})
        },
        u'sharing.webdav_share': {
            'Meta': {'ordering': "['webdav_name']", 'object_name': 'WebDAV_Share'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'webdav_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'webdav_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'webdav_path': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255'}),
            'webdav_perm': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'webdav_ro': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'storage.task': {
            'Meta': {'ordering': "['task_filesystem']", 'object_name': 'Task'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'task_begin': ('django.db.models.fields.TimeField', [], {'default': 'datetime.time(9, 0)'}),
            'task_byweekday': ('django.db.models.fields.CharField', [], {'default': "'1,2,3,4,5'", 'max_length': '120', 'blank': 'True'}),
            'task_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'task_end': ('django.db.models.fields.TimeField', [], {'default': 'datetime.time(18, 0)'}),
            'task_excludesystemdataset': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'task_filesystem': ('django.db.models.fields.CharField', [], {'max_length': '150'}),
            'task_interval': ('django.db.models.fields.PositiveIntegerField', [], {'default': '60', 'max_length': '120'}),
            'task_recursive': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'task_repeat_unit': ('django.db.models.fields.CharField', [], {'default': "'weekly'", 'max_length': '120'}),
            'task_ret_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '2'}),
            'task_ret_unit': ('django.db.models.fields.CharField', [], {'default': "'week'", 'max_length': '120'})
        }
    }

    complete_apps = ['sharing']
    symmetrical = True
