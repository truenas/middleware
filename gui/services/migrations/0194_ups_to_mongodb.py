# -*- coding: utf-8 -*-
import os
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models

from datastore import get_default_datastore
from datastore.config import ConfigStore

class Migration(DataMigration):

    def forwards(self, orm):

        # Skip for install time, we only care for upgrades here
        if 'FREENAS_INSTALL' in os.environ:
            return

        ds = get_default_datastore()
        cs = ConfigStore(ds)

        ups = orm['services.UPS'].objects.all()[0]
        svc = orm['services.services'].objects.filter(srv_service='ups')
        svc = svc[0] if svc.exists() else None

        if svc:
            cs.set('service.ups.enable', svc.srv_enable)

        cs.set('service.ups.mode', ups.ups_mode.upper())
        cs.set('service.ups.identifier', ups.ups_identifier)
        cs.set('service.ups.remote_host', ups.ups_remotehost)
        cs.set('service.ups.remote_port', ups.ups_remoteport)
        cs.set('service.ups.driver', ups.ups_driver.split('$')[0])
        cs.set('service.ups.driver_port', ups.ups_port)
        cs.set('service.ups.auxiliary', ups.ups_options or None)
        cs.set('service.ups.description', ups.ups_description or None)
        cs.set('service.ups.shutdown_mode', ups.ups_shutdown.upper())
        cs.set('service.ups.shutdown_timer', ups.ups_shutdowntimer)
        cs.set('service.ups.monitor_user', ups.ups_monuser)
        cs.set('service.ups.monitor_password', ups.ups_monpwd)
        cs.set('service.ups.auxiliary_users', ups.ups_extrausers or None)
        cs.set('service.ups.monitor_remote', ups.ups_rmonitor)
        cs.set('service.ups.email_notify', ups.ups_emailnotify)
        cs.set('service.ups.email_recipients', ups.ups_toemail or [])
        cs.set('service.ups.email_subject', ups.ups_subject)
        cs.set('service.ups.powerdown', ups.ups_powerdown)

    def backwards(self, orm):
        "Write your backwards methods here."

    models = {
        u'directoryservice.kerberosrealm': {
            'Meta': {'object_name': 'KerberosRealm'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'krb_admin_server': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'krb_kdc': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'krb_kpasswd_server': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'krb_realm': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'})
        },
        u'services.afp': {
            'Meta': {'object_name': 'AFP'},
            'afp_srv_bindip': ('freenasUI.freeadmin.models.fields.ListField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'afp_srv_connections_limit': ('django.db.models.fields.IntegerField', [], {'default': '50', 'max_length': '120'}),
            'afp_srv_dbpath': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'afp_srv_global_aux': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'afp_srv_guest': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_srv_guest_user': ('freenasUI.freeadmin.models.fields.UserField', [], {'default': "'nobody'", 'max_length': '120'}),
            'afp_srv_homedir': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'afp_srv_homedir_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_srv_homename': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'services.cifs': {
            'Meta': {'object_name': 'CIFS'},
            'cifs_SID': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cifs_srv_aio_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_aio_rs': ('django.db.models.fields.IntegerField', [], {'default': '4096', 'max_length': '120'}),
            'cifs_srv_aio_ws': ('django.db.models.fields.IntegerField', [], {'default': '4096', 'max_length': '120'}),
            'cifs_srv_allow_execute_always': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cifs_srv_bindip': ('freenasUI.freeadmin.models.fields.MultiSelectField', [], {'max_length': '250', 'null': 'True', 'blank': 'True'}),
            'cifs_srv_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_dirmask': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_domain_logons': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_doscharset': ('django.db.models.fields.CharField', [], {'default': "'CP437'", 'max_length': '120'}),
            'cifs_srv_filemask': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_guest': ('freenasUI.freeadmin.models.fields.UserField', [], {'default': "'nobody'", 'max_length': '120'}),
            'cifs_srv_hostlookup': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cifs_srv_localmaster': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_loglevel': ('django.db.models.fields.CharField', [], {'default': "'0'", 'max_length': '120'}),
            'cifs_srv_max_protocol': ('django.db.models.fields.CharField', [], {'default': "'SMB2'", 'max_length': '120'}),
            'cifs_srv_min_protocol': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_netbiosname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'cifs_srv_nullpw': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_obey_pam_restrictions': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cifs_srv_smb_options': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'cifs_srv_syslog': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_timeserver': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_unixcharset': ('django.db.models.fields.CharField', [], {'default': "'UTF-8'", 'max_length': '120'}),
            'cifs_srv_unixext': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cifs_srv_workgroup': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'cifs_srv_zeroconf': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'services.domaincontroller': {
            'Meta': {'object_name': 'DomainController'},
            'dc_dns_backend': ('django.db.models.fields.CharField', [], {'default': "'SAMBA_INTERNAL'", 'max_length': '120'}),
            'dc_dns_forwarder': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'dc_domain': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'dc_forest_level': ('django.db.models.fields.CharField', [], {'default': "'2003'", 'max_length': '120'}),
            'dc_kerberos_realm': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['directoryservice.KerberosRealm']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'dc_passwd': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'dc_realm': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'dc_role': ('django.db.models.fields.CharField', [], {'default': "'dc'", 'max_length': '120'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'services.dynamicdns': {
            'Meta': {'object_name': 'DynamicDNS'},
            'ddns_domain': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ddns_fupdateperiod': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ddns_ipserver': ('django.db.models.fields.CharField', [], {'default': "'checkip.dyndns.org:80 /.'", 'max_length': '150', 'blank': 'True'}),
            'ddns_options': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ddns_password': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ddns_provider': ('django.db.models.fields.CharField', [], {'default': "'dyndns@dyndns.org'", 'max_length': '120', 'blank': 'True'}),
            'ddns_updateperiod': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ddns_username': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'services.fiberchanneltotarget': {
            'Meta': {'object_name': 'FiberChannelToTarget'},
            'fc_port': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'fc_target': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['services.iSCSITarget']", 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'services.ftp': {
            'Meta': {'object_name': 'FTP'},
            'ftp_anonpath': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
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
            'ftp_ssltls_certificate': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['system.Certificate']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'ftp_timeout': ('django.db.models.fields.PositiveIntegerField', [], {'default': '120'}),
            'ftp_tls': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_tls_opt_allow_client_renegotiations': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_tls_opt_allow_dot_login': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_tls_opt_allow_per_user': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_tls_opt_common_name_required': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_tls_opt_dns_name_required': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_tls_opt_enable_diags': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_tls_opt_export_cert_data': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_tls_opt_ip_address_required': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_tls_opt_no_cert_request': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_tls_opt_no_empty_fragments': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_tls_opt_no_session_reuse_required': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_tls_opt_stdenvvars': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_tls_policy': ('django.db.models.fields.CharField', [], {'default': "'on'", 'max_length': '120'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'services.iscsitarget': {
            'Meta': {'ordering': "['iscsi_target_name']", 'object_name': 'iSCSITarget'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target_alias': ('django.db.models.fields.CharField', [], {'max_length': '120', 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'iscsi_target_mode': ('django.db.models.fields.CharField', [], {'default': "'iscsi'", 'max_length': '20'}),
            'iscsi_target_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'})
        },
        u'services.iscsitargetauthcredential': {
            'Meta': {'object_name': 'iSCSITargetAuthCredential'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target_auth_peersecret': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'iscsi_target_auth_peeruser': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'iscsi_target_auth_secret': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_target_auth_tag': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'iscsi_target_auth_user': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        u'services.iscsitargetauthorizedinitiator': {
            'Meta': {'object_name': 'iSCSITargetAuthorizedInitiator'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target_initiator_auth_network': ('django.db.models.fields.TextField', [], {'default': "'ALL'", 'max_length': '2048'}),
            'iscsi_target_initiator_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'iscsi_target_initiator_initiators': ('django.db.models.fields.TextField', [], {'default': "'ALL'", 'max_length': '2048'}),
            'iscsi_target_initiator_tag': ('django.db.models.fields.IntegerField', [], {'default': '1', 'unique': 'True'})
        },
        u'services.iscsitargetextent': {
            'Meta': {'ordering': "['iscsi_target_extent_name']", 'object_name': 'iSCSITargetExtent'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target_extent_avail_threshold': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'iscsi_target_extent_blocksize': ('django.db.models.fields.IntegerField', [], {'default': '512', 'max_length': '4'}),
            'iscsi_target_extent_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'iscsi_target_extent_filesize': ('django.db.models.fields.CharField', [], {'default': '0', 'max_length': '120'}),
            'iscsi_target_extent_insecure_tpc': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'iscsi_target_extent_naa': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '34', 'blank': 'True'}),
            'iscsi_target_extent_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'iscsi_target_extent_path': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_target_extent_pblocksize': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'iscsi_target_extent_rpm': ('django.db.models.fields.CharField', [], {'default': "u'SSD'", 'max_length': '20'}),
            'iscsi_target_extent_serial': ('django.db.models.fields.CharField', [], {'default': "'10000001'", 'max_length': '16'}),
            'iscsi_target_extent_type': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_target_extent_xen': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'services.iscsitargetglobalconfiguration': {
            'Meta': {'object_name': 'iSCSITargetGlobalConfiguration'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_basename': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_isns_servers': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'iscsi_pool_avail_threshold': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'})
        },
        u'services.iscsitargetgroups': {
            'Meta': {'unique_together': "(('iscsi_target', 'iscsi_target_portalgroup'),)", 'object_name': 'iSCSITargetGroups'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['services.iSCSITarget']"}),
            'iscsi_target_authgroup': ('django.db.models.fields.IntegerField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'iscsi_target_authtype': ('django.db.models.fields.CharField', [], {'default': "'None'", 'max_length': '120'}),
            'iscsi_target_initialdigest': ('django.db.models.fields.CharField', [], {'default': "'Auto'", 'max_length': '120'}),
            'iscsi_target_initiatorgroup': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['services.iSCSITargetAuthorizedInitiator']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'iscsi_target_portalgroup': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['services.iSCSITargetPortal']"})
        },
        u'services.iscsitargetportal': {
            'Meta': {'object_name': 'iSCSITargetPortal'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target_portal_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'iscsi_target_portal_discoveryauthgroup': ('django.db.models.fields.IntegerField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'iscsi_target_portal_discoveryauthmethod': ('django.db.models.fields.CharField', [], {'default': "'None'", 'max_length': '120'}),
            'iscsi_target_portal_tag': ('django.db.models.fields.IntegerField', [], {'default': '1', 'max_length': '120'})
        },
        u'services.iscsitargetportalip': {
            'Meta': {'unique_together': "(('iscsi_target_portalip_ip', 'iscsi_target_portalip_port'),)", 'object_name': 'iSCSITargetPortalIP'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target_portalip_ip': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'iscsi_target_portalip_port': ('django.db.models.fields.SmallIntegerField', [], {'default': '3260'}),
            'iscsi_target_portalip_portal': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'ips'", 'to': u"orm['services.iSCSITargetPortal']"})
        },
        u'services.iscsitargettoextent': {
            'Meta': {'ordering': "['iscsi_target', 'iscsi_lunid']", 'unique_together': "(('iscsi_target', 'iscsi_extent'),)", 'object_name': 'iSCSITargetToExtent'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_extent': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['services.iSCSITargetExtent']"}),
            'iscsi_lunid': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'iscsi_target': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['services.iSCSITarget']"})
        },
        u'services.lldp': {
            'Meta': {'object_name': 'LLDP'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lldp_country': ('django.db.models.fields.CharField', [], {'max_length': '2', 'blank': 'True'}),
            'lldp_intdesc': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'lldp_location': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'})
        },
        u'services.nfs': {
            'Meta': {'object_name': 'NFS'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nfs_srv_allow_nonroot': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nfs_srv_bindip': ('django.db.models.fields.CharField', [], {'max_length': '250', 'blank': 'True'}),
            'nfs_srv_mountd_port': ('django.db.models.fields.SmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'nfs_srv_rpclockd_port': ('django.db.models.fields.SmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'nfs_srv_rpcstatd_port': ('django.db.models.fields.SmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'nfs_srv_servers': ('django.db.models.fields.PositiveIntegerField', [], {'default': '4'}),
            'nfs_srv_udp': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nfs_srv_v4': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nfs_srv_v4_krb': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'services.rpctoken': {
            'Meta': {'object_name': 'RPCToken'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'secret': ('django.db.models.fields.CharField', [], {'max_length': '1024'})
        },
        u'services.rsyncd': {
            'Meta': {'object_name': 'Rsyncd'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'rsyncd_auxiliary': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'rsyncd_port': ('django.db.models.fields.IntegerField', [], {'default': '873'})
        },
        u'services.rsyncmod': {
            'Meta': {'ordering': "['rsyncmod_name']", 'object_name': 'RsyncMod'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'rsyncmod_auxiliary': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'rsyncmod_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'rsyncmod_group': ('freenasUI.freeadmin.models.fields.GroupField', [], {'default': "'nobody'", 'max_length': '120'}),
            'rsyncmod_hostsallow': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'rsyncmod_hostsdeny': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'rsyncmod_maxconn': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'rsyncmod_mode': ('django.db.models.fields.CharField', [], {'default': "'rw'", 'max_length': '120'}),
            'rsyncmod_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'rsyncmod_path': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255'}),
            'rsyncmod_user': ('freenasUI.freeadmin.models.fields.UserField', [], {'default': "'nobody'", 'max_length': '120'})
        },
        u'services.services': {
            'Meta': {'object_name': 'services'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'srv_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'srv_service': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        u'services.smart': {
            'Meta': {'object_name': 'SMART'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'smart_critical': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'smart_difference': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'smart_email': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'smart_informational': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'smart_interval': ('django.db.models.fields.IntegerField', [], {'default': '30'}),
            'smart_powermode': ('django.db.models.fields.CharField', [], {'default': "'never'", 'max_length': '60'})
        },
        u'services.snmp': {
            'Meta': {'object_name': 'SNMP'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'snmp_community': ('django.db.models.fields.CharField', [], {'default': "'public'", 'max_length': '120', 'blank': 'True'}),
            'snmp_contact': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'snmp_location': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'snmp_options': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'snmp_traps': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'snmp_v3': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'snmp_v3_authtype': ('django.db.models.fields.CharField', [], {'default': "'SHA'", 'max_length': '3', 'blank': 'True'}),
            'snmp_v3_password': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'snmp_v3_privpassphrase': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'snmp_v3_privproto': ('django.db.models.fields.CharField', [], {'max_length': '3', 'null': 'True', 'blank': 'True'}),
            'snmp_v3_username': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'})
        },
        u'services.ssh': {
            'Meta': {'object_name': 'SSH'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ssh_compression': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ssh_host_dsa_key': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_dsa_key_cert_pub': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_dsa_key_pub': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_ecdsa_key': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_ecdsa_key_cert_pub': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_ecdsa_key_pub': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_ed25519_key': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_ed25519_key_cert_pub': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_ed25519_key_pub': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_key': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_key_pub': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_rsa_key': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_rsa_key_cert_pub': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_host_rsa_key_pub': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'ssh_options': ('django.db.models.fields.TextField', [], {'max_length': '120', 'blank': 'True'}),
            'ssh_passwordauth': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ssh_privatekey': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'blank': 'True'}),
            'ssh_rootlogin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ssh_sftp_log_facility': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'ssh_sftp_log_level': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'ssh_tcpfwd': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ssh_tcpport': ('django.db.models.fields.PositiveIntegerField', [], {'default': '22'})
        },
        u'services.tftp': {
            'Meta': {'object_name': 'TFTP'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'tftp_directory': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255'}),
            'tftp_newfiles': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'tftp_options': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'tftp_port': ('django.db.models.fields.PositiveIntegerField', [], {'default': '69'}),
            'tftp_umask': ('django.db.models.fields.CharField', [], {'default': "'022'", 'max_length': '120'}),
            'tftp_username': ('freenasUI.freeadmin.models.fields.UserField', [], {'default': "'nobody'", 'max_length': '120'})
        },
        u'services.ups': {
            'Meta': {'object_name': 'UPS'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ups_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ups_driver': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ups_emailnotify': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ups_extrausers': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ups_identifier': ('django.db.models.fields.CharField', [], {'default': "'ups'", 'max_length': '120'}),
            'ups_mode': ('django.db.models.fields.CharField', [], {'default': "'master'", 'max_length': '6'}),
            'ups_monpwd': ('django.db.models.fields.CharField', [], {'default': "'fixmepass'", 'max_length': '30'}),
            'ups_monuser': ('django.db.models.fields.CharField', [], {'default': "'upsmon'", 'max_length': '50'}),
            'ups_options': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ups_port': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ups_powerdown': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'ups_remotehost': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'ups_remoteport': ('django.db.models.fields.IntegerField', [], {'default': '3493', 'blank': 'True'}),
            'ups_rmonitor': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ups_shutdown': ('django.db.models.fields.CharField', [], {'default': "'batt'", 'max_length': '120'}),
            'ups_shutdowntimer': ('django.db.models.fields.IntegerField', [], {'default': '30'}),
            'ups_subject': ('django.db.models.fields.CharField', [], {'default': "'UPS report generated by %h'", 'max_length': '120'}),
            'ups_toemail': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'})
        },
        u'services.webdav': {
            'Meta': {'object_name': 'WebDAV'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'webdav_certssl': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['system.Certificate']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'webdav_htauth': ('django.db.models.fields.CharField', [], {'default': "'digest'", 'max_length': '120'}),
            'webdav_password': ('django.db.models.fields.CharField', [], {'default': "'davtest'", 'max_length': '120'}),
            'webdav_protocol': ('django.db.models.fields.CharField', [], {'default': "'http'", 'max_length': '120'}),
            'webdav_tcpport': ('django.db.models.fields.PositiveIntegerField', [], {'default': '8080'}),
            'webdav_tcpportssl': ('django.db.models.fields.PositiveIntegerField', [], {'default': '8081'})
        },
        u'system.certificate': {
            'Meta': {'object_name': 'Certificate'},
            'cert_CSR': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_CSR_path': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'cert_DN': ('django.db.models.fields.CharField', [], {'max_length': '2000', 'blank': 'True'}),
            'cert_certificate': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_certificate_path': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'cert_city': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_common': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_country': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_digest_algorithm': ('django.db.models.fields.CharField', [], {'default': "'SHA256'", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_email': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_key_length': ('django.db.models.fields.IntegerField', [], {'default': '2048', 'null': 'True', 'blank': 'True'}),
            'cert_lifetime': ('django.db.models.fields.IntegerField', [], {'default': '3650', 'null': 'True', 'blank': 'True'}),
            'cert_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'cert_organization': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_privatekey': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_privatekey_path': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'cert_serial': ('django.db.models.fields.IntegerField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_signedby': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['system.CertificateAuthority']", 'null': 'True', 'blank': 'True'}),
            'cert_state': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_type': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'cert_valid_from': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'cert_valid_until': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'id': ('django.db.models.fields.CharField', [], {'max_length': '120', 'primary_key': 'True'})
        },
        u'system.certificateauthority': {
            'Meta': {'object_name': 'CertificateAuthority'},
            'cert_CSR': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_CSR_path': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'cert_DN': ('django.db.models.fields.CharField', [], {'max_length': '2000', 'blank': 'True'}),
            'cert_certificate': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_certificate_path': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'cert_city': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_common': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_country': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_digest_algorithm': ('django.db.models.fields.CharField', [], {'default': "'SHA256'", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_email': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_key_length': ('django.db.models.fields.IntegerField', [], {'default': '2048', 'null': 'True', 'blank': 'True'}),
            'cert_lifetime': ('django.db.models.fields.IntegerField', [], {'default': '3650', 'null': 'True', 'blank': 'True'}),
            'cert_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'cert_organization': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_privatekey': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_privatekey_path': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'cert_serial': ('django.db.models.fields.IntegerField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_signedby': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['system.CertificateAuthority']", 'null': 'True', 'blank': 'True'}),
            'cert_state': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_type': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'cert_valid_from': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'cert_valid_until': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'id': ('django.db.models.fields.CharField', [], {'max_length': '120', 'primary_key': 'True'})
        }
    }

    complete_apps = ['services']
    symmetrical = True
