=============
Release Notes
=============

Release notes for the FreeNAS 9.3 API.


Resources
---------

- New resource added for LLDP service settings: /api/v1.0/services/lldp/
- New resource added to provide the system version: /api/v1.0/system/version/
- Endpoint added in the Volume resource to upgrade zpool version: /api/v1.0/storage/volume/(string:name)/upgrade/
- Endpoint added in the CronJob resource to run a job on demand: /api/v1.0/tasks/cronjob/(int:id)/run/
- Endpoint added in the Rsync resource to run a job on demand: /api/v1.0/tasks/rsync/(int:id)/run/
- Admin Password resource has been removed: /api/v1.0/system/adminpassword/ . It has been replaced by users passwords in 9.2.
- Admin User resource has been removed: /api/v1.0/system/adminuser/ . Since 9.2 the "root" user is the admin.

Fields
------

- Field added in the User resource: bsdusr_sshpubkey
- Field added in the network Global Configuration resource: gc_httpproxy
- Field removed in the Active Directory resource: ad_workgroup
- Fields added in the Active Directory resource: ad_keytab, ad_use_keytab
