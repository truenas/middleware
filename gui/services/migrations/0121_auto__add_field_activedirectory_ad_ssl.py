# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'ActiveDirectory.ad_ssl'
        db.add_column(u'services_activedirectory', 'ad_ssl',
                      self.gf('django.db.models.fields.CharField')(default='off', max_length=120),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'ActiveDirectory.ad_ssl'
        db.delete_column(u'services_activedirectory', 'ad_ssl')


    models = {
        u'services.activedirectory': {
            'Meta': {'object_name': 'ActiveDirectory'},
            'ad_allow_trusted_doms': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_bindname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_bindpw': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_dcname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_dns_timeout': ('django.db.models.fields.IntegerField', [], {'default': '10'}),
            'ad_domainname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_gcname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_keytab': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'ad_kpwdname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_krbname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_netbiosname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_ssl': ('django.db.models.fields.CharField', [], {'default': "'off'", 'max_length': '120'}),
            'ad_timeout': ('django.db.models.fields.IntegerField', [], {'default': '10'}),
            'ad_unix_extensions': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_use_default_domain': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'ad_use_keytab': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_verbose_logging': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_workgroup': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'services.afp': {
            'Meta': {'object_name': 'AFP'},
            'afp_srv_connections_limit': ('django.db.models.fields.IntegerField', [], {'default': '50', 'max_length': '120'}),
            'afp_srv_dbpath': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'afp_srv_guest': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_srv_guest_user': ('freenasUI.freeadmin.models.fields.UserField', [], {'default': "'nobody'", 'max_length': '120'}),
            'afp_srv_homedir': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'afp_srv_homedir_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'services.cifs': {
            'Meta': {'object_name': 'CIFS'},
            'cifs_srv_aio_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_aio_rs': ('django.db.models.fields.IntegerField', [], {'default': '4096', 'max_length': '120'}),
            'cifs_srv_aio_ws': ('django.db.models.fields.IntegerField', [], {'default': '4096', 'max_length': '120'}),
            'cifs_srv_allow_execute_always': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cifs_srv_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_dirmask': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_domain_logons': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_doscharset': ('django.db.models.fields.CharField', [], {'default': "'CP437'", 'max_length': '120'}),
            'cifs_srv_filemask': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_guest': ('freenasUI.freeadmin.models.fields.UserField', [], {'default': "'nobody'", 'max_length': '120'}),
            'cifs_srv_homedir': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'cifs_srv_homedir_aux': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'cifs_srv_homedir_browseable_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_homedir_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_hostlookup': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cifs_srv_localmaster': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_loglevel': ('django.db.models.fields.CharField', [], {'default': "'0'", 'max_length': '120'}),
            'cifs_srv_max_protocol': ('django.db.models.fields.CharField', [], {'default': "'SMB2'", 'max_length': '120'}),
            'cifs_srv_min_protocol': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_netbiosname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'cifs_srv_nullpw': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
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
            'dc_passwd': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'dc_realm': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'dc_role': ('django.db.models.fields.CharField', [], {'default': "'dc'", 'max_length': '120'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'services.dynamicdns': {
            'Meta': {'object_name': 'DynamicDNS'},
            'ddns_domain': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ddns_fupdateperiod': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ddns_ipserver': ('django.db.models.fields.CharField', [], {'max_length': '150', 'blank': 'True'}),
            'ddns_options': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ddns_password': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ddns_provider': ('django.db.models.fields.CharField', [], {'default': "'dyndns@dyndns.org'", 'max_length': '120', 'blank': 'True'}),
            'ddns_updateperiod': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ddns_username': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
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
            'ftp_ssltls_certfile': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
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
            'ftp_tls_opt_use_implicit_ssl': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_tls_policy': ('django.db.models.fields.CharField', [], {'default': "'on'", 'max_length': '120'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'services.iscsitarget': {
            'Meta': {'ordering': "['iscsi_target_name']", 'object_name': 'iSCSITarget'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target_alias': ('django.db.models.fields.CharField', [], {'max_length': '120', 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'iscsi_target_authgroup': ('django.db.models.fields.IntegerField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'iscsi_target_authtype': ('django.db.models.fields.CharField', [], {'default': "'Auto'", 'max_length': '120'}),
            'iscsi_target_flags': ('django.db.models.fields.CharField', [], {'default': "'rw'", 'max_length': '120'}),
            'iscsi_target_initialdigest': ('django.db.models.fields.CharField', [], {'default': "'Auto'", 'max_length': '120'}),
            'iscsi_target_initiatorgroup': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['services.iSCSITargetAuthorizedInitiator']"}),
            'iscsi_target_logical_blocksize': ('django.db.models.fields.IntegerField', [], {'default': '512', 'max_length': '3'}),
            'iscsi_target_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'iscsi_target_portalgroup': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['services.iSCSITargetPortal']"}),
            'iscsi_target_queue_depth': ('django.db.models.fields.IntegerField', [], {'default': '32', 'max_length': '3'}),
            'iscsi_target_serial': ('django.db.models.fields.CharField', [], {'default': "'10000001'", 'max_length': '16'}),
            'iscsi_target_type': ('django.db.models.fields.CharField', [], {'default': "'Disk'", 'max_length': '120'})
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
            'iscsi_target_extent_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'iscsi_target_extent_filesize': ('django.db.models.fields.CharField', [], {'default': '0', 'max_length': '120'}),
            'iscsi_target_extent_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'iscsi_target_extent_path': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_target_extent_type': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        u'services.iscsitargetglobalconfiguration': {
            'Meta': {'object_name': 'iSCSITargetGlobalConfiguration'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_basename': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_defaultt2r': ('django.db.models.fields.IntegerField', [], {'default': '60', 'max_length': '120'}),
            'iscsi_defaultt2w': ('django.db.models.fields.IntegerField', [], {'default': '2', 'max_length': '120'}),
            'iscsi_discoveryauthgroup': ('django.db.models.fields.IntegerField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'iscsi_discoveryauthmethod': ('django.db.models.fields.CharField', [], {'default': "'Auto'", 'max_length': '120'}),
            'iscsi_experimental_target': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'iscsi_firstburst': ('django.db.models.fields.IntegerField', [], {'default': '65536', 'max_length': '120'}),
            'iscsi_iotimeout': ('django.db.models.fields.IntegerField', [], {'default': '30', 'max_length': '120'}),
            'iscsi_luc_authgroup': ('django.db.models.fields.IntegerField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'iscsi_luc_authmethod': ('django.db.models.fields.CharField', [], {'default': "'CHAP'", 'max_length': '120', 'blank': 'True'}),
            'iscsi_luc_authnetwork': ('django.db.models.fields.CharField', [], {'default': "'127.0.0.0/8'", 'max_length': '120', 'blank': 'True'}),
            'iscsi_lucip': ('django.db.models.fields.IPAddressField', [], {'default': "'127.0.0.1'", 'max_length': '15', 'null': 'True', 'blank': 'True'}),
            'iscsi_lucport': ('django.db.models.fields.IntegerField', [], {'default': '3261', 'null': 'True', 'blank': 'True'}),
            'iscsi_maxburst': ('django.db.models.fields.IntegerField', [], {'default': '262144', 'max_length': '120'}),
            'iscsi_maxconnect': ('django.db.models.fields.IntegerField', [], {'default': '8', 'max_length': '120'}),
            'iscsi_maxoutstandingr2t': ('django.db.models.fields.IntegerField', [], {'default': '16', 'max_length': '120'}),
            'iscsi_maxrecdata': ('django.db.models.fields.IntegerField', [], {'default': '262144', 'max_length': '120'}),
            'iscsi_maxsesh': ('django.db.models.fields.IntegerField', [], {'default': '16', 'max_length': '120'}),
            'iscsi_multithreaded': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'iscsi_nopinint': ('django.db.models.fields.IntegerField', [], {'default': '20', 'max_length': '120'}),
            'iscsi_r2t': ('django.db.models.fields.IntegerField', [], {'default': '32', 'max_length': '120'}),
            'iscsi_toggleluc': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'services.iscsitargetportal': {
            'Meta': {'object_name': 'iSCSITargetPortal'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target_portal_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
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
            'Meta': {'object_name': 'iSCSITargetToExtent'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_extent': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['services.iSCSITargetExtent']", 'unique': 'True'}),
            'iscsi_lunid': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'iscsi_target': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['services.iSCSITarget']"})
        },
        u'services.ldap': {
            'Meta': {'object_name': 'LDAP'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ldap_anonbind': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ldap_basedn': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_groupsuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_hostname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_machinesuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_options': ('django.db.models.fields.TextField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_passwordsuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_pwencryption': ('django.db.models.fields.CharField', [], {'default': "'clear'", 'max_length': '120'}),
            'ldap_rootbasedn': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_rootbindpw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_ssl': ('django.db.models.fields.CharField', [], {'default': "'off'", 'max_length': '120'}),
            'ldap_tls_cacertfile': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ldap_usersuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'})
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
            'nfs_srv_udp': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'services.nis': {
            'Meta': {'object_name': 'NIS'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nis_domain': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'nis_manycast': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nis_secure_mode': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nis_servers': ('django.db.models.fields.CharField', [], {'max_length': '8192', 'blank': 'True'})
        },
        u'services.nt4': {
            'Meta': {'object_name': 'NT4'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nt4_adminname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'nt4_adminpw': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'nt4_dcname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'nt4_netbiosname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'nt4_workgroup': ('django.db.models.fields.CharField', [], {'max_length': '120'})
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
            'snmp_community': ('django.db.models.fields.CharField', [], {'default': "'public'", 'max_length': '120'}),
            'snmp_contact': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'snmp_location': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'snmp_options': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'snmp_traps': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'services.ssh': {
            'Meta': {'object_name': 'SSH'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
            'ups_remotehost': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'ups_remoteport': ('django.db.models.fields.IntegerField', [], {'default': '3493', 'blank': 'True'}),
            'ups_rmonitor': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ups_shutdown': ('django.db.models.fields.CharField', [], {'default': "'batt'", 'max_length': '120'}),
            'ups_shutdowntimer': ('django.db.models.fields.IntegerField', [], {'default': '30'}),
            'ups_subject': ('django.db.models.fields.CharField', [], {'default': "'UPS report generated by %h'", 'max_length': '120'}),
            'ups_toemail': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'})
        }
    }

    complete_apps = ['services']