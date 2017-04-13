=============
Release Notes
=============

Release notes for the FreeNAS 9.10 API.

Resources
---------

* Resources removed

 - SSL: /api/v1.0/system/ssl/


Release notes for the FreeNAS 9.3 API.


Resources
---------

* Resources added

 - Jails: /api/v1.0/jails/jails/
 - Jails Configuration: /api/v1.0/jails/configuration/
 - Jails Mountpoints: /api/v1.0/jails/mountpoints/
 - Jails Templates: /api/v1.0/jails/templates/
 - Services Domain Controller: /api/v1.0/services/domaincontroller/
 - Services LLDP: /api/v1.0/services/lldp/
 - Storage Permission: /api/v1.0/storage/permission/
 - System Reboot: /api/v1.0/system/reboot/ (existed since 9.2.1 but undocumented)
 - System Shutdown: /api/v1.0/system/shutdown/ (existed since 9.2.1 but undocumented)
 - System Version: /api/v1.0/system/version/

* Endpoints added to existing resources

 - Volume resource to upgrade zpool version: /api/v1.0/storage/volume/(string:name)/upgrade/
 - CronJob resource to run a job on demand: /api/v1.0/tasks/cronjob/(int:id)/run/
 - Rsync resource to run a job on demand: /api/v1.0/tasks/rsync/(int:id)/run/


Fields
------

* Fields added

 - account User resource: bsdusr_sshpubkey
 - network Global Configuration resource: gc_httpproxy
 - service AFP resource: afp_srv_bindip, afp_srv_global_aux
 - service CIFS resource: cifs_srv_domain_logons, cifs_srv_obey_pam_restrictions, cifs_SID
 - service Dynamic DNS resource: ddns_ipserver
 - service NFS resource: nfs_srv_v4
 - service iSCSI extent resource: iscsi_target_extent_insecure_tpc, iscsi_target_extent_naa
 - sharing CIFS: cifs_home
 - sharing NFS: nfs_security
 - storage Replication resource: repl_compression, repl_remote_cipher
 - system Settings resource: stg_guihttpsredirect, stg_wizardshown
 - system Tunable resource: tun_type
 - directory service ActiveDirectory resource: ad_certfile, ad_enable, ad_keytab, ad_ssl, ad_use_keytab
 - directory service LDAP resource: ldap_binddn, ldap_enable, ldap_sudosuffix, ldap_use_default_domain, ldap_idmap_backend
 - directory service NIS resource: nis_enable
 - directory service NT4 resource: nt4_enable, nt4_idmap_backend, nt4_use_default_domain


Backwardly incompatible changes
-------------------------------

* Resources removed

 - Admin Password resource has been removed: /api/v1.0/system/adminpassword/ . It has been replaced by users passwords in 9.2.
 - Admin User resource has been removed: /api/v1.0/system/adminuser/ . Since 9.2 the "root" user is the admin.
 - Sysctl resource has been removed: /api/v1.0/system/sysctl/ . Sysctl has been merged into /api/v1.0/system/tunable/

* Fields removed

 - Active Directory resource: ad_workgroup
 - CIFS service resource: cifs_srv_homedir, cifs_srv_homedir_browseable_enable, cifs_srv_homedir_enable, cifs_srv_homedir_aux
 - Settings resource: stg_directoryservice
 - Replication resource: repl_remote_fast_cipher
 - iSCST Target resource: iscsi_target_flags, iscsi_target_type

* Fields renamed

 - directory service LDAP resource: ldap_rootbasedn -> ldap_basedn, ldap_rootbindpw -> ldap_bindpw, ldap_tls_cacertfile -> ldap_certfile

* Resources renamed

 - CronJob resource moved from /api/v1.0/system/cronjob/ to /api/v1.0/tasks/cronjob/
 - InitShutdown resource moved from /api/v1.0/system/initshutdown/ to /api/v1.0/tasks/initshutdown/
 - Rsync resource moved from /api/v1.0/system/rsync/ to /api/v1.0/tasks/rsync/
 - SMARTTest resource moved from /api/v1.0/system/smarttest/ to /api/v1.0/tasks/smarttest/
 - ActiveDirectory resourced move from /api/v1.0/services/activedirectory/ to /api/v1.0/directoryservice/activedirectory/
 - LDAP resourced move from /api/v1.0/services/ldap/ to /api/v1.0/directoryservice/ldap/
 - NIS resourced move from /api/v1.0/services/nis/ to /api/v1.0/directoryservice/nis/
 - NT4 resourced move from /api/v1.0/services/nt4/ to /api/v1.0/directoryservice/nt4/
