# encoding: utf-8
import datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models
from freenasUI.common.system import get_sw_name


class Migration(DataMigration):

    def forwards(self, orm):
        
        # Adding model 'rsyncjob'
        db.create_table('services_rsyncjob', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('rj_type', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('rj_path', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('rj_server', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('rj_who', self.gf('django.db.models.fields.CharField')(default='root', max_length=120)),
            ('rj_description', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('rj_ToggleMinutes', self.gf('django.db.models.fields.CharField')(default='Selected', max_length=120)),
            ('rj_Minutes1', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('rj_Minutes2', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('rj_Minutes3', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('rj_Minutes4', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('rj_ToggleHours', self.gf('django.db.models.fields.CharField')(default='Selected', max_length=120)),
            ('rj_Hours1', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('rj_Hours2', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('rj_ToggleDays', self.gf('django.db.models.fields.CharField')(default='Selected', max_length=120)),
            ('rj_Days1', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('rj_Days2', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('rj_Days3', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('rj_ToggleMonths', self.gf('django.db.models.fields.CharField')(default='Selected', max_length=120)),
            ('rj_Months', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('rj_ToggleWeekdays', self.gf('django.db.models.fields.CharField')(default='Selected', max_length=120)),
            ('rj_Weekdays', self.gf('django.db.models.fields.CharField')(default='(NONE)', max_length=120)),
            ('rj_recursive', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('rj_times', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('rj_compress', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('rj_archive', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('rj_delete', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('rj_quiet', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('rj_preserveperms', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('rj_extattr', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('rj_options', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('services', ['rsyncjob'])

        # Adding model 'services'
        db.create_table('services_services', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('srv_service', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('srv_enable', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('services', ['services'])

        # Adding model 'CIFS'
        db.create_table('services_cifs', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('cifs_srv_netbiosname', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('cifs_srv_workgroup', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('cifs_srv_description', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('cifs_srv_doscharset', self.gf('django.db.models.fields.CharField')(default='CP437', max_length=120)),
            ('cifs_srv_unixcharset', self.gf('django.db.models.fields.CharField')(default='UTF-8', max_length=120)),
            ('cifs_srv_loglevel', self.gf('django.db.models.fields.CharField')(default='1', max_length=120)),
            ('cifs_srv_localmaster', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('cifs_srv_timeserver', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('cifs_srv_guest', self.gf('django.db.models.fields.CharField')(default='www', max_length=120)),
            ('cifs_srv_filemask', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('cifs_srv_dirmask', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('cifs_srv_sendbuffer', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('cifs_srv_recvbuffer', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('cifs_srv_largerw', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('cifs_srv_sendfile', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('cifs_srv_easupport', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('cifs_srv_dosattr', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('cifs_srv_nullpw', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('cifs_srv_smb_options', self.gf('django.db.models.fields.TextField')(max_length=120, blank=True)),
        ))
        db.send_create_signal('services', ['CIFS'])

        # Adding model 'AFP'
        db.create_table('services_afp', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('afp_srv_name', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('afp_srv_guest', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('afp_srv_local', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('afp_srv_ddp', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('services', ['AFP'])

        # Adding model 'NFS'
        db.create_table('services_nfs', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('nfs_srv_servers', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('services', ['NFS'])

        # Adding model 'Unison'
        db.create_table('services_unison', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('uni_workingdir', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('uni_createworkingdir', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('services', ['Unison'])

        # Adding model 'iSCSITarget'
        db.create_table('services_iscsitarget', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('iscsi_basename', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('iscsi_discoveryauthmethod', self.gf('django.db.models.fields.CharField')(default='auto', max_length=120)),
            ('iscsi_discoveryauthgroup', self.gf('django.db.models.fields.CharField')(default='none', max_length=120)),
            ('iscsi_io', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('iscsi_nopinint', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('iscsi_maxsesh', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('iscsi_maxconnect', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('iscsi_firstburst', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('iscsi_maxburst', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('iscsi_maxrecdata', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('iscsi_toggleluc', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('services', ['iSCSITarget'])

        # Adding model 'DynamicDNS'
        db.create_table('services_dynamicdns', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('ddns_provider', self.gf('django.db.models.fields.CharField')(default='dyndns', max_length=120)),
            ('ddns_domain', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ddns_username', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('ddns_password', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('ddns_updateperiod', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ddns_fupdateperiod', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ddns_wildcard', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ddns_options', self.gf('django.db.models.fields.TextField')(blank=True)),
        ))
        db.send_create_signal('services', ['DynamicDNS'])

        # Adding model 'SNMP'
        db.create_table('services_snmp', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('snmp_location', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('snmp_contact', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('snmp_community', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('snmp_traps', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('snmp_options', self.gf('django.db.models.fields.TextField')(blank=True)),
        ))
        db.send_create_signal('services', ['SNMP'])

        # Adding model 'UPS'
        db.create_table('services_ups', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('ups_identifier', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('ups_driver', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ups_port', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ups_options', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('ups_description', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ups_shutdown', self.gf('django.db.models.fields.CharField')(default='batt', max_length=120)),
            ('ups_shutdowntimer', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('ups_rmonitor', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ups_emailnotify', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ups_toemail', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ups_subject', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('services', ['UPS'])

        # Adding model 'Webserver'
        db.create_table('services_webserver', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('web_protocol', self.gf('django.db.models.fields.CharField')(default='OFF', max_length=120)),
            ('web_port', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('web_docroot', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('web_auth', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('web_dirlisting', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('services', ['Webserver'])

        # Adding model 'BitTorrent'
        db.create_table('services_bittorrent', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('bt_peerport', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('bt_downloaddir', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('bt_configdir', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('bt_portfwd', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('bt_pex', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('bt_disthash', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('bt_encrypt', self.gf('django.db.models.fields.CharField')(default='preferred', max_length=120, blank=True)),
            ('bt_uploadbw', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('bt_downloadbw', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('bt_watchdir', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('bt_incompletedir', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('bt_umask', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('bt_options', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('bt_adminport', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('bt_adminauth', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('bt_adminuser', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('bt_adminpass', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('services', ['BitTorrent'])

        # Adding model 'FTP'
        db.create_table('services_ftp', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('ftp_clients', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('ftp_ipconnections', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('ftp_loginattempt', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('ftp_timeout', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('ftp_rootlogin', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ftp_onlyanonymous', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ftp_onlylocal', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ftp_banner', self.gf('django.db.models.fields.TextField')(max_length=120, blank=True)),
            ('ftp_filemask', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('ftp_dirmask', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('ftp_fxp', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ftp_resume', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ftp_defaultroot', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ftp_ident', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ftp_reversedns', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ftp_masqaddress', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ftp_passiveportsmin', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('ftp_passiveportsmax', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('ftp_localuserbw', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ftp_localuserdlbw', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ftp_anonuserbw', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ftp_anonuserdlbw', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ftp_ssltls', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ftp_options', self.gf('django.db.models.fields.TextField')(max_length=120, blank=True)),
        ))
        db.send_create_signal('services', ['FTP'])

        # Adding model 'TFTP'
        db.create_table('services_tftp', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('tftp_directory', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('tftp_newfiles', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('tftp_port', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('tftp_username', self.gf('django.db.models.fields.CharField')(default='nobody', max_length=120)),
            ('tftp_umask', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('tftp_options', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
        ))
        db.send_create_signal('services', ['TFTP'])

        # Adding model 'SSH'
        db.create_table('services_ssh', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('ssh_tcpport', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('ssh_rootlogin', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ssh_passwordauth', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ssh_tcpfwd', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ssh_compression', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ssh_privatekey', self.gf('django.db.models.fields.TextField')(max_length=1024, blank=True)),
            ('ssh_options', self.gf('django.db.models.fields.TextField')(max_length=120, blank=True)),
        ))
        db.send_create_signal('services', ['SSH'])

        # Adding model 'ActiveDirectory'
        db.create_table('services_activedirectory', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('ad_dcname', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('ad_domainname', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('ad_netbiosname', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('ad_adminname', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('ad_adminpw', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('services', ['ActiveDirectory'])

        # Adding model 'LDAP'
        db.create_table('services_ldap', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('ldap_hostname', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ldap_basedn', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ldap_anonbind', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ldap_rootbasedn', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ldap_rootbindpw', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ldap_pwencryption', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('ldap_usersuffix', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ldap_groupsuffix', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ldap_passwordsuffix', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ldap_machinesuffix', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('ldap_options', self.gf('django.db.models.fields.TextField')(max_length=120, blank=True)),
        ))
        db.send_create_signal('services', ['LDAP'])

        afp = orm.AFP()
        afp.afp_srv_name = get_sw_name().lower()
        afp.afp_srv_guest = False
        afp.afp_srv_local = True
        afp.afp_srv_ddp = False
        afp.save()

        cifs = orm.CIFS()
        cifs.cifs_srv_netbiosname = get_sw_name().lower()
        cifs.cifs_srv_workgroup = 'WORKGROUP'
        cifs.cifs_srv_description = '%s Server' % (get_sw_name(), )
        cifs.cifs_srv_doscharset = 'CP437'
        cifs.cifs_srv_unixcharset = 'UTF-8'
        cifs.cifs_srv_loglevel = '1'
        cifs.cifs_srv_localmaster = True
        cifs.cifs_srv_timeserver = True
        cifs.cifs_srv_guest = 'nobody'
        cifs.cifs_srv_largerw = False
        cifs.cifs_srv_sendfile = True
        cifs.cifs_srv_easupport = False
        cifs.cifs_srv_dosattr = True
        cifs.cifs_srv_nullpw = False
        cifs.save()

        ddns = orm.DynamicDNS()
        ddns.ddns_provider = 'dyndns'
        ddns.ddns_username = 'admin'
        ddns.ddns_password = get_sw_name().lower()
        ddns.ddns_wildcard = False
        ddns.save()

        ftp = orm.FTP()
        ftp.ftp_clients = 5
        ftp.ftp_ipconnections = 2
        ftp.ftp_loginattempt = 1
        ftp.ftp_timeout = 600
        ftp.ftp_rootlogin = False
        ftp.ftp_onlyanonymous = False
        ftp.ftp_onlylocal = False
        ftp.ftp_filemask = '077'
        ftp.ftp_dirmask = '022'
        ftp.ftp_fxp = 0
        ftp.ftp_resume = 0
        ftp.ftp_defaultroot = 1
        ftp.ftp_ident = 0
        ftp.ftp_reversedns = 0
        ftp.ftp_passiveportsmin = 0
        ftp.ftp_passiveportsmax = 0
        ftp.ftp_localuserbw = 0
        ftp.ftp_localuserdlbw = 0
        ftp.ftp_anonuserbw = 0
        ftp.ftp_anonuserdlbw = 0
        ftp.ftp_ssltls = False
        ftp.save()

        nfs = orm.NFS()
        nfs.nfs_srv_servers = 4
        nfs.save()

        snmp = orm.SNMP()
        snmp.snmp_community = 'public'
        snmp.snmp_traps = 0
        snmp.save()

        ssh = orm.SSH()
        ssh.ssh_tcpport = 22
        ssh.ssh_rootlogin = False
        ssh.ssh_passwordauth = True
        ssh.ssh_tcpfwd = False
        ssh.ssh_compression = False
        ssh.save()

        tftp = orm.TFTP()
        tftp.tftp_directory = '/tftproot'
        tftp.tftp_newfiles = False
        tftp.tftp_port = 69
        tftp.tftp_username = 'nobody'
        tftp.tftp_umask = '022'
        tftp.save()

        ups = orm.UPS()
        ups.ups_identifier = 'ups'
        ups.ups_shutdown = 'batt'
        ups.ups_shutdowntimer = 30
        ups.ups_rmonitor = False
        ups.ups_emailnotify = False
        ups.ups_subject = 'UPS report generated by %h'
        ups.save()

        ad = orm.ActiveDirectory()
        ad.ad_windows_version = 'windows2000'
        ad.save()

        ldap = orm.LDAP()
        ldap.ldap_anonbind = 0
        ldap.ldap_pwencryption = 'clear'
        ldap.ldap_ssl = 'off'
        ldap.ldap_options = 'ldap_version 3\ntimelimit 30\nbind_timelimit 30\nbind_policy soft\npam_ldap_attribute uid'
        ldap.save()

        for srv_service in ('activedirectory', 'afp', 'bittorrent', 'cifs', 'dynamicdns',
                        'ftp', 'iscsitarget', 'ldap', 'nfs', 'snmp', 'ssh', 'tftp', 'unison',
                        'ups', 'webserver'):
            s = orm.Services()
            s.srv_service = srv_service
            s.srv_enable = False
            s.save()

    def backwards(self, orm):
        
        # Deleting model 'rsyncjob'
        db.delete_table('services_rsyncjob')

        # Deleting model 'services'
        db.delete_table('services_services')

        # Deleting model 'CIFS'
        db.delete_table('services_cifs')

        # Deleting model 'AFP'
        db.delete_table('services_afp')

        # Deleting model 'NFS'
        db.delete_table('services_nfs')

        # Deleting model 'Unison'
        db.delete_table('services_unison')

        # Deleting model 'iSCSITarget'
        db.delete_table('services_iscsitarget')

        # Deleting model 'DynamicDNS'
        db.delete_table('services_dynamicdns')

        # Deleting model 'SNMP'
        db.delete_table('services_snmp')

        # Deleting model 'UPS'
        db.delete_table('services_ups')

        # Deleting model 'Webserver'
        db.delete_table('services_webserver')

        # Deleting model 'BitTorrent'
        db.delete_table('services_bittorrent')

        # Deleting model 'FTP'
        db.delete_table('services_ftp')

        # Deleting model 'TFTP'
        db.delete_table('services_tftp')

        # Deleting model 'SSH'
        db.delete_table('services_ssh')

        # Deleting model 'ActiveDirectory'
        db.delete_table('services_activedirectory')

        # Deleting model 'LDAP'
        db.delete_table('services_ldap')


    models = {
        'services.activedirectory': {
            'Meta': {'object_name': 'ActiveDirectory'},
            'ad_adminname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_adminpw': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_dcname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_domainname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_netbiosname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
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
            'cifs_srv_description': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_dirmask': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_dosattr': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_doscharset': ('django.db.models.fields.CharField', [], {'default': "'CP437'", 'max_length': '120'}),
            'cifs_srv_easupport': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cifs_srv_filemask': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'cifs_srv_guest': ('django.db.models.fields.CharField', [], {'default': "'www'", 'max_length': '120'}),
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
