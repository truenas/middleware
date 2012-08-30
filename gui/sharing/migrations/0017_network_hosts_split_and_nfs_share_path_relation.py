# -*- coding: utf-8 -*-
import datetime
import re
from ipaddr import IPNetwork
from south.db import db
from south.v2 import DataMigration
from django.db import models

class Migration(DataMigration):

    def forwards(self, orm):
        "Write your forwards methods here."
        # Note: Remember to use orm['appname.ModelName'] rather than "from appname.models..."
        for share in orm['sharing.NFS_Share'].objects.all():
            net = share.nfs_network
            net = re.sub(r'\s{2,}|\n', ' ', net).strip()
            networks = []
            hosts = []
            for n in net.split(' '):
                try:
                    IPNetwork(n.encode('utf-8'))
                    if n.find("/") == -1:
                        raise ValueError(n)
                    networks.append(n)
                except:
                    hosts.append(n)
            share.nfs_network = ' '.join(networks)
            share.nfs_hosts = ' '.join(hosts)

            spath = orm['sharing.NFS_Share_Path']()
            spath.path = share.nfs_path
            spath.share = share
            spath.save()

            share.save()

    def backwards(self, orm):
        "Write your backwards methods here."

    models = {
        'sharing.afp_share': {
            'Meta': {'ordering': "['afp_name']", 'object_name': 'AFP_Share'},
            'afp_adouble': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'afp_allow': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_cachecnid': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_crlf': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_dbpath': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_deny': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_discoverymode': ('django.db.models.fields.CharField', [], {'default': "'Default'", 'max_length': '120'}),
            'afp_diskdiscovery': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_dperm': ('django.db.models.fields.CharField', [], {'default': "'644'", 'max_length': '3'}),
            'afp_fperm': ('django.db.models.fields.CharField', [], {'default': "'755'", 'max_length': '3'}),
            'afp_mswindows': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'afp_nodev': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_nofileid': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_nohex': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_nostat': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_path': ('freenasUI.freeadmin.models.PathField', [], {'max_length': '255'}),
            'afp_prodos': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_ro': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_rw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_sharecharset': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_sharepw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'afp_upriv': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'sharing.cifs_share': {
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
            'cifs_path': ('freenasUI.freeadmin.models.PathField', [], {'max_length': '255'}),
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
            'nfs_hosts': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'nfs_mapall_group': ('freenasUI.freeadmin.models.GroupField', [], {'default': "''", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'nfs_mapall_user': ('freenasUI.freeadmin.models.UserField', [], {'default': "''", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'nfs_maproot_group': ('freenasUI.freeadmin.models.GroupField', [], {'default': "''", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'nfs_maproot_user': ('freenasUI.freeadmin.models.UserField', [], {'default': "''", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'nfs_network': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'nfs_path': ('freenasUI.freeadmin.models.PathField', [], {'max_length': '255'}),
            'nfs_quiet': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nfs_ro': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'sharing.nfs_share_path': {
            'Meta': {'object_name': 'NFS_Share_Path'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'path': ('freenasUI.freeadmin.models.PathField', [], {'max_length': '255'}),
            'share': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'paths'", 'to': "orm['sharing.NFS_Share']"})
        }
    }

    complete_apps = ['sharing']
    symmetrical = True
