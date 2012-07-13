# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Deleting field 'AFP_Share.afp_path2'
        db.delete_column('sharing_afp_share', 'afp_path_id')

        # Renaming column for 'AFP_Share.afp_path' to match new field type.
        db.rename_column('sharing_afp_share', 'afp_path2', 'afp_path')

        # Deleting field 'NFS_Share.nfs_path2'
        db.delete_column('sharing_nfs_share', 'nfs_path_id')

        # Renaming column for 'NFS_Share.nfs_path' to match new field type.
        db.rename_column('sharing_nfs_share', 'nfs_path2', 'nfs_path')

        # Deleting field 'CIFS_Share.cifs_path2'
        db.delete_column('sharing_cifs_share', 'cifs_path_id')

        # Renaming column for 'CIFS_Share.cifs_path' to match new field type.
        db.rename_column('sharing_cifs_share', 'cifs_path2', 'cifs_path')


    def backwards(self, orm):
        
        # Adding index on 'CIFS_Share', fields ['cifs_path']
        db.create_index('sharing_cifs_share', ['cifs_path_id'])

        # Adding index on 'NFS_Share', fields ['nfs_path']
        db.create_index('sharing_nfs_share', ['nfs_path_id'])

        # Adding index on 'AFP_Share', fields ['afp_path']
        db.create_index('sharing_afp_share', ['afp_path_id'])

        # We cannot add back in field 'AFP_Share.afp_path2'
        raise RuntimeError(
            "Cannot reverse this migration. 'AFP_Share.afp_path2' and its values cannot be restored.")

        # Renaming column for 'AFP_Share.afp_path' to match new field type.
        db.rename_column('sharing_afp_share', 'afp_path', 'afp_path_id')
        # Changing field 'AFP_Share.afp_path'
        db.alter_column('sharing_afp_share', 'afp_path_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['storage.MountPoint']))

        # We cannot add back in field 'NFS_Share.nfs_path2'
        raise RuntimeError(
            "Cannot reverse this migration. 'NFS_Share.nfs_path2' and its values cannot be restored.")

        # Renaming column for 'NFS_Share.nfs_path' to match new field type.
        db.rename_column('sharing_nfs_share', 'nfs_path', 'nfs_path_id')
        # Changing field 'NFS_Share.nfs_path'
        db.alter_column('sharing_nfs_share', 'nfs_path_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['storage.MountPoint']))

        # We cannot add back in field 'CIFS_Share.cifs_path2'
        raise RuntimeError(
            "Cannot reverse this migration. 'CIFS_Share.cifs_path2' and its values cannot be restored.")

        # Renaming column for 'CIFS_Share.cifs_path' to match new field type.
        db.rename_column('sharing_cifs_share', 'cifs_path', 'cifs_path_id')
        # Changing field 'CIFS_Share.cifs_path'
        db.alter_column('sharing_cifs_share', 'cifs_path_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['storage.MountPoint']))


    models = {
        'sharing.afp_share': {
            'Meta': {'object_name': 'AFP_Share'},
            'afp_allow': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_cachecnid': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_crlf': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_dbpath': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_deny': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_discoverymode': ('django.db.models.fields.CharField', [], {'default': "'Default'", 'max_length': '120'}),
            'afp_diskdiscovery': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_mswindows': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'afp_noadouble': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_nodev': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_nofileid': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_nohex': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_nostat': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_path': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'afp_prodos': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_ro': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_rw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_sharecharset': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_sharepw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_upriv': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'sharing.cifs_share': {
            'Meta': {'object_name': 'CIFS_Share'},
            'cifs_auxsmbconf': ('django.db.models.fields.TextField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_browsable': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cifs_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_guest': ('freenasUI.freeadmin.models.UserField', [], {'default': "'www'", 'max_length': '120'}),
            'cifs_guestok': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_guestonly': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_hostsallow': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_hostsdeny': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_inheritperms': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'cifs_path': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'cifs_recyclebin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_ro': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_showhiddenfiles': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'sharing.nfs_share': {
            'Meta': {'object_name': 'NFS_Share'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nfs_alldirs': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nfs_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'nfs_mapall_group': ('freenasUI.freeadmin.models.GroupField', [], {'default': "''", 'max_length': '120', 'blank': 'True'}),
            'nfs_mapall_user': ('freenasUI.freeadmin.models.UserField', [], {'default': "''", 'max_length': '120', 'blank': 'True'}),
            'nfs_maproot_group': ('freenasUI.freeadmin.models.GroupField', [], {'default': "''", 'max_length': '120', 'blank': 'True'}),
            'nfs_maproot_user': ('freenasUI.freeadmin.models.UserField', [], {'default': "''", 'max_length': '120', 'blank': 'True'}),
            'nfs_network': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'nfs_path': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'nfs_quiet': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nfs_ro': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        }
    }

    complete_apps = ['sharing']
