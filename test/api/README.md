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

* Configure Host information by
  * $ cd [path]/freenas/test/api/test-suite/
  * $ vi server.config
  * Config Hostname, Username (usually as root) and password (of username)

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
  * ActiveDirectory: get(), put()
  * LDAP: get(), put()
  * NIS: get(), put()
  * NT4: get(), put()

* Network
  * Global Configuration: get(), put()
  * Interface: get(), post(), put(), delete()
  * VLAN: get(), post(), put(), delete()
  * LAGG: get(), post(), delete()
  * Static Route: get(), post(), put(), delete()

* Plugins
  * Plugins: get(), start(), stop(), delete()

* Services
  * AFP: get(), put()
  * CIFS: get(), put()
  * Domain Controller: get(), put()
  * DynamicDNS: get(), put()
  * FTP: get(), put()
  * LLDP: get(), put()
  * NFS: get(), put()
  * Rsyncd: get(), put()
  * RsyncMod: get(), post(), put(), delete()
  * SMART: get(), put()
  * SNMP: get(), put()
  * SSH: get(), put()
  * TFTP: get(), put()
  * UPS: get(), put()

* Sharing
  * CIFS: get(), post(), put(), delete()
  * NFS: get(), post(), put(), delete()
  * AFP: get(), post(), put(), delete()

* Storage
  * Volume: get(), post(), delete()
  * Snapshot: get(), post(), delete()
  * Task: get(), post(), put(), delete()
  * Replication: get(), post(), put(), delete()
  * Scrub: get(), post(), put(), delete()
  * Disk: get(), put()

* System
  * Advanced: get(), put()
  * Alert: get()
  * Email: get()
  * NTPServer: get(), post(), put(), delete()
  * Reboot: post()
  * Settings: get(), put()
  * Shutdown: post()
  * SSL: get(), put()
  * Tunable: get(), post(), put(), delete()
  * Version: get()

* Tasks
  * CronJob: get(), post(), put(), delete(), run()
  * InitShutdown: get(), post(), put(), delete()
  * Rsync: get(), post(), put(), delete(), run
  * SMARTTest: get(), post(), put(), delete()


