freenas-test-api
================

## Requirements:

* Your build environment must be FreeBSD 9.2-RELEASE (
  FreeBSD 10 or 11 is also supported for API test programs).

* You have to make sure python-2.7 is well installed (no guarantee on other versions of python).

* You will need the following ports/packages
  * pkg install www/py-requests-oauth-hook 
  * pkg install www/py-requests-oauthlib

## How to actually use

* For all APIs we basically have four functions:
  * get() : to get information about configuration of special thing you want to know
  * post(): to create a new instance
  * put(): to update an instance
  * delete(): to delete an instance
  * For some special APIs we have run(), start() and stop() etc...... 
    You can check the list at the bottom of this introduction.

* You can check content of all APIs on http://api.freenas.org

* If you want to test a single leaf such as Sharing-CIFS under Sharing
  * $ cd [path]/freenas/test/api/test-suite/
  * $ python
  * Under python script (all characters MUST be lower cases):
    >>import sharing_cifs
    >>sharing_cifs.post()
    >>sharing_cifs.put()
    >>sharing_cifs.get()
    >>sharing_cifs.delete()
  * You can create your own test suite by combining diffierent leafs
  * You can use command
    $ ls -l
    to check what APIs are available currently

* If you want to use a upper level test suite such as System
  * $ cd [path]/freenas/test/api/test-suite/
  * $ python system.py

* If you want to use the uppest level test suite: Fulltest
  * $ cd [path]/freenas/test/api/test-suite/
  * $ python fulltest.py 

## API function list

* Directory Service
  * ActiveDirectory
  * LDAP
  * NIS
  * NT4

* Jails
  * Configuration
  * Jails
  * MountPoints
  * Templates

* Network
  * Global Configuration
  * Interface
  * VLAN
  * LAGG
  * Static Route

* Plugins
  * Plugins

* Services
  * Services
  * AFP
  * CIFS
  * Domain Controller
  * DynamicDNS
  * FTP
  * iSCSI
  * LLDP
  * NFS
  * Rsyncd
  * RsyncMod
  * SMART
  * SNMP
  * SSH
  * TFTP
  * UPS

* Sharing
  * CIFS
  * NFS
  * AFP

* Storage
  * Volume
  * Snapshot
  * Task
  * Replication
  * Scrub
  * Disk

* System
  * Advanced
  * Alert
  * Email
  * NTPServer
  * Reboot
  * Settings
  * Shutdown
  * SSL
  * Tunable
  * Version

* Tasks
  * CronJob
  * InitShutdown
  * Rsync
  * SMARTTest


