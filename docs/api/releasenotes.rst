=============
Release Notes
=============

Release notes for the FreeNAS 9.3 API.


Resources
---------

* Resources added

 - LLDP service settings: /api/v1.0/services/lldp/
 - System version: /api/v1.0/system/version/
 - Jails Configuration settings: /api/v1.0/jails/configuration/
 - Jails: /api/v1.0/jails/jails/
 - Jails Mountpoints: /api/v1.0/jails/mountpoints/
 - Jails Templates: /api/v1.0/jails/templates/

* Endpoints added to existing resources

 - Volume resource to upgrade zpool version: /api/v1.0/storage/volume/(string:name)/upgrade/
 - CronJob resource to run a job on demand: /api/v1.0/tasks/cronjob/(int:id)/run/
 - Rsync resource to run a job on demand: /api/v1.0/tasks/rsync/(int:id)/run/


Fields
------

* Fields added

 - account User resource: bsdusr_sshpubkey
 - network Global Configuration resource: gc_httpproxy
 - service CIFS resource: cifs_srv_domain_logons
 - service Dynamic DNS resource: ddns_ipserver
 - storage Replication resource: repl_compression
 - system Settings resource: stg_guihttpsredirect
 - system Tunable resource: tun_type
 - directory service Active Directory resource: ad_keytab, ad_use_keytab


Backwardly incompatible changes
-------------------------------

* Resources removed

 - Admin Password resource has been removed: /api/v1.0/system/adminpassword/ . It has been replaced by users passwords in 9.2.
 - Admin User resource has been removed: /api/v1.0/system/adminuser/ . Since 9.2 the "root" user is the admin.
 - Sysctl resource has been removed: /api/v1.0/system/sysctl/ . Sysctl has been merged into /api/v1.0/system/tunable/

* Fields removed

 - Active Directory resource: ad_workgroup
 - Settings resource: stg_directoryservice

* Resources renamed

 - CronJob resource moved from /api/v1.0/system/cronjob/ to /api/v1.0/tasks/cronjob/
 - InitShutdown resource moved from /api/v1.0/system/initshutdown/ to /api/v1.0/tasks/initshutdown/
 - Rsync resource moved from /api/v1.0/system/rsync/ to /api/v1.0/tasks/rsync/
 - SMARTTest resource moved from /api/v1.0/system/smarttest/ to /api/v1.0/tasks/smarttest/
