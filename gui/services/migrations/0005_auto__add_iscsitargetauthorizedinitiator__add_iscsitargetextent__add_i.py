# encoding: utf-8
import datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models

class Migration(DataMigration):

    def forwards(self, orm):
        
        # Adding model 'iSCSITargetAuthorizedInitiator'
        db.create_table('services_iscsitargetauthorizedinitiator', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('iscsi_target_initiator_tag', self.gf('django.db.models.fields.IntegerField')(unique=True, max_length=120)),
            ('iscsi_target_initiator_initiators', self.gf('django.db.models.fields.TextField')(default='ALL', max_length=2048)),
            ('iscsi_target_initiator_auth_network', self.gf('django.db.models.fields.TextField')(default='ALL', max_length=2048)),
            ('iscsi_target_initiator_comment', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
        ))
        db.send_create_signal('services', ['iSCSITargetAuthorizedInitiator'])

        # Adding model 'iSCSITargetExtent'
        db.create_table('services_iscsitargetextent', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('iscsi_target_extent_name', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('iscsi_target_extent_type', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('iscsi_target_extent_path', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('iscsi_target_extent_filesize', self.gf('django.db.models.fields.IntegerField')(default=0, max_length=120)),
            ('iscsi_target_extent_comment', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
        ))
        db.send_create_signal('services', ['iSCSITargetExtent'])

        # Adding model 'iSCSITargetToExtent'
        db.create_table('services_iscsitargettoextent', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('iscsi_target', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['services.iSCSITarget'])),
            ('iscsi_extent', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['services.iSCSITargetExtent'], unique=True)),
            ('iscsi_target_lun', self.gf('django.db.models.fields.IntegerField')(default=0, max_length=120)),
        ))
        db.send_create_signal('services', ['iSCSITargetToExtent'])

        # Adding model 'iSCSITargetGlobalConfiguration'
        db.create_table('services_iscsitargetglobalconfiguration', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('iscsi_basename', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('iscsi_mediadirectory', self.gf('django.db.models.fields.CharField')(default='/mnt', max_length=120)),
            ('iscsi_discoveryauthmethod', self.gf('django.db.models.fields.CharField')(default='auto', max_length=120)),
            ('iscsi_discoveryauthgroup', self.gf('django.db.models.fields.CharField')(default='none', max_length=120)),
            ('iscsi_iotimeout', self.gf('django.db.models.fields.IntegerField')(default=30, max_length=120)),
            ('iscsi_nopinint', self.gf('django.db.models.fields.IntegerField')(default=20, max_length=120)),
            ('iscsi_maxsesh', self.gf('django.db.models.fields.IntegerField')(default=16, max_length=120)),
            ('iscsi_maxconnect', self.gf('django.db.models.fields.IntegerField')(default=8, max_length=120)),
            ('iscsi_r2t', self.gf('django.db.models.fields.IntegerField')(default=32, max_length=120)),
            ('iscsi_maxoutstandingr2t', self.gf('django.db.models.fields.IntegerField')(default=16, max_length=120)),
            ('iscsi_firstburst', self.gf('django.db.models.fields.IntegerField')(default=65536, max_length=120)),
            ('iscsi_maxburst', self.gf('django.db.models.fields.IntegerField')(default=262144, max_length=120)),
            ('iscsi_maxrecdata', self.gf('django.db.models.fields.IntegerField')(default=262144, max_length=120)),
            ('iscsi_defaultt2w', self.gf('django.db.models.fields.IntegerField')(default=2, max_length=120)),
            ('iscsi_defaultt2r', self.gf('django.db.models.fields.IntegerField')(default=60, max_length=120)),
            ('iscsi_toggleluc', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('iscsi_lucip', self.gf('django.db.models.fields.CharField')(default='127.0.0.1', max_length=120)),
            ('iscsi_lucport', self.gf('django.db.models.fields.IntegerField')(default=3261, max_length=120)),
            ('iscsi_luc_authnetwork', self.gf('django.db.models.fields.CharField')(default='127.0.0.0/8', max_length=120)),
            ('iscsi_luc_authmethod', self.gf('django.db.models.fields.CharField')(default='CHAP', max_length=120)),
            ('iscsi_luc_authgroup', self.gf('django.db.models.fields.IntegerField')(default=1, max_length=120)),
        ))
        db.send_create_signal('services', ['iSCSITargetGlobalConfiguration'])

        # Adding model 'iSCSITarget'
        db.delete_table('services_iscsitarget')
        db.create_table('services_iscsitarget', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('iscsi_target_name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=120)),
            ('iscsi_target_alias', self.gf('django.db.models.fields.CharField')(unique=True, max_length=120, blank=True)),
            ('iscsi_target_type', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('iscsi_target_flags', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('iscsi_target_portalgroup', self.gf('django.db.models.fields.IntegerField')(default=1, max_length=120)),
            ('iscsi_target_initiatorgroup', self.gf('django.db.models.fields.IntegerField')(default=1, max_length=120)),
            ('iscsi_target_authtype', self.gf('django.db.models.fields.CharField')(default='Auto', max_length=120)),
            ('iscsi_target_authgroup', self.gf('django.db.models.fields.IntegerField')(default=1, max_length=120)),
            ('iscsi_target_initialdigest', self.gf('django.db.models.fields.CharField')(default='Auto', max_length=120)),
            ('iscsi_target_queue_depth', self.gf('django.db.models.fields.IntegerField')(default=0, max_length=3)),
            ('iscsi_target_logical_blocksize', self.gf('django.db.models.fields.IntegerField')(default=512, max_length=3)),
        ))
        db.send_create_signal('services', ['iSCSITarget'])

        # Adding model 'iSCSITargetAuthCredential'
        db.create_table('services_iscsitargetauthcredential', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('iscsi_target_auth_tag', self.gf('django.db.models.fields.IntegerField')(default=1, max_length=120)),
            ('iscsi_target_auth_user', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('iscsi_target_auth_secret', self.gf('django.db.models.fields.CharField')(max_length=120)),
            ('iscsi_target_auth_peeruser', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
            ('iscsi_target_auth_peersecret', self.gf('django.db.models.fields.CharField')(max_length=120)),
        ))
        db.send_create_signal('services', ['iSCSITargetAuthCredential'])

        # Adding model 'iSCSITargetPortal'
        db.create_table('services_iscsitargetportal', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('iscsi_target_portal_tag', self.gf('django.db.models.fields.IntegerField')(default=1, max_length=120)),
            ('iscsi_target_portal_listen', self.gf('django.db.models.fields.CharField')(default='0.0.0.0:3260', max_length=120)),
            ('iscsi_target_portal_comment', self.gf('django.db.models.fields.CharField')(max_length=120, blank=True)),
        ))
        db.send_create_signal('services', ['iSCSITargetPortal'])

        gc = orm.iSCSITargetGlobalConfiguration()
        gc.iscsi_basename='iqn.2005-10.org.freenas.ctl'
        gc.iscsi_discoveryauthgroup=''
        gc.save()

    def backwards(self, orm):
        
        # Deleting model 'iSCSITargetAuthorizedInitiator'
        db.delete_table('services_iscsitargetauthorizedinitiator')

        # Deleting model 'iSCSITargetExtent'
        db.delete_table('services_iscsitargetextent')

        # Deleting model 'iSCSITargetToExtent'
        db.delete_table('services_iscsitargettoextent')

        # Deleting model 'iSCSITargetGlobalConfiguration'
        db.delete_table('services_iscsitargetglobalconfiguration')

        # Deleting model 'iSCSITargetAuthCredential'
        db.delete_table('services_iscsitargetauthcredential')

        # Deleting model 'iSCSITargetPortal'
        db.delete_table('services_iscsitargetportal')

        # We cannot add back in model 'iSCSITarget'
        raise RuntimeError(
            "Cannot reverse this migration. 'iSCSITarget' and its values cannot be restored.")

        # Adding field 'iSCSITarget.iscsi_discoveryauthgroup'
        db.add_column('services_iscsitarget', 'iscsi_discoveryauthgroup', self.gf('django.db.models.fields.CharField')(default='none', max_length=120), keep_default=False)

        # Adding field 'iSCSITarget.iscsi_toggleluc'
        db.add_column('services_iscsitarget', 'iscsi_toggleluc', self.gf('django.db.models.fields.BooleanField')(default=False), keep_default=False)

        # We cannot add back in field 'iSCSITarget.iscsi_io'
        raise RuntimeError(
            "Cannot reverse this migration. 'iSCSITarget.iscsi_io' and its values cannot be restored.")

        # Deleting field 'iSCSITarget.iscsi_target_name'
        db.delete_column('services_iscsitarget', 'iscsi_target_name')


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
            'iscsi_target_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'})
        },
        'services.iscsitarget': {
            'Meta': {'object_name': 'iSCSITarget'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target_alias': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120', 'blank': 'True'}),
            'iscsi_target_authgroup': ('django.db.models.fields.IntegerField', [], {'default': '1', 'max_length': '120'}),
            'iscsi_target_authtype': ('django.db.models.fields.CharField', [], {'default': "'Auto'", 'max_length': '120'}),
            'iscsi_target_flags': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_target_initialdigest': ('django.db.models.fields.CharField', [], {'default': "'Auto'", 'max_length': '120'}),
            'iscsi_target_initiatorgroup': ('django.db.models.fields.IntegerField', [], {'default': '1', 'max_length': '120'}),
            'iscsi_target_logical_blocksize': ('django.db.models.fields.IntegerField', [], {'default': '512', 'max_length': '3'}),
            'iscsi_target_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'iscsi_target_portalgroup': ('django.db.models.fields.IntegerField', [], {'default': '1', 'max_length': '120'}),
            'iscsi_target_queue_depth': ('django.db.models.fields.IntegerField', [], {'default': '0', 'max_length': '3'}),
            'iscsi_target_type': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'services.iscsitargetauthcredential': {
            'Meta': {'object_name': 'iSCSITargetAuthCredential'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target_auth_peersecret': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_target_auth_peeruser': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'iscsi_target_auth_secret': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_target_auth_tag': ('django.db.models.fields.IntegerField', [], {'default': '1', 'max_length': '120'}),
            'iscsi_target_auth_user': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'services.iscsitargetauthorizedinitiator': {
            'Meta': {'object_name': 'iSCSITargetAuthorizedInitiator'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target_initiator_auth_network': ('django.db.models.fields.TextField', [], {'default': "'ALL'", 'max_length': '2048'}),
            'iscsi_target_initiator_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'iscsi_target_initiator_initiators': ('django.db.models.fields.TextField', [], {'default': "'ALL'", 'max_length': '2048'}),
            'iscsi_target_initiator_tag': ('django.db.models.fields.IntegerField', [], {'unique': 'True', 'max_length': '120'})
        },
        'services.iscsitargetextent': {
            'Meta': {'object_name': 'iSCSITargetExtent'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target_extent_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'iscsi_target_extent_filesize': ('django.db.models.fields.IntegerField', [], {'default': '0', 'max_length': '120'}),
            'iscsi_target_extent_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_target_extent_path': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_target_extent_type': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        'services.iscsitargetglobalconfiguration': {
            'Meta': {'object_name': 'iSCSITargetGlobalConfiguration'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_basename': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'iscsi_defaultt2r': ('django.db.models.fields.IntegerField', [], {'default': '60', 'max_length': '120'}),
            'iscsi_defaultt2w': ('django.db.models.fields.IntegerField', [], {'default': '2', 'max_length': '120'}),
            'iscsi_discoveryauthgroup': ('django.db.models.fields.CharField', [], {'default': "'none'", 'max_length': '120'}),
            'iscsi_discoveryauthmethod': ('django.db.models.fields.CharField', [], {'default': "'auto'", 'max_length': '120'}),
            'iscsi_firstburst': ('django.db.models.fields.IntegerField', [], {'default': '65536', 'max_length': '120'}),
            'iscsi_iotimeout': ('django.db.models.fields.IntegerField', [], {'default': '30', 'max_length': '120'}),
            'iscsi_luc_authgroup': ('django.db.models.fields.IntegerField', [], {'default': '1', 'max_length': '120'}),
            'iscsi_luc_authmethod': ('django.db.models.fields.CharField', [], {'default': "'CHAP'", 'max_length': '120'}),
            'iscsi_luc_authnetwork': ('django.db.models.fields.CharField', [], {'default': "'127.0.0.0/8'", 'max_length': '120'}),
            'iscsi_lucip': ('django.db.models.fields.CharField', [], {'default': "'127.0.0.1'", 'max_length': '120'}),
            'iscsi_lucport': ('django.db.models.fields.IntegerField', [], {'default': '3261', 'max_length': '120'}),
            'iscsi_maxburst': ('django.db.models.fields.IntegerField', [], {'default': '262144', 'max_length': '120'}),
            'iscsi_maxconnect': ('django.db.models.fields.IntegerField', [], {'default': '8', 'max_length': '120'}),
            'iscsi_maxoutstandingr2t': ('django.db.models.fields.IntegerField', [], {'default': '16', 'max_length': '120'}),
            'iscsi_maxrecdata': ('django.db.models.fields.IntegerField', [], {'default': '262144', 'max_length': '120'}),
            'iscsi_maxsesh': ('django.db.models.fields.IntegerField', [], {'default': '16', 'max_length': '120'}),
            'iscsi_mediadirectory': ('django.db.models.fields.CharField', [], {'default': "'/mnt'", 'max_length': '120'}),
            'iscsi_nopinint': ('django.db.models.fields.IntegerField', [], {'default': '20', 'max_length': '120'}),
            'iscsi_r2t': ('django.db.models.fields.IntegerField', [], {'default': '32', 'max_length': '120'}),
            'iscsi_toggleluc': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'services.iscsitargetportal': {
            'Meta': {'object_name': 'iSCSITargetPortal'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_target_portal_comment': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'iscsi_target_portal_listen': ('django.db.models.fields.CharField', [], {'default': "'0.0.0.0:3260'", 'max_length': '120'}),
            'iscsi_target_portal_tag': ('django.db.models.fields.IntegerField', [], {'default': '1', 'max_length': '120'})
        },
        'services.iscsitargettoextent': {
            'Meta': {'object_name': 'iSCSITargetToExtent'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'iscsi_extent': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['services.iSCSITargetExtent']", 'unique': 'True'}),
            'iscsi_target': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['services.iSCSITarget']"}),
            'iscsi_target_lun': ('django.db.models.fields.IntegerField', [], {'default': '0', 'max_length': '120'})
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
