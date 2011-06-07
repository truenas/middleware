# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'SSH.ssh_host_dsa_key'
        db.add_column('services_ssh', 'ssh_host_dsa_key', self.gf('django.db.models.fields.TextField')(max_length=1024, null=True, blank=True), keep_default=False)

        # Adding field 'SSH.ssh_host_dsa_key_pub'
        db.add_column('services_ssh', 'ssh_host_dsa_key_pub', self.gf('django.db.models.fields.TextField')(max_length=1024, null=True, blank=True), keep_default=False)

        # Adding field 'SSH.ssh_host_key'
        db.add_column('services_ssh', 'ssh_host_key', self.gf('django.db.models.fields.TextField')(max_length=1024, null=True, blank=True), keep_default=False)

        # Adding field 'SSH.ssh_host_key_pub'
        db.add_column('services_ssh', 'ssh_host_key_pub', self.gf('django.db.models.fields.TextField')(max_length=1024, null=True, blank=True), keep_default=False)

        # Adding field 'SSH.ssh_host_rsa_key'
        db.add_column('services_ssh', 'ssh_host_rsa_key', self.gf('django.db.models.fields.TextField')(max_length=1024, null=True, blank=True), keep_default=False)

        # Adding field 'SSH.ssh_host_rsa_key_pub'
        db.add_column('services_ssh', 'ssh_host_rsa_key_pub', self.gf('django.db.models.fields.TextField')(max_length=1024, null=True, blank=True), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'SSH.ssh_host_dsa_key'
        db.delete_column('services_ssh', 'ssh_host_dsa_key')

        # Deleting field 'SSH.ssh_host_dsa_key_pub'
        db.delete_column('services_ssh', 'ssh_host_dsa_key_pub')

        # Deleting field 'SSH.ssh_host_key'
        db.delete_column('services_ssh', 'ssh_host_key')

        # Deleting field 'SSH.ssh_host_key_pub'
        db.delete_column('services_ssh', 'ssh_host_key_pub')

        # Deleting field 'SSH.ssh_host_rsa_key'
        db.delete_column('services_ssh', 'ssh_host_rsa_key')

        # Deleting field 'SSH.ssh_host_rsa_key_pub'
        db.delete_column('services_ssh', 'ssh_host_rsa_key_pub')


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
            'afp_srv_local': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'afp_srv_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'services.bittorrent': {
            'Meta': {'object_name': 'BitTorrent'},
            'bt_adminauth': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'bt_adminpass': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'bt_adminport': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'bt_adminuser': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'bt_configdir': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'bt_disthash': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bt_downloadbw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'bt_downloaddir': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'bt_encrypt': ('django.db.models.fields.CharField', [], {'default': "'preferred'", 'max_length': '120', 'blank': 'True'}),
            'bt_incompletedir': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'bt_options': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'bt_peerport': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'bt_pex': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bt_portfwd': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bt_umask': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'bt_uploadbw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'bt_watchdir': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'services.cifs': {
            'Meta': {'object_name': 'CIFS'},
            'cifs_srv_aio_enable': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cifs_srv_aio_rs': ('django.db.models.fields.IntegerField', [], {'default': "'1'", 'max_length': '120'}),
            'cifs_srv_aio_ws': ('django.db.models.fields.IntegerField', [], {'default': "'1'", 'max_length': '120'}),
            'cifs_srv_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_dirmask': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_dosattr': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_doscharset': ('django.db.models.fields.CharField', [], {'default': "'CP437'", 'max_length': '120'}),
            'cifs_srv_easupport': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_filemask': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_guest': ('django.db.models.fields.CharField', [], {'default': "'www'", 'max_length': '120'}),
            'cifs_srv_homedir_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_largerw': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_localmaster': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_loglevel': ('django.db.models.fields.CharField', [], {'default': "'Minimum'", 'max_length': '120'}),
            'cifs_srv_netbiosname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'cifs_srv_nullpw': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_recvbuffer': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_sendbuffer': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
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
            'ddns_wildcard': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'services.ftp': {
            'Meta': {'object_name': 'FTP'},
            'ftp_anonuserbw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ftp_anonuserdlbw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ftp_banner': ('django.db.models.fields.TextField', [], {'max_length': '120', 'blank': 'True'}),
            'ftp_clients': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ftp_defaultroot': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_dirmask': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ftp_filemask': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ftp_fxp': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_ident': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_ipconnections': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ftp_localuserbw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ftp_localuserdlbw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ftp_loginattempt': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ftp_masqaddress': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ftp_onlyanonymous': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_onlylocal': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_options': ('django.db.models.fields.TextField', [], {'max_length': '120', 'blank': 'True'}),
            'ftp_passiveportsmax': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ftp_passiveportsmin': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ftp_resume': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_reversedns': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_rootlogin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_ssltls': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ftp_timeout': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'services.iscsitarget': {
            'Meta': {'object_name': 'iSCSITarget'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_basename': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_discoveryauthgroup': ('django.db.models.fields.CharField', [], {'default': "'none'", 'max_length': '120'}),
            'iscsi_discoveryauthmethod': ('django.db.models.fields.CharField', [], {'default': "'auto'", 'max_length': '120'}),
            'iscsi_firstburst': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_io': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_maxburst': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_maxconnect': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_maxrecdata': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_maxsesh': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_nopinint': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_toggleluc': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
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
            'nfs_srv_servers': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'services.rsyncjob': {
            'Meta': {'object_name': 'rsyncjob'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'rj_Days1': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'rj_Days2': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'rj_Days3': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'rj_Hours1': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'rj_Hours2': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'rj_Minutes1': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'rj_Minutes2': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'rj_Minutes3': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'rj_Minutes4': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'rj_Months': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'rj_ToggleDays': ('django.db.models.fields.CharField', [], {'default': "'Selected'", 'max_length': '120'}),
            'rj_ToggleHours': ('django.db.models.fields.CharField', [], {'default': "'Selected'", 'max_length': '120'}),
            'rj_ToggleMinutes': ('django.db.models.fields.CharField', [], {'default': "'Selected'", 'max_length': '120'}),
            'rj_ToggleMonths': ('django.db.models.fields.CharField', [], {'default': "'Selected'", 'max_length': '120'}),
            'rj_ToggleWeekdays': ('django.db.models.fields.CharField', [], {'default': "'Selected'", 'max_length': '120'}),
            'rj_Weekdays': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'rj_archive': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rj_compress': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rj_delete': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rj_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'rj_extattr': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rj_options': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'rj_path': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'rj_preserveperms': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rj_quiet': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rj_recursive': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rj_server': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'rj_times': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rj_type': ('django.db.models.fields.CharField', [], {'default': "'(NONE)'", 'max_length': '120'}),
            'rj_who': ('django.db.models.fields.CharField', [], {'default': "'root'", 'max_length': '120'})
        },
        'services.services': {
            'Meta': {'object_name': 'services'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'srv_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'srv_service': ('django.db.models.fields.CharField', [], {'max_length': '120'})
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
            'tftp_username': ('django.db.models.fields.CharField', [], {'default': "'nobody'", 'max_length': '120'})
        },
        'services.unison': {
            'Meta': {'object_name': 'Unison'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'uni_createworkingdir': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'uni_workingdir': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'})
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
        'services.webserver': {
            'Meta': {'object_name': 'Webserver'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'web_auth': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'web_dirlisting': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'web_docroot': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'web_port': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'web_protocol': ('django.db.models.fields.CharField', [], {'default': "'OFF'", 'max_length': '120'})
        }
    }

    complete_apps = ['services']
