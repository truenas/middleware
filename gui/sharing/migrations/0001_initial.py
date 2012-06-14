# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'CIFS_Share'
        db.create_table('sharing_cifs_share', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('cifs_name', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('cifs_comment', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('cifs_path', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['storage.MountPoint'])),
            ('cifs_ro', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('cifs_browsable', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('cifs_inheritperms', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('cifs_recyclebin', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('cifs_showhiddenfiles', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('cifs_hostsallow', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('cifs_hostsdeny', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('cifs_auxsmbconf', self.gf('django.db.models.fields.TextField')(max_length=120, blank=True)),
        ))
        db.send_create_signal('sharing', ['CIFS_Share'])

        # Adding model 'AFP_Share'
        db.create_table('sharing_afp_share', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('afp_name', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('afp_comment', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('afp_path', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['storage.MountPoint'])),
            ('afp_sharepw', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('afp_sharecharset', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('afp_allow', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('afp_deny', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('afp_ro', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('afp_rw', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('afp_diskdiscovery', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('afp_discoverymode', self.gf('django.db.models.fields.CharField')(default='Default', max_length=120)),
            ('afp_dbpath', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('afp_cachecnid', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('afp_crlf', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('afp_mswindows', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('afp_noadouble', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('afp_nodev', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('afp_nofileid', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('afp_nohex', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('afp_prodos', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('afp_nostat', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('afp_upriv', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal('sharing', ['AFP_Share'])

        # Adding model 'NFS_Share'
        db.create_table('sharing_nfs_share', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('nfs_comment', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('nfs_path', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['storage.MountPoint'])),
            ('nfs_allroot', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('nfs_network', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('nfs_alldirs', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('nfs_ro', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('nfs_quiet', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('sharing', ['NFS_Share'])


    def backwards(self, orm):
        
        # Deleting model 'CIFS_Share'
        db.delete_table('sharing_cifs_share')

        # Deleting model 'AFP_Share'
        db.delete_table('sharing_afp_share')

        # Deleting model 'NFS_Share'
        db.delete_table('sharing_nfs_share')


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
            'afp_upriv': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'sharing.cifs_share': {
            'Meta': {'object_name': 'CIFS_Share'},
            'cifs_auxsmbconf': ('django.db.models.fields.TextField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_browsable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
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
            'nfs_network': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'nfs_path': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['storage.MountPoint']"}),
            'nfs_quiet': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nfs_ro': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'storage.mountpoint': {
            'Meta': {'object_name': 'MountPoint'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
