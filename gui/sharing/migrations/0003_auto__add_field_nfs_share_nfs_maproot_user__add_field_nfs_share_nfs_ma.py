# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'NFS_Share.nfs_maproot_user'
        db.add_column('sharing_nfs_share', 'nfs_maproot_user', self.gf('django.db.models.fields.CharField')(default='', max_length=120, blank=True), keep_default=False)

        # Adding field 'NFS_Share.nfs_maproot_group'
        db.add_column('sharing_nfs_share', 'nfs_maproot_group', self.gf('django.db.models.fields.CharField')(default='', max_length=120, blank=True), keep_default=False)

        # Adding field 'NFS_Share.nfs_mapall_user'
        db.add_column('sharing_nfs_share', 'nfs_mapall_user', self.gf('django.db.models.fields.CharField')(default='', max_length=120, blank=True), keep_default=False)

        # Adding field 'NFS_Share.nfs_mapall_group'
        db.add_column('sharing_nfs_share', 'nfs_mapall_group', self.gf('django.db.models.fields.CharField')(default='', max_length=120, blank=True), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'NFS_Share.nfs_maproot_user'
        db.delete_column('sharing_nfs_share', 'nfs_maproot_user')

        # Deleting field 'NFS_Share.nfs_maproot_group'
        db.delete_column('sharing_nfs_share', 'nfs_maproot_group')

        # Deleting field 'NFS_Share.nfs_mapall_user'
        db.delete_column('sharing_nfs_share', 'nfs_mapall_user')

        # Deleting field 'NFS_Share.nfs_mapall_group'
        db.delete_column('sharing_nfs_share', 'nfs_mapall_group')


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
            'afp_path': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['storage.MountPoint']"}),
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
            'cifs_guest': ('django.db.models.fields.CharField', [], {'default': "'www'", 'max_length': '120'}),
            'cifs_guestok': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_guestonly': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_hostsallow': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_hostsdeny': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_inheritperms': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'cifs_path': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['storage.MountPoint']"}),
            'cifs_recyclebin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_ro': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_showhiddenfiles': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'sharing.nfs_share': {
            'Meta': {'object_name': 'NFS_Share'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nfs_alldirs': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nfs_allroot': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nfs_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'nfs_mapall_group': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '120', 'blank': 'True'}),
            'nfs_mapall_user': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '120', 'blank': 'True'}),
            'nfs_maproot_group': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '120', 'blank': 'True'}),
            'nfs_maproot_user': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '120', 'blank': 'True'}),
            'nfs_network': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'nfs_path': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['storage.MountPoint']"}),
            'nfs_quiet': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nfs_ro': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'storage.mountpoint': {
            'Meta': {'object_name': 'MountPoint'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mp_ischild': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'mp_options': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True'}),
            'mp_path': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'mp_volume': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['storage.Volume']"})
        },
        'storage.volume': {
            'Meta': {'object_name': 'Volume'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'vol_fstype': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'vol_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'})
        }
    }

    complete_apps = ['sharing']
