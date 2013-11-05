# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models


class Migration(DataMigration):

    def forwards(self, orm):
        # Deleting field 'AFP_Share.afp_adouble'
        db.delete_column(u'sharing_afp_share', 'afp_adouble')

        # Deleting field 'AFP_Share.afp_mswindows'
        db.delete_column(u'sharing_afp_share', 'afp_mswindows')

        # Deleting field 'AFP_Share.afp_prodos'
        db.delete_column(u'sharing_afp_share', 'afp_prodos')

        # Deleting field 'AFP_Share.afp_nofileid'
        db.delete_column(u'sharing_afp_share', 'afp_nofileid')

        # Deleting field 'AFP_Share.afp_diskdiscovery'
        db.delete_column(u'sharing_afp_share', 'afp_diskdiscovery')

        # Deleting field 'AFP_Share.afp_sharecharset'
        db.delete_column(u'sharing_afp_share', 'afp_sharecharset')

        # Deleting field 'AFP_Share.afp_nohex'
        db.delete_column(u'sharing_afp_share', 'afp_nohex')

        # Deleting field 'AFP_Share.afp_cachecnid'
        db.delete_column(u'sharing_afp_share', 'afp_cachecnid')

        # Deleting field 'AFP_Share.afp_crlf'
        db.delete_column(u'sharing_afp_share', 'afp_crlf')

        # Adding field 'AFP_Share.afp_timemachine'
        db.add_column(u'sharing_afp_share', 'afp_timemachine',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)

        # Adding field 'AFP_Share.afp_umask'
        db.add_column(u'sharing_afp_share', 'afp_umask',
                      self.gf('django.db.models.fields.CharField')(default='022', max_length=3),
                      keep_default=False)

        # Workaround south bug
        orm['sharing.AFP_Share'].objects.update(
            afp_timemachine=False,
        )


    def backwards(self, orm):
        # Adding field 'AFP_Share.afp_adouble'
        db.add_column(u'sharing_afp_share', 'afp_adouble',
                      self.gf('django.db.models.fields.BooleanField')(default=True),
                      keep_default=False)

        # Adding field 'AFP_Share.afp_mswindows'
        db.add_column(u'sharing_afp_share', 'afp_mswindows',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)

        # Adding field 'AFP_Share.afp_prodos'
        db.add_column(u'sharing_afp_share', 'afp_prodos',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)

        # Adding field 'AFP_Share.afp_nofileid'
        db.add_column(u'sharing_afp_share', 'afp_nofileid',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)

        # Adding field 'AFP_Share.afp_diskdiscovery'
        db.add_column(u'sharing_afp_share', 'afp_diskdiscovery',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)

        # Adding field 'AFP_Share.afp_sharecharset'
        db.add_column(u'sharing_afp_share', 'afp_sharecharset',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=120, blank=True),
                      keep_default=False)

        # Adding field 'AFP_Share.afp_nohex'
        db.add_column(u'sharing_afp_share', 'afp_nohex',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)

        # Adding field 'AFP_Share.afp_cachecnid'
        db.add_column(u'sharing_afp_share', 'afp_cachecnid',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)

        # Adding field 'AFP_Share.afp_crlf'
        db.add_column(u'sharing_afp_share', 'afp_crlf',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)

        # Deleting field 'AFP_Share.afp_timemachine'
        db.delete_column(u'sharing_afp_share', 'afp_timemachine')

        # Deleting field 'AFP_Share.afp_umask'
        db.delete_column(u'sharing_afp_share', 'afp_umask')


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
            'afp_nodev': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_nostat': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_path': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255'}),
            'afp_ro': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_rw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_sharepw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_timemachine': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_umask': ('django.db.models.fields.CharField', [], {'default': "'022'", 'max_length': '3'}),
            'afp_upriv': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'sharing.cifs_share': {
            'Meta': {'ordering': "['cifs_name']", 'object_name': 'CIFS_Share'},
            'cifs_auxsmbconf': ('django.db.models.fields.TextField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_browsable': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cifs_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_guestok': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_guestonly': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_hostsallow': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'cifs_hostsdeny': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'cifs_inheritowner': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_inheritperms': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'cifs_path': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255'}),
            'cifs_recyclebin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_ro': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_showhiddenfiles': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
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
            'nfs_ro': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'sharing.nfs_share_path': {
            'Meta': {'object_name': 'NFS_Share_Path'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'path': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255'}),
            'share': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'paths'", 'to': u"orm['sharing.NFS_Share']"})
        }
    }

    complete_apps = ['sharing']
