# -*- coding: utf-8 -*-
import datetime
import os
import platform
import time
from south.db import db
from south.v2 import DataMigration
from django.db import models

from freenasUI.jails.utils import get_jails_index
from freenasUI.common.pipesubr import pipeopen
from freenasUI.common.warden import (
    get_warden_template_abi_arch,
    get_warden_template_abi_version,
)

class Migration(DataMigration):

    def zfs_rename(self, src, dst):
        p = pipeopen("/sbin/zfs rename -f '%s' '%s'" % (src, dst))
        zfsout = p.communicate()
        if p.returncode != 0:
            return False
        return True

    def zfs_set_mountpoint(self, dataset, mp):
        p = pipeopen("/sbin/zfs set mountpoint='%s' '%s'" % (mp, dataset))
        zfsout = p.communicate()
        if p.returncode != 0:
            return False
        return True

    def mv_template(self, src, dst):
        p = pipeopen("/bin/mv '%s' '%s'" % (src, dst))
        out = p.communicate()
        if p.returncode != 0:
            return False
        return True

    def forwards(self, orm):
        templates = ['pluginjail', 'portjail', 'standard']
        freebsd_release = '9.2-RELEASE'
        freenas_release = '9.2.0'

        arch = platform.architecture()
        if arch[0] == '64bit':
            arch = 'x64'
        else:
            arch = 'x86'

        for t in templates:
            t = orm['jails.Jailtemplate'].objects.filter(jt_name='%s' % t)[0]
            t.jt_url = "%s/freenas-%s-%s.tgz" % \
                 (get_jails_index(release='9.2.0', arch=arch), t, freebsd_release)
            t.save()

        jc = None
        jc_dataset = None

        try:
            jc = orm['jails.JailsConfiguration'].objects.order_by("-id")[0]
        except:
            pass

        if jc and jc.jc_path:
            p = pipeopen("/sbin/zfs list -H")
            zfsout = p.communicate()
            lines = zfsout[0].strip().split('\n')
            for line in lines:
                parts = line.split()
                if parts[4] == jc.jc_path:
                    jc_dataset = parts[0]
                    break

        if jc_dataset:
            for t in templates:
                template = "%s/.warden-template-%s" % (jc.jc_path, t)
                if not os.path.exists(template):
                    continue

                a = get_warden_template_abi_arch(template)
                v = get_warden_template_abi_version(template)
                template = "%s/.warden-template-%s" % (jc_dataset, t)

                #
                # The template is already on 9.2-RELEASE and
                # has the same architecture.
                #
                if v == freebsd_release and a == arch:
                    pass

                #
                # The template is either not on 9.2-RELEASE or
                # has a different architecture.
                #
                else:
                    newt = "%s/.warden-template-%s-%s-%s" % (jc_dataset, t, v, a)
                    newmp = "%s/.warden-template-%s-%s-%s" % (jc.jc_path, t, v, a)
                    oldmp = "%s/.warden-template-%s" % (jc.jc_path, t)

                    #
                    # Don't rename dataset or move directory if it already exists
                    #
                    if os.path.exists(newmp):
                        timestr = time.strftime("%Y%m%d%H%M%S")
                        newt = "%s/.warden-template-%s-%s-%s-%s" % \
                            (jc_dataset, t, v, a, timstr)
                        newmp = "%s/.warden-template-%s-%s-%s-%s" % \
                            (jc.jc_path, t, v, a, timestr)

                    #
                    # Set mountpoint to none so we can rename the directory
                    # the dataset is currently mounted on.
                    #
                    if not self.zfs_set_mountpoint(template, 'none'):
                        continue

                    #
                    # Rename the dataset, move the directory, set new mountpoint
                    #
                    if self.zfs_rename(template, newt):
                        if self.mv_template(oldmp, newmp):
                            newmp = newmp.replace("/mnt", "")
                            self.zfs_set_mountpoint(newt, newmp)

    def backwards(self, orm):
        templates = ['pluginjail', 'portjail', 'standard']
        arch = platform.architecture()
        if arch[0] == '64bit':
            arch = 'x64'
        else:
            arch = 'x86'

        for t in templates:
            t = orm['jails.Jailtemplate'].objects.filter(jt_name='%s' % t)[0]
            t.jt_url = "%s/freenas-%s.tgz" % \
                 (get_jails_index(release='latest', arch=arch), t)
            t.save()

    models = {
        u'jails.jails': {
            'Meta': {'object_name': 'Jails'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jail_alias_bridge_ipv4': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_alias_bridge_ipv6': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_alias_ipv4': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_alias_ipv6': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_autostart': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'max_length': '120'}),
            'jail_bridge_ipv4': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_bridge_ipv6': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_defaultrouter_ipv4': ('django.db.models.fields.GenericIPAddressField', [], {'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'jail_defaultrouter_ipv6': ('django.db.models.fields.GenericIPAddressField', [], {'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'jail_host': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jail_ipv4': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_ipv6': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_mac': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'jail_nat': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'jail_status': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jail_type': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'jail_vnet': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'max_length': '120'})
        },
        u'jails.jailsconfiguration': {
            'Meta': {'object_name': 'JailsConfiguration'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jc_collectionurl': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'jc_ipv4_network': ('freenasUI.freeadmin.models.fields.Network4Field', [], {'max_length': '18', 'blank': 'True'}),
            'jc_ipv4_network_end': ('freenasUI.freeadmin.models.fields.Network4Field', [], {'max_length': '18', 'blank': 'True'}),
            'jc_ipv4_network_start': ('freenasUI.freeadmin.models.fields.Network4Field', [], {'max_length': '18', 'blank': 'True'}),
            'jc_ipv6_network': ('freenasUI.freeadmin.models.fields.Network6Field', [], {'max_length': '43', 'blank': 'True'}),
            'jc_ipv6_network_end': ('freenasUI.freeadmin.models.fields.Network6Field', [], {'max_length': '43', 'blank': 'True'}),
            'jc_ipv6_network_start': ('freenasUI.freeadmin.models.fields.Network6Field', [], {'max_length': '43', 'blank': 'True'}),
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
            'readonly': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'source': ('django.db.models.fields.CharField', [], {'max_length': '300'})
        }
    }

    complete_apps = ['jails']
    symmetrical = True
