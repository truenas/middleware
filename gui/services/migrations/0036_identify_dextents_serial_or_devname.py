# encoding: utf-8
from subprocess import Popen, PIPE
import datetime
import re
from south.db import db
from south.v2 import DataMigration
from django.db import models

def serial_from_device(self, devname):
    p1 = Popen(["/usr/local/sbin/smartctl", "-i", "/dev/%s" % devname], stdout=PIPE)
    output = p1.communicate()[0]
    search = re.search(r'^Serial Number:[ \t\s]+(?P<serial>.+)', output, re.I|re.M)
    if search:
        return search.group("serial")
    return None

class Migration(DataMigration):

    def forwards(self, orm):
        "Write your forwards methods here."
        for d in orm.iSCSITargetExtent.objects.filter(iscsi_target_extent_type="Disk"):
            try:
                disk = orm['storage.Disk'].objects.get(pk=d.iscsi_target_extent_path)
                if disk.disk_identifier.startswith('{label}label/extent_'):
                    devname = disk.disk_identifier.split('{label}label/extent_')[1]
                    serial = serial_from_device(devname)
                    if serial:
                        disk.disk_identifier = "{serial}%s" % serial
                    else:
                        disk.disk_identifier = "{devicename}%s" % devname
                    disk.save()
            except:
                pass

    def backwards(self, orm):
        "Write your backwards methods here."


    models = {
        'services.activedirectory': {
            'Meta': {'object_name': 'ActiveDirectory'},
            'ad_adminname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_adminpw': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_dcname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_domainname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_netbiosname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_workgroup': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'services.afp': {
            'Meta': {'object_name': 'AFP'},
            'afp_srv_ddp': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_srv_guest': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_srv_guest_user': ('freenasUI.freeadmin.models.UserField', [], {'default': "'nobody'", 'max_length': '120'}),
            'afp_srv_local': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_srv_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'services.cifs': {
            'Meta': {'object_name': 'CIFS'},
            'cifs_srv_aio_enable': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cifs_srv_aio_rs': ('django.db.models.fields.IntegerField', [], {'default': '1', 'max_length': '120'}),
            'cifs_srv_aio_ws': ('django.db.models.fields.IntegerField', [], {'default': '1', 'max_length': '120'}),
            'cifs_srv_authmodel': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'cifs_srv_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_dirmask': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_dosattr': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_doscharset': ('django.db.models.fields.CharField', [], {'default': "'CP437'", 'max_length': '120'}),
            'cifs_srv_easupport': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_filemask': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_guest': ('freenasUI.freeadmin.models.UserField', [], {'default': "'nobody'", 'max_length': '120'}),
            'cifs_srv_guestok': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_guestonly': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_homedir': ('freenasUI.freeadmin.models.PathField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'cifs_srv_homedir_browseable_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_homedir_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_largerw': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_localmaster': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_loglevel': ('django.db.models.fields.CharField', [], {'default': "'Minimum'", 'max_length': '120'}),
            'cifs_srv_netbiosname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'cifs_srv_nullpw': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_sendfile': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_smb_options': ('django.db.models.fields.TextField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_timeserver': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_unixcharset': ('django.db.models.fields.CharField', [], {'default': "'UTF-8'", 'max_length': '120'}),
            'cifs_srv_workgroup': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'services.dynamicdns': {
            'Meta': {'object_name': 'DynamicDNS'},
            'ddns_domain': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ddns_fupdateperiod': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ddns_options': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ddns_password': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ddns_provider': ('django.db.models.fields.CharField', [], {'default': "'dyndns'", 'max_length': '120'}),
            'ddns_updateperiod': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ddns_username': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'services.ftp': {
            'Meta': {'object_name': 'FTP'},
            'ftp_anonpath': ('freenasUI.freeadmin.models.PathField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'ftp_anonuserbw': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'ftp_anonuserdlbw': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'ftp_banner': ('django.db.models.fields.TextField', [], {'max_length': '120', 'blank': 'True'}),
            'ftp_clients': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'ftp_defaultroot': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_dirmask': ('django.db.models.fields.CharField', [], {'default': "'077'", 'max_length': '3'}),
            'ftp_filemask': ('django.db.models.fields.CharField', [], {'default': "'077'", 'max_length': '3'}),
            'ftp_fxp': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_ident': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_ipconnections': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'ftp_localuserbw': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'ftp_localuserdlbw': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'ftp_loginattempt': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'ftp_masqaddress': ('django.db.models.fields.IPAddressField', [], {'max_length': '15', 'blank': 'True'}),
            'ftp_onlyanonymous': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_onlylocal': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_options': ('django.db.models.fields.TextField', [], {'max_length': '120', 'blank': 'True'}),
            'ftp_passiveportsmax': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'ftp_passiveportsmin': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'ftp_port': ('django.db.models.fields.PositiveIntegerField', [], {'default': '21'}),
            'ftp_resume': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_reversedns': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_rootlogin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_ssltls': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_timeout': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'services.iscsitarget': {
            'Meta': {'object_name': 'iSCSITarget'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target_alias': ('django.db.models.fields.CharField', [], {'max_length': '120', 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'iscsi_target_authgroup': ('django.db.models.fields.IntegerField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'iscsi_target_authtype': ('django.db.models.fields.CharField', [], {'default': "'Auto'", 'max_length': '120'}),
            'iscsi_target_flags': ('django.db.models.fields.CharField', [], {'default': "'rw'", 'max_length': '120'}),
            'iscsi_target_initialdigest': ('django.db.models.fields.CharField', [], {'default': "'Auto'", 'max_length': '120'}),
            'iscsi_target_initiatorgroup': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['services.iSCSITargetAuthorizedInitiator']"}),
            'iscsi_target_logical_blocksize': ('django.db.models.fields.IntegerField', [], {'default': '512', 'max_length': '3'}),
            'iscsi_target_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'iscsi_target_portalgroup': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['services.iSCSITargetPortal']"}),
            'iscsi_target_queue_depth': ('django.db.models.fields.IntegerField', [], {'default': '32', 'max_length': '3'}),
            'iscsi_target_serial': ('django.db.models.fields.CharField', [], {'default': "'10000001'", 'max_length': '16'}),
            'iscsi_target_type': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'services.iscsitargetauthcredential': {
            'Meta': {'object_name': 'iSCSITargetAuthCredential'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target_auth_peersecret': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_target_auth_peeruser': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'iscsi_target_auth_secret': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_target_auth_tag': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'iscsi_target_auth_user': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'services.iscsitargetauthorizedinitiator': {
            'Meta': {'object_name': 'iSCSITargetAuthorizedInitiator'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target_initiator_auth_network': ('django.db.models.fields.TextField', [], {'default': "'ALL'", 'max_length': '2048'}),
            'iscsi_target_initiator_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'iscsi_target_initiator_initiators': ('django.db.models.fields.TextField', [], {'default': "'ALL'", 'max_length': '2048'}),
            'iscsi_target_initiator_tag': ('django.db.models.fields.IntegerField', [], {'default': '1', 'unique': 'True'})
        },
        'services.iscsitargetextent': {
            'Meta': {'object_name': 'iSCSITargetExtent'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target_extent_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'iscsi_target_extent_filesize': ('django.db.models.fields.CharField', [], {'default': '0', 'max_length': '120'}),
            'iscsi_target_extent_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'iscsi_target_extent_path': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_target_extent_type': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'services.iscsitargetglobalconfiguration': {
            'Meta': {'object_name': 'iSCSITargetGlobalConfiguration'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_basename': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_defaultt2r': ('django.db.models.fields.IntegerField', [], {'default': '60', 'max_length': '120'}),
            'iscsi_defaultt2w': ('django.db.models.fields.IntegerField', [], {'default': '2', 'max_length': '120'}),
            'iscsi_discoveryauthgroup': ('django.db.models.fields.IntegerField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'iscsi_discoveryauthmethod': ('django.db.models.fields.CharField', [], {'default': "'Auto'", 'max_length': '120'}),
            'iscsi_firstburst': ('django.db.models.fields.IntegerField', [], {'default': '65536', 'max_length': '120'}),
            'iscsi_iotimeout': ('django.db.models.fields.IntegerField', [], {'default': '30', 'max_length': '120'}),
            'iscsi_luc_authgroup': ('django.db.models.fields.IntegerField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'iscsi_luc_authmethod': ('django.db.models.fields.CharField', [], {'default': "'chap'", 'max_length': '120', 'blank': 'True'}),
            'iscsi_luc_authnetwork': ('django.db.models.fields.IPAddressField', [], {'default': "'255.255.255.0'", 'max_length': '15', 'blank': 'True'}),
            'iscsi_lucip': ('django.db.models.fields.IPAddressField', [], {'default': "'127.0.0.1'", 'max_length': '15', 'blank': 'True'}),
            'iscsi_lucport': ('django.db.models.fields.IntegerField', [], {'default': '3261', 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'iscsi_maxburst': ('django.db.models.fields.IntegerField', [], {'default': '262144', 'max_length': '120'}),
            'iscsi_maxconnect': ('django.db.models.fields.IntegerField', [], {'default': '8', 'max_length': '120'}),
            'iscsi_maxoutstandingr2t': ('django.db.models.fields.IntegerField', [], {'default': '16', 'max_length': '120'}),
            'iscsi_maxrecdata': ('django.db.models.fields.IntegerField', [], {'default': '262144', 'max_length': '120'}),
            'iscsi_maxsesh': ('django.db.models.fields.IntegerField', [], {'default': '16', 'max_length': '120'}),
            'iscsi_nopinint': ('django.db.models.fields.IntegerField', [], {'default': '20', 'max_length': '120'}),
            'iscsi_r2t': ('django.db.models.fields.IntegerField', [], {'default': '32', 'max_length': '120'}),
            'iscsi_toggleluc': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'services.iscsitargetportal': {
            'Meta': {'object_name': 'iSCSITargetPortal'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target_portal_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'iscsi_target_portal_listen': ('django.db.models.fields.TextField', [], {'default': "'0.0.0.0:3260'", 'max_length': '120'}),
            'iscsi_target_portal_tag': ('django.db.models.fields.IntegerField', [], {'default': '1', 'max_length': '120'})
        },
        'services.iscsitargettoextent': {
            'Meta': {'object_name': 'iSCSITargetToExtent'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_extent': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['services.iSCSITargetExtent']", 'unique': 'True'}),
            'iscsi_target': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['services.iSCSITarget']"})
        },
        'services.ldap': {
            'Meta': {'object_name': 'LDAP'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ldap_anonbind': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ldap_basedn': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_groupsuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_hostname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_machinesuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_options': ('django.db.models.fields.TextField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_passwordsuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_pwencryption': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ldap_rootbasedn': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_rootbindpw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_ssl': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_tls_cacertfile': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ldap_usersuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'})
        },
        'services.nfs': {
            'Meta': {'object_name': 'NFS'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nfs_srv_async': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nfs_srv_servers': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'services.rsyncd': {
            'Meta': {'object_name': 'Rsyncd'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'rsyncd_auxiliary': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'rsyncd_port': ('django.db.models.fields.IntegerField', [], {'default': '873'})
        },
        'services.rsyncmod': {
            'Meta': {'object_name': 'RsyncMod'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'rsyncmod_auxiliary': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'rsyncmod_comment': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'rsyncmod_group': ('freenasUI.freeadmin.models.GroupField', [], {'default': "'nobody'", 'max_length': '120', 'blank': 'True'}),
            'rsyncmod_hostsallow': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'rsyncmod_hostsdeny': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'rsyncmod_maxconn': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'rsyncmod_mode': ('django.db.models.fields.CharField', [], {'default': "'rw'", 'max_length': '120'}),
            'rsyncmod_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'rsyncmod_path': ('freenasUI.freeadmin.models.PathField', [], {'max_length': '255'}),
            'rsyncmod_user': ('freenasUI.freeadmin.models.UserField', [], {'default': "'nobody'", 'max_length': '120', 'blank': 'True'})
        },
        'services.services': {
            'Meta': {'object_name': 'services'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'srv_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'srv_service': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'services.smart': {
            'Meta': {'object_name': 'SMART'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'smart_critical': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'smart_difference': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'smart_email': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'smart_informal': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'smart_interval': ('django.db.models.fields.IntegerField', [], {'default': '30'}),
            'smart_powermode': ('django.db.models.fields.CharField', [], {'default': "'never'", 'max_length': '60'})
        },
        'services.snmp': {
            'Meta': {'object_name': 'SNMP'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'snmp_community': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'snmp_contact': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'snmp_location': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'snmp_options': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'snmp_traps': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'services.ssh': {
            'Meta': {'object_name': 'SSH'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ssh_compression': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ssh_host_dsa_key': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_dsa_key_pub': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_key': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_key_pub': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_rsa_key': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_rsa_key_pub': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_options': ('django.db.models.fields.TextField', [], {'max_length': '120', 'blank': 'True'}),
            'ssh_passwordauth': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ssh_privatekey': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'blank': 'True'}),
            'ssh_rootlogin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ssh_tcpfwd': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ssh_tcpport': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'services.tftp': {
            'Meta': {'object_name': 'TFTP'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'tftp_directory': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'tftp_newfiles': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'tftp_options': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'tftp_port': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'tftp_umask': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'tftp_username': ('freenasUI.freeadmin.models.UserField', [], {'default': "'nobody'", 'max_length': '120'})
        },
        'services.ups': {
            'Meta': {'object_name': 'UPS'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ups_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ups_driver': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ups_emailnotify': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ups_identifier': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ups_options': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ups_port': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ups_rmonitor': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ups_shutdown': ('django.db.models.fields.CharField', [], {'default': "'batt'", 'max_length': '120'}),
            'ups_shutdowntimer': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ups_subject': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ups_toemail': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'})
        },
        'storage.disk': {
            'Meta': {'object_name': 'Disk'},
            'disk_acousticlevel': ('django.db.models.fields.CharField', [], {'default': "'Disabled'", 'max_length': '120'}),
            'disk_advpowermgmt': ('django.db.models.fields.CharField', [], {'default': "'Disabled'", 'max_length': '120'}),
            'disk_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'disk_group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['storage.DiskGroup']"}),
            'disk_hddstandby': ('django.db.models.fields.CharField', [], {'default': "'Always On'", 'max_length': '120'}),
            'disk_identifier': ('django.db.models.fields.CharField', [], {'max_length': '42'}),
            'disk_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'disk_smartoptions': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'disk_togglesmart': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'disk_transfermode': ('django.db.models.fields.CharField', [], {'default': "'Auto'", 'max_length': '120'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'storage.diskgroup': {
            'Meta': {'object_name': 'DiskGroup'},
            'group_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'group_type': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'group_volume': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['storage.Volume']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'storage.mountpoint': {
            'Meta': {'object_name': 'MountPoint'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mp_ischild': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'mp_options': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True'}),
            'mp_path': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'mp_volume': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['storage.Volume']"})
        },
        'storage.replication': {
            'Meta': {'object_name': 'Replication'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'repl_lastsnapshot': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'repl_limit': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'repl_mountpoint': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['storage.MountPoint']"}),
            'repl_remote': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['storage.ReplRemote']"}),
            'repl_userepl': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'repl_zfs': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'storage.replremote': {
            'Meta': {'object_name': 'ReplRemote'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ssh_remote_hostkey': ('django.db.models.fields.CharField', [], {'max_length': '2048'}),
            'ssh_remote_hostname': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'storage.task': {
            'Meta': {'object_name': 'Task'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'task_begin': ('django.db.models.fields.TimeField', [], {'default': 'datetime.time(9, 0)'}),
            'task_byweekday': ('django.db.models.fields.CharField', [], {'default': "'1,2,3,4,5'", 'max_length': '120', 'blank': 'True'}),
            'task_end': ('django.db.models.fields.TimeField', [], {'default': 'datetime.time(18, 0)'}),
            'task_interval': ('django.db.models.fields.PositiveIntegerField', [], {'default': '60', 'max_length': '120'}),
            'task_mountpoint': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['storage.MountPoint']"}),
            'task_recursive': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'task_repeat_unit': ('django.db.models.fields.CharField', [], {'default': "'weekly'", 'max_length': '120'}),
            'task_ret_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '2'}),
            'task_ret_unit': ('django.db.models.fields.CharField', [], {'default': "'week'", 'max_length': '120'})
        },
        'storage.volume': {
            'Meta': {'object_name': 'Volume'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'vol_fstype': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'vol_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'})
        }
    }

    complete_apps = ['storage', 'services']
