=========
System
=========

Resources related to system.

Admin Password
--------------

The Admin Password resource represents password change form to access the WebGUI.

Change Password
+++++++++++++++

.. http:put:: /api/v1.0/system/adminpassword/

   Change password to access WebGUI.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/system/adminpassword/ HTTP/1.1
      Content-Type: application/json

        {
                "old_password": "freenas",
                "new_password": "freenas2"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

      Admin password changed.

   :json string old_password: old password
   :json string new_password: new password
   :resheader Content-Type: content type of the response
   :statuscode 202: no error


Admin User
----------

The Admin User resource represents WebGUI account information.

List resource
+++++++++++++++

.. http:get:: /api/v1.0/system/adminuser/

   Get user settings.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/adminuser/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "username": "admin",
                "first_name": "",
                "last_name": ""
        }

   :resheader Content-Type: content type of the response
   :statuscode 200: no error

Update resource
+++++++++++++++

.. http:put:: /api/v1.0/system/adminuser/

   Change user settings.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/system/adminuser/ HTTP/1.1
      Content-Type: application/json

        {
                "username": "myadmin"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "username": "myadmin",
                "first_name": "",
                "last_name": ""
        }

   :json string username: webgui username
   :json string first_name: first name
   :json string last_name: last name
   :resheader Content-Type: content type of the response
   :statuscode 202: no error


CronJob
----------

The CronJob resource represents cron(8) to execute scheduled commands.

List resource
+++++++++++++

.. http:get:: /api/v1.0/system/cronjob/

   Returns a list of all cronjobs.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/cronjob/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "cron_command": "touch /tmp/xx",
                "cron_daymonth": "*",
                "cron_dayweek": "*",
                "cron_description": "",
                "cron_enabled": true,
                "cron_hour": "*",
                "cron_minute": "*",
                "cron_month": "1,2,3,4,6,7,8,9,10,11,12",
                "cron_stderr": false,
                "cron_stdout": true,
                "cron_user": "root",
                "id": 1
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/system/cronjob/

   Creates a new cronjob and returns the new cronjob object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/cronjob/ HTTP/1.1
      Content-Type: application/json

        {
                "cron_user": "root",
                "cron_command": "/data/myscript.sh",
                "cron_minute": "*/20",
                "cron_hour": "*",
                "cron_daymonth": "*",
                "cron_month": "*",
                "cron_dayweek": "*",
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "cron_command": "/data/myscript.sh",
                "cron_daymonth": "*",
                "cron_dayweek": "*",
                "cron_description": "",
                "cron_enabled": true,
                "cron_hour": "*",
                "cron_minute": "*/20",
                "cron_month": "*",
                "cron_stderr": false,
                "cron_stdout": true,
                "cron_user": "root",
                "id": 2
        }

   :json string cron_command: command to execute
   :json string cron_daymonth: days of the month to run
   :json string cron_dayweek: days of the week to run
   :json string cron_description: description of the job
   :json boolean cron_enabled: job enabled?
   :json string cron_hour: hours to run
   :json string cron_minute: minutes to run
   :json string cron_month: months to run
   :json string cron_user: user to run
   :json boolean cron_stderr: redirect stderr to /dev/null
   :json boolean cron_stdout: redirect stdout to /dev/null
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/system/cronjob/(int:id)/

   Update cronjob `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/system/cronjob/2/ HTTP/1.1
      Content-Type: application/json

        {
                "cron_enabled": false,
                "cron_stderr": true
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "cron_command": "/data/myscript.sh",
                "cron_daymonth": "*",
                "cron_dayweek": "*",
                "cron_description": "",
                "cron_enabled": false,
                "cron_hour": "*",
                "cron_minute": "*/20",
                "cron_month": "*",
                "cron_stderr": true,
                "cron_stdout": true,
                "cron_user": "root",
                "id": 2
        }

   :json string cron_command: command to execute
   :json string cron_daymonth: days of the month to run
   :json string cron_dayweek: days of the week to run
   :json string cron_description: description of the job
   :json boolean cron_enabled: job enabled?
   :json string cron_hour: hours to run
   :json string cron_minute: minutes to run
   :json string cron_month: months to run
   :json string cron_user: user to run
   :json boolean cron_stderr: redirect stderr to /dev/null
   :json boolean cron_stdout: redirect stdout to /dev/null
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/system/cronjob/(int:id)/

   Delete cronjob `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/system/cronjob/2/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


InitShutdown
------------

The InitShutdown resource represents Init and Shutdown scripts.

List resource
+++++++++++++

.. http:get:: /api/v1.0/system/initshutdown/

   Returns a list of all init shutdown scripts.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/initshutdown/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "id": 1
                "ini_type": "command",
                "ini_command": "rm /mnt/tank/temp*",
                "ini_when": "postinit"
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/system/initshutdown/

   Creates a new initshutdown and returns the new initshutdown object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/initshutdown/ HTTP/1.1
      Content-Type: application/json

        {
                "ini_type": "command",
                "ini_command": "rm /mnt/tank/temp*",
                "ini_when": "postinit"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "ini_command": "rm /mnt/tank/temp*",
                "ini_script": null,
                "ini_type": "command",
                "ini_when": "postinit"
        }

   :json string ini_command: command to execute
   :json string ini_script: path to script to execute
   :json string ini_type: run a command ("command") or a script ("script")
   :json string ini_when: preinit, postinit, shutdown
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/system/initshutdown/(int:id)/

   Update initshutdown `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/system/initshutdown/1/ HTTP/1.1
      Content-Type: application/json

        {
                "ini_when": "preinit"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "ini_command": "rm /mnt/tank/temp*",
                "ini_script": null,
                "ini_type": "command",
                "ini_when": "preinit"
        }

   :json string ini_command: command to execute
   :json string ini_script: path to script to execute
   :json string ini_type: run a command ("command") or a script ("script")
   :json string ini_when: preinit, postinit, shutdown
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/system/initshutdown/(int:id)/

   Delete initshutdown `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/system/initshutdown/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


NTPServer
----------

The NTPServer resource represents ntp.conf(5) to configure Network Time Protocol (NTP).

List resource
+++++++++++++

.. http:get:: /api/v1.0/system/ntpserver/

   Returns a list of all ntpservers.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/ntpserver/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "ntp_minpoll": 6,
                "ntp_maxpoll": 9,
                "ntp_prefer": false,
                "ntp_address": "0.freebsd.pool.ntp.org",
                "ntp_burst": false,
                "id": 1,
                "ntp_iburst": true
        },
        {
                "ntp_minpoll": 6,
                "ntp_maxpoll": 9,
                "ntp_prefer": false,
                "ntp_address": "1.freebsd.pool.ntp.org",
                "ntp_burst": false,
                "id": 2,
                "ntp_iburst": true
        },
        {
                "ntp_minpoll": 6,
                "ntp_maxpoll": 9,
                "ntp_prefer": false,
                "ntp_address": "2.freebsd.pool.ntp.org",
                "ntp_burst": false,
                "id": 3,
                "ntp_iburst": true
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/system/ntpserver/

   Creates a new ntpserver and returns the new ntpserver object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/ntpserver/ HTTP/1.1
      Content-Type: application/json

        {
                "ntp_address": "br.pool.ntp.org"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "ntp_minpoll": 6,
                "ntp_maxpoll": 10,
                "ntp_prefer": false,
                "ntp_address": "br.pool.ntp.org",
                "ntp_burst": false,
                "id": 4,
                "ntp_iburst": true
        }

   :json string ntp_minpoll: minimum poll interval as a power of 2 in seconds
   :json string ntp_maxpoll: maximum poll interval as a power of 2 in seconds
   :json string ntp_prefer: mark this server as preferred
   :json string ntp_address: address of the server
   :json string ntp_burst: send a burst of 8 packets when reachable
   :json string ntp_iburst: send a burst of 8 packets when unreachable
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/system/ntpserver/(int:id)/

   Update ntpserver `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/system/ntpserver/2/ HTTP/1.1
      Content-Type: application/json

        {
                "ntp_prefer": true,
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "ntp_minpoll": 6,
                "ntp_maxpoll": 10,
                "ntp_prefer": true,
                "ntp_address": "br.pool.ntp.org",
                "ntp_burst": false,
                "id": 4,
                "ntp_iburst": true
        }

   :json string ntp_minpoll: minimum poll interval as a power of 2 in seconds
   :json string ntp_maxpoll: maximum poll interval as a power of 2 in seconds
   :json string ntp_prefer: mark this server as preferred
   :json string ntp_address: address of the server
   :json string ntp_burst: send a burst of 8 packets when reachable
   :json string ntp_iburst: send a burst of 8 packets when unreachable
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/system/ntpserver/(int:id)/

   Delete ntpserver `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/system/ntpserver/2/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


Rsync
----------

The Rsync resource represents rsync(1) to execute scheduled commands.

List resource
+++++++++++++

.. http:get:: /api/v1.0/system/rsync/

   Returns a list of all rsyncs.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/rsync/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "rsync_user": "root",
                "rsync_minute": "*/20",
                "rsync_enabled": true,
                "rsync_daymonth": "*",
                "rsync_path": "/mnt/tank",
                "rsync_delete": false,
                "rsync_hour": "*",
                "id": 1,
                "rsync_extra": "",
                "rsync_archive": false,
                "rsync_compress": true,
                "rsync_dayweek": "*",
                "rsync_desc": "",
                "rsync_direction": "push",
                "rsync_times": true,
                "rsync_preserveattr": false,
                "rsync_remotehost": "testhost",
                "rsync_mode": "module",
                "rsync_remotemodule": "testmodule",
                "rsync_remotepath": "",
                "rsync_quiet": false,
                "rsync_recursive": true,
                "rsync_month": "*",
                "rsync_preserveperm": false,
                "rsync_remoteport": 22
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/system/rsync/

   Creates a new rsync and returns the new rsync object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/rsync/ HTTP/1.1
      Content-Type: application/json

        {
                "rsync_path": "/mnt/tank",
                "rsync_user": "root",
                "rsync_mode": "module",
                "rsync_remotemodule": "testmodule",
                "rsync_remotehost": "testhost",
                "rsync_direction": "push",
                "rsync_minute": "*/20",
                "rsync_hour": "*",
                "rsync_daymonth": "*",
                "rsync_month": "*",
                "rsync_dayweek": "*",
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "rsync_user": "root",
                "rsync_minute": "*/20",
                "rsync_enabled": true,
                "rsync_daymonth": "*",
                "rsync_path": "/mnt/tank",
                "rsync_delete": false,
                "rsync_hour": "*",
                "id": 1,
                "rsync_extra": "",
                "rsync_archive": false,
                "rsync_compress": true,
                "rsync_dayweek": "*",
                "rsync_desc": "",
                "rsync_direction": "push",
                "rsync_times": true,
                "rsync_preserveattr": false,
                "rsync_remotehost": "testhost",
                "rsync_mode": "module",
                "rsync_remotemodule": "testmodule",
                "rsync_remotepath": "",
                "rsync_quiet": false,
                "rsync_recursive": true,
                "rsync_month": "*",
                "rsync_preserveperm": false,
                "rsync_remoteport": 22
        }

   :json string rsync_path: path to rsync
   :json string rsync_user: user to run rsync(1)
   :json string rsync_mode: module, ssh
   :json string rsync_remotemodule: module of remote side
   :json string rsync_remotehost: host of remote side
   :json string rsync_remoteport: port of remote side
   :json string rsync_remotepath: path of remote side
   :json string rsync_direction: push, pull
   :json string rsync_minute: minutes to run
   :json string rsync_hour: hours to run
   :json string rsync_daymonth: days of month to run
   :json string rsync_month: months to run
   :json string rsync_dayweek: days of week to run
   :json boolean rsync_archive: archive mode
   :json boolean rsync_compress: compress the stream
   :json boolean rsync_times: preserve times
   :json boolean rsync_preserveattr: preserve file attributes
   :json boolean rsync_quiet: run quietly
   :json boolean rsync_recursive: recursive
   :json boolean rsync_preserveperm: preserve permissions
   :json string extra: extra arguments to rsync(1)
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/system/rsync/(int:id)/

   Update rsync `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/system/rsync/1/ HTTP/1.1
      Content-Type: application/json

        {
                "rsync_archive": true
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "rsync_user": "root",
                "rsync_minute": "*/20",
                "rsync_enabled": true,
                "rsync_daymonth": "*",
                "rsync_path": "/mnt/tank",
                "rsync_delete": false,
                "rsync_hour": "*",
                "id": 1,
                "rsync_extra": "",
                "rsync_archive": true,
                "rsync_compress": true,
                "rsync_dayweek": "*",
                "rsync_desc": "",
                "rsync_direction": "push",
                "rsync_times": true,
                "rsync_preserveattr": false,
                "rsync_remotehost": "testhost",
                "rsync_mode": "module",
                "rsync_remotemodule": "testmodule",
                "rsync_remotepath": "",
                "rsync_quiet": false,
                "rsync_recursive": true,
                "rsync_month": "*",
                "rsync_preserveperm": false,
                "rsync_remoteport": 22
        }

   :json string rsync_path: path to rsync
   :json string rsync_user: user to run rsync(1)
   :json string rsync_mode: module, ssh
   :json string rsync_remotemodule: module of remote side
   :json string rsync_remotehost: host of remote side
   :json string rsync_remoteport: port of remote side
   :json string rsync_remotepath: path of remote side
   :json string rsync_direction: push, pull
   :json string rsync_minute: minutes to run
   :json string rsync_hour: hours to run
   :json string rsync_daymonth: days of month to run
   :json string rsync_month: months to run
   :json string rsync_dayweek: days of week to run
   :json boolean rsync_archive: archive mode
   :json boolean rsync_compress: compress the stream
   :json boolean rsync_times: preserve times
   :json boolean rsync_preserveattr: preserve file attributes
   :json boolean rsync_quiet: run quietly
   :json boolean rsync_recursive: recursive
   :json boolean rsync_preserveperm: preserve permissions
   :json string extra: extra arguments to rsync(1)
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/system/rsync/(int:id)/

   Delete rsync `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/system/rsync/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


Settings
--------

The Settings resource represents the ssytem settings.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/settings/

   Returns the settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/settings/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "stg_timezone": "America/Los_Angeles",
                "stg_guiport": "",
                "stg_guiprotocol": "http",
                "stg_guiv6address": "::",
                "stg_syslogserver": "",
                "stg_language": "en",
                "stg_directoryservice": "",
                "stg_guiaddress": "0.0.0.0",
                "stg_kbdmap": "",
                "id": 1
        }

   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/settings/

   Update settings.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/settings/ HTTP/1.1
      Content-Type: application/json

        {
                "stg_timezone": "America/Sao_Paulo"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "stg_timezone": "America/Sao_Paulo",
                "stg_guiport": "",
                "stg_guiprotocol": "http",
                "stg_guiv6address": "::",
                "stg_syslogserver": "",
                "stg_language": "en",
                "stg_directoryservice": "",
                "stg_guiaddress": "0.0.0.0",
                "stg_kbdmap": "",
                "id": 1
        }

   :json string stg_guiprotocol: http, https
   :json string stg_guiaddress: WebGUI IPv4 Address
   :json string stg_guiv6address: WebGUI IPv6 Address
   :json string stg_guiport: WebGUI Port
   :json string stg_language: webguil language
   :json string stg_kbdmap: see /usr/share/syscons/keymaps/INDEX.keymaps
   :json string stg_timezone: see /usr/share/zoneinfo
   :json string stg_syslogserver: Syslog server
   :json string stg_directoryservice: activedirectory, ldap, nt4, nis
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


SMARTTest
----------

The SMARTTest resource represents schedule of SMART tests using smartd(8).

List resource
+++++++++++++

.. http:get:: /api/v1.0/system/smarttest/

   Returns a list of all smarttests.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/smarttest/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "smarttest_dayweek": "*",
                "smarttest_daymonth": "*",
                "smarttest_disks": [
                        2,
                        3
                ],
                "smarttest_month": "*",
                "smarttest_type": "L",
                "id": 1,
                "smarttest_hour": "*",
                "smarttest_desc": ""
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/system/smarttest/

   Creates a new smarttest and returns the new smarttest object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/smarttest/ HTTP/1.1
      Content-Type: application/json

        {
                "smarttest_disks": [2, 3],
                "smarttest_type": "L",
                "smarttest_hour": "*",
                "smarttest_daymonth": "*",
                "smarttest_month": "*",
                "smarttest_dayweek": "*",
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "smarttest_dayweek": "*",
                "smarttest_daymonth": "*",
                "smarttest_disks": [
                        2,
                        3
                ],
                "smarttest_month": "*",
                "smarttest_type": "L",
                "id": 1,
                "smarttest_hour": "*",
                "smarttest_desc": ""
        }

   :json string smarttest_dayweek: days of the week to run
   :json string smarttest_daymonth: days of the month to run
   :json string smarttest_hour: hours to run
   :json string smarttest_month: months to run
   :json string smarttest_disks: list of ids of "storage/disk" resource
   :json string smarttest_type: L (Long Self-Test), S (Short Self-Test), C (Conveyance Self-Test (ATA  only)), O (Offline Immediate Test (ATA only))
   :json string smarttest_desc: user description of the test
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/system/smarttest/(int:id)/

   Update smarttest `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/system/smarttest/1/ HTTP/1.1
      Content-Type: application/json

        {
                "smarttest_type": "S",
                "smarttest_disks": [2, 3]
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "smarttest_dayweek": "*",
                "smarttest_daymonth": "*",
                "smarttest_disks": [
                        2,
                        3
                ],
                "smarttest_month": "*",
                "smarttest_type": "L",
                "id": 1,
                "smarttest_hour": "*",
                "smarttest_desc": ""
        }

   :json string smarttest_dayweek: days of the week to run
   :json string smarttest_daymonth: days of the month to run
   :json string smarttest_hour: hours to run
   :json string smarttest_month: months to run
   :json string smarttest_disks: list of ids of "storage/disk" resource
   :json string smarttest_type: L (Long Self-Test), S (Short Self-Test), C (Conveyance Self-Test (ATA  only)), O (Offline Immediate Test (ATA only))
   :json string smarttest_desc: user description of the test
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/system/smarttest/(int:id)/

   Delete smarttest `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/system/smarttest/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


Sysctl
----------

The Sysctl resource represents sysctl(8), get or set kernel state.

List resource
+++++++++++++

.. http:get:: /api/v1.0/system/sysctl/

   Returns a list of all sysctls.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/sysctl/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "sysctl_mib": "net.inet.tcp.rfc1323",
                "sysctl_comment": "",
                "sysctl_value": "0",
                "sysctl_enabled": true
                "id": 1,
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/system/sysctl/

   Creates a new sysctl and returns the new sysctl object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/sysctl/ HTTP/1.1
      Content-Type: application/json

        {
                "sysctl_mib": "net.inet.tcp.rfc1323",
                "sysctl_value": "0",
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "sysctl_mib": "net.inet.tcp.rfc1323",
                "sysctl_comment": "",
                "sysctl_value": "0",
                "sysctl_enabled": true
                "id": 1,
        }

   :json string sysctl_mib: name of the sysctl
   :json string sysctl_value: value of the sysctl
   :json string sysctl_comment: user comment for the entry
   :json boolean sysctl_enabled: whether the entry is enabled
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/system/sysctl/(int:id)/

   Update sysctl `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/system/sysctl/1/ HTTP/1.1
      Content-Type: application/json

        {
                "sysctl_value": "1",
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "sysctl_mib": "net.inet.tcp.rfc1323",
                "sysctl_comment": "",
                "sysctl_value": "1",
                "sysctl_enabled": true
                "id": 1,
        }

   :json string sysctl_mib: name of the sysctl
   :json string sysctl_value: value of the sysctl
   :json string sysctl_comment: user comment for the entry
   :json boolean sysctl_enabled: whether the entry is enabled
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/system/sysctl/(int:id)/

   Delete sysctl `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/system/sysctl/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


Tunable
----------

The Tunable resource represents loader.conf(5).

List resource
+++++++++++++

.. http:get:: /api/v1.0/system/tunable/

   Returns a list of all tunables.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/tunable/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "tun_var": "xhci_load",
                "tun_comment": "",
                "tun_value": "YES",
                "tun_enabled": true
                "id": 1,
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/system/tunable/

   Creates a new tunable and returns the new tunable object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/tunable/ HTTP/1.1
      Content-Type: application/json

        {
                "tun_var": "xhci_load",
                "tun_value": "YES",
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "tun_var": "xhci_load",
                "tun_comment": "",
                "tun_value": "YES",
                "tun_enabled": true
                "id": 1,
        }

   :json string tun_var: name of the tunable
   :json string tun_value: value of the tunable
   :json string tun_comment: user comment for the entry
   :json boolean tun_enabled: whether the entry is enabled
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/system/tunable/(int:id)/

   Update tunable `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/system/tunable/1/ HTTP/1.1
      Content-Type: application/json

        {
                "tun_enabled": false
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "tun_var": "xhci_load",
                "tun_comment": "",
                "tun_value": "YES",
                "tun_enabled": false
                "id": 1,
        }

   :json string tun_var: name of the tunable
   :json string tun_value: value of the tunable
   :json string tun_comment: user comment for the entry
   :json boolean tun_enabled: whether the entry is enabled
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/system/tunable/(int:id)/

   Delete tunable `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/system/tunable/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error
