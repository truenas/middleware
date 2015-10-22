# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models


class UPSDRIVER_CHOICES(object):
    "Populate choices from /usr/local/libexec/nut/driver.list"
    def __iter__(self):
        if os.path.exists("/usr/local/libexec/nut/driver.list"):
            with open('/usr/local/libexec/nut/driver.list', 'rb') as f:
                d = f.read()
            r = cStringIO.StringIO()
            for line in re.sub(r'[ \t]+', ' ', d, flags=re.M).split('\n'):
                r.write(line.strip() + '\n')
            r.seek(0)
            reader = csv.reader(r, delimiter=' ', quotechar='"')
            for row in reader:
                if len(row) == 0 or row[0].startswith('#'):
                    continue
                if row[-2] == '#':
                    last = -3
                else:
                    last = -1
                if row[last].find(' (experimental)') != -1:
                    row[last] = row[last].replace(' (experimental)', '').strip()
                for i, field in enumerate(list(row)):
                    row[i] = field.decode('utf8')
                yield (u"$".join([row[last], row[3]]), u"%s (%s)" %
                       (u" ".join(row[0:last]), row[last]))


class Migration(DataMigration):

    def forwards(self, orm):
        "Write your forwards methods here."
        # Note: Remember to use orm['appname.ModelName'] rather than "from appname.models..."
        try:
            ups = orm['services.UPS'].objects.order_by('-id')[0]
            if not ups.ups_driver:
                return
            for choice, name in UPSDRIVER_CHOICES():
                if choice.split("$")[0] == ups.ups_driver:
                    ups.ups_driver = choice
                    ups.save()
                    break
        except:
            pass


    def backwards(self, orm):
        "Write your backwards methods here."

    models = {
        'services.activedirectory': {
            'Meta': {'object_name': 'ActiveDirectory'},
            'ad_adminname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_adminpw': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_allow_trusted_doms': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_dcname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_dns_timeout': ('django.db.models.fields.IntegerField', [], {'default': '10'}),
            'ad_domainname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_gcname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_kpwdname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_krbname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_netbiosname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_timeout': ('django.db.models.fields.IntegerField', [], {'default': '10'}),
            'ad_unix_extensions': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_use_default_domain': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'ad_verbose_logging': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_workgroup': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'services.afp': {
            'Meta': {'object_name': 'AFP'},
            'afp_srv_connections_limit': ('django.db.models.fields.IntegerField', [], {'default': '50', 'max_length': '120'}),
            'afp_srv_guest': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_srv_guest_user': ('freenasUI.freeadmin.models.UserField', [], {'default': "'nobody'", 'max_length': '120'}),
            'afp_srv_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'services.cifs': {
            'Meta': {'object_name': 'CIFS'},
            'cifs_srv_aio_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_aio_rs': ('django.db.models.fields.IntegerField', [], {'default': '4096', 'max_length': '120'}),
            'cifs_srv_aio_ws': ('django.db.models.fields.IntegerField', [], {'default': '4096', 'max_length': '120'}),
            'cifs_srv_authmodel': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'cifs_srv_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_dirmask': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_dosattr': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_doscharset': ('django.db.models.fields.CharField', [], {'default': "'CP437'", 'max_length': '120'}),
            'cifs_srv_easupport': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_filemask': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_guest': ('freenasUI.freeadmin.models.UserField', [], {'default': "'nobody'", 'max_length': '120'}),
            'cifs_srv_homedir': ('freenasUI.freeadmin.models.PathField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'cifs_srv_homedir_aux': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'cifs_srv_homedir_browseable_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_homedir_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_hostlookup': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cifs_srv_largerw': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_localmaster': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_loglevel': ('django.db.models.fields.CharField', [], {'default': "'1'", 'max_length': '120'}),
            'cifs_srv_netbiosname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'cifs_srv_nullpw': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_sendfile': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_smb_options': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'cifs_srv_timeserver': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_unixcharset': ('django.db.models.fields.CharField', [], {'default': "'UTF-8'", 'max_length': '120'}),
            'cifs_srv_unixext': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cifs_srv_workgroup': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'cifs_srv_zeroconf': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'services.dynamicdns': {
            'Meta': {'object_name': 'DynamicDNS'},
            'ddns_domain': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ddns_fupdateperiod': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ddns_options': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ddns_password': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ddns_provider': ('django.db.models.fields.CharField', [], {'default': "'dyndns'", 'max_length': '120', 'blank': 'True'}),
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
            'ftp_clients': ('django.db.models.fields.PositiveIntegerField', [], {'default': '32'}),
            'ftp_defaultroot': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_dirmask': ('django.db.models.fields.CharField', [], {'default': "'077'", 'max_length': '3'}),
            'ftp_filemask': ('django.db.models.fields.CharField', [], {'default': "'077'", 'max_length': '3'}),
            'ftp_fxp': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_ident': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_ipconnections': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'ftp_localuserbw': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'ftp_localuserdlbw': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'ftp_loginattempt': ('django.db.models.fields.PositiveIntegerField', [], {'default': '3'}),
            'ftp_masqaddress': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
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
            'ftp_ssltls_certfile': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ftp_timeout': ('django.db.models.fields.PositiveIntegerField', [], {'default': '120'}),
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
            'iscsi_target_type': ('django.db.models.fields.CharField', [], {'default': "'Disk'", 'max_length': '120'})
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
            'Meta': {'ordering': "['iscsi_target_extent_name']", 'object_name': 'iSCSITargetExtent'},
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
            'iscsi_luc_authnetwork': ('django.db.models.fields.CharField', [], {'default': "'127.0.0.0/8'", 'max_length': '120', 'blank': 'True'}),
            'iscsi_lucip': ('django.db.models.fields.IPAddressField', [], {'default': "'127.0.0.1'", 'max_length': '15', 'null': 'True', 'blank': 'True'}),
            'iscsi_lucport': ('django.db.models.fields.IntegerField', [], {'default': '3261', 'null': 'True', 'blank': 'True'}),
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
            'iscsi_target_portal_tag': ('django.db.models.fields.IntegerField', [], {'default': '1', 'max_length': '120'})
        },
        'services.iscsitargetportalip': {
            'Meta': {'unique_together': "(('iscsi_target_portalip_ip', 'iscsi_target_portalip_port'),)", 'object_name': 'iSCSITargetPortalIP'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target_portalip_ip': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'iscsi_target_portalip_port': ('django.db.models.fields.SmallIntegerField', [], {'default': '3260'}),
            'iscsi_target_portalip_portal': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['services.iSCSITargetPortal']"})
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
            'ldap_ssl': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ldap_tls_cacertfile': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ldap_usersuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'})
        },
        'services.nfs': {
            'Meta': {'object_name': 'NFS'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nfs_srv_allow_nonroot': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nfs_srv_async': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nfs_srv_bindip': ('django.db.models.fields.CharField', [], {'max_length': '250', 'blank': 'True'}),
            'nfs_srv_servers': ('django.db.models.fields.PositiveIntegerField', [], {'default': '4'})
        },
        'services.nis': {
            'Meta': {'object_name': 'NIS'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nis_domain': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'nis_manycast': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nis_secure_mode': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nis_servers': ('django.db.models.fields.CharField', [], {'max_length': '8192', 'blank': 'True'})
        },
        'services.nt4': {
            'Meta': {'object_name': 'NT4'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nt4_adminname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'nt4_adminpw': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'nt4_dcname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'nt4_netbiosname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'nt4_workgroup': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'services.pluginsjail': {
            'Meta': {'object_name': 'PluginsJail'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jail_ipv4address': ('freenasUI.contrib.IPAddressField.IPAddressField', [], {}),
            'jail_ipv4netmask': ('django.db.models.fields.CharField', [], {'max_length': '3'}),
            'jail_mac': ('freenasUI.freeadmin.models.MACField', [], {'default': "''", 'max_length': '17', 'blank': 'True'}),
            'jail_name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '120'}),
            'jail_path': ('freenasUI.freeadmin.models.PathField', [], {'max_length': '255'}),
            'plugins_path': ('freenasUI.freeadmin.models.PathField', [], {'max_length': '255'})
        },
        'services.rpctoken': {
            'Meta': {'object_name': 'RPCToken'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'secret': ('django.db.models.fields.CharField', [], {'max_length': '1024'})
        },
        'services.rsyncd': {
            'Meta': {'object_name': 'Rsyncd'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'rsyncd_auxiliary': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'rsyncd_port': ('django.db.models.fields.IntegerField', [], {'default': '873'})
        },
        'services.rsyncmod': {
            'Meta': {'ordering': "['rsyncmod_name']", 'object_name': 'RsyncMod'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'rsyncmod_auxiliary': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'rsyncmod_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
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
            'snmp_location': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'snmp_options': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'snmp_traps': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'services.ssh': {
            'Meta': {'object_name': 'SSH'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ssh_compression': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ssh_host_dsa_key': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_dsa_key_pub': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_ecdsa_key': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_ecdsa_key_pub': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_key': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_key_pub': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_rsa_key': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_rsa_key_pub': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_options': ('django.db.models.fields.TextField', [], {'max_length': '120', 'blank': 'True'}),
            'ssh_passwordauth': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ssh_privatekey': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'blank': 'True'}),
            'ssh_rootlogin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ssh_sftp_log_facility': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'ssh_sftp_log_level': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'ssh_tcpfwd': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ssh_tcpport': ('django.db.models.fields.PositiveIntegerField', [], {})
        },
        'services.tftp': {
            'Meta': {'object_name': 'TFTP'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'tftp_directory': ('freenasUI.freeadmin.models.PathField', [], {'max_length': '255'}),
            'tftp_newfiles': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'tftp_options': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'tftp_port': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'tftp_umask': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'tftp_username': ('freenasUI.freeadmin.models.UserField', [], {'default': "'nobody'", 'max_length': '120'})
        },
        'services.ups': {
            'Meta': {'object_name': 'UPS'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ups_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ups_driver': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ups_emailnotify': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ups_extrausers': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ups_identifier': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ups_masterpwd': ('django.db.models.fields.CharField', [], {'default': "'fixmepass'", 'max_length': '30'}),
            'ups_options': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ups_port': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ups_rmonitor': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ups_shutdown': ('django.db.models.fields.CharField', [], {'default': "'batt'", 'max_length': '120'}),
            'ups_shutdowntimer': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ups_subject': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ups_toemail': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'})
        }
    }

    complete_apps = ['services']
    symmetrical = True
