=========
System
=========

Resources related to system.


Advanced
--------

The Advanced resource represents the advanced settings.

List resource
+++++++++++++

.. http:get:: /api/v1.0/system/advanced/

   Returns the advanced dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/advanced/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "adv_serialconsole": false,
                "adv_traceback": true,
                "adv_uploadcrash": true,
                "adv_consolescreensaver": false,
                "adv_debugkernel": false,
                "adv_advancedmode": false,
                "adv_consolemsg": false,
                "adv_anonstats": true,
                "adv_autotune": false,
                "adv_powerdaemon": false,
                "adv_swapondrive": 2,
                "adv_anonstats_token": "",
                "adv_motd": "Welcome to FreeNAS",
                "adv_consolemenu": true,
                "id": 1,
                "adv_serialport": "0x2f8",
                "adv_serialspeed": "9600"
        }

   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/system/advanced/

   Update advanced.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/system/advanced/ HTTP/1.1
      Content-Type: application/json

        {
                "adv_powerdaemon": true
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "adv_serialconsole": false,
                "adv_traceback": true,
                "adv_uploadcrash": true,
                "adv_consolescreensaver": false,
                "adv_debugkernel": false,
                "adv_advancedmode": false,
                "adv_consolemsg": false,
                "adv_anonstats": true,
                "adv_autotune": false,
                "adv_powerdaemon": true,
                "adv_swapondrive": 2,
                "adv_anonstats_token": "",
                "adv_motd": "Welcome to FreeNAS",
                "adv_consolemenu": true,
                "id": 1,
                "adv_serialport": "0x2f8",
                "adv_serialspeed": "9600"
        }

   :json boolean adv_consolemenu: Enable Console Menu
   :json boolean adv_serialconsole: Use Serial Console
   :json string adv_serialport: 0x2f8, 0x3f8
   :json string adv_serialspeed: 9600, 19200, 38400, 57600, 115200
   :json boolean adv_consolescreensaver: Enable screen saver
   :json boolean adv_powerdaemon: Enable powerd (Power Saving Daemon)
   :json string adv_swapondrive: Swap size on each drive in GiB, affects new disks only
   :json boolean adv_consolemsg: Show console messages in the footer
   :json boolean adv_traceback: Show tracebacks in case of fatal errors
   :json boolean adv_uploadcrash: Upload kernel crashes to analysis
   :json boolean adv_advancedmode: Show advanced fields by default
   :json boolean adv_autotune: Enable autotune
   :json boolean adv_debugkernel: Enable debug kernel
   :json string adv_motd: MOTD banner
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 200: no error


Alert
-----

The Alert resource represents system alerts.

List resource
+++++++++++++

.. http:get:: /api/v1.0/system/alert/

   Returns a list of system alerts.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/alert/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        [{
                "id": "256ad2f48e5e541e28388701e34409cc",
                "level": "OK",
                "message": "The volume tank (ZFS) status is HEALTHY",
                "dismissed": false
        }]

   :resheader Content-Type: content type of the response
   :statuscode 200: no error


BootEnv
-------

The BootEnv resource represents the interface for the boot environment (beadm).

List resource
+++++++++++++

.. http:get:: /api/v1.0/system/bootenv/

   Returns a list of all boot environments.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/bootenv/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "id": "default",
                "active": "NR",
                "created": "2014-08-27T08:24:00",
                "name": "default",
                "space": "896.5M"
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 20
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/system/bootenv/

   Creates a new object and returns it.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/bootenv/ HTTP/1.1
      Content-Type: application/json

        {
                "name": "pre-changes",
                "source": "default"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "id": "pre-changes",
                "active": "-",
                "created": "2014-08-28T08:24:00",
                "name": "pre-changes",
                "space": "896.5M"
        }

   :json string name: name of the new boot environment
   :json string source: name of the boot environment to clone from
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/system/bootenv/(int:id)/

   Delete boot environment `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/system/bootenv/pre-changes/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


Email
--------

The Email resource represents the email settings.

List resource
+++++++++++++

.. http:get:: /api/v1.0/system/email/

   Returns the email settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/email/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "em_fromemail": "root@freenas.local",
                "em_outgoingserver": "",
                "em_pass": null,
                "em_port": 25,
                "em_security": "plain",
                "em_smtp": false,
                "em_user": null,
                "id": 1
        }

   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/system/email/

   Update email settins.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/system/email/ HTTP/1.1
      Content-Type: application/json

        {
                "em_fromemail": "william.spam@ixsystems.com",
                "em_outgoingserver": "mail.ixsystems.com",
                "em_pass": "changeme",
                "em_port": 25,
                "em_security": "plain",
                "em_smtp": true,
                "em_user": "william.spam@ixsystems.com"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "em_fromemail": "william.spam@ixsystems.com",
                "em_outgoingserver": "mail.ixsystems.com",
                "em_pass": "changeme",
                "em_port": 25,
                "em_security": "plain",
                "em_smtp": true,
                "em_user": "william.spam@ixsystems.com",
                "id": 1
        }

   :json string em_fromemail: from email address
   :json string em_outgoingserver: address of outgoing mail server
   :json interger em_port: port to connect to
   :json boolean em_smtp: use SMTP authentication
   :json string em_security: type of authentication (plain, ssl, tls)
   :json string em_user: username for auth
   :json string em_pass: username password
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 200: no error


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
   :query limit: limit number. default is 20
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

      HTTP/1.1 200 OK
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
   :statuscode 200: no error


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


Reboot
------

Reboot the machine.

List resource
+++++++++++++

.. http:post:: /api/v1.0/system/reboot/

   Reboot the machine.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/reboot/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

      Reboot process started.

   :resheader Content-Type: content type of the response
   :statuscode 202: no error


Settings
--------

The Settings resource represents the system settings.

List resource
+++++++++++++

.. http:get:: /api/v1.0/system/settings/

   Returns the settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/settings/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "stg_timezone": "America/Los_Angeles",
                "stg_guiport": 80,
                "stg_guihttpsport": 443,
                "stg_guihttpsredirect": true,
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

.. http:put:: /api/v1.0/system/settings/

   Update settings.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/system/settings/ HTTP/1.1
      Content-Type: application/json

        {
                "stg_timezone": "America/Sao_Paulo"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "stg_timezone": "America/Sao_Paulo",
                "stg_guiport": 80,
                "stg_guihttpsport": 443,
                "stg_guihttpsredirect": true,
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
   :json integer stg_guiport: WebGUI Port for HTTP
   :json integer stg_guihttpsport: WebGUI Port for HTTPS
   :json boolean stg_guihttpsredirect: Redirect HTTP (port 80) to HTTPS when only the HTTPS protocol is enabled
   :json string stg_language: webguil language
   :json string stg_kbdmap: see /usr/share/syscons/keymaps/INDEX.keymaps
   :json string stg_timezone: see /usr/share/zoneinfo
   :json string stg_syslogserver: Syslog server
   :json string stg_directoryservice: activedirectory, ldap, nt4, nis
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 200: no error


Certificate Authority
---------------------

The Certificate Authority resource represents SSL CAs.

List resource
+++++++++++++

.. http:get:: /api/v1.0/system/certificateauthority/

   Returns a list of all CAs.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/certificateauthority/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "CA_type_existing": true,
                "CA_type_intermediate": false,
                "CA_type_internal": false,
                "cert_CSR": "",
                "cert_DN": "/C=US/ST=CA/L=San Jose/O=iXsystems/CN=FreeNAS/emailAddress=example@ixsystems.com",
                "cert_certificate": "-----BEGIN CERTIFICATE-----\nMIIDyzCCArOgAwIBAgIBATANBgkqhkiG9w0BAQsFADB5MQswCQYDVQQGEwJVUzEL\nMAkGA1UECAwCQ0ExETAPBgNVBAcMCFNhbiBKb3NlMRIwEAYDVQQKDAlpWHN5c3Rl\nbXMxEDAOBgNVBAMMB0ZyZWVOQVMxJDAiBgkqhkiG9w0BCQEWFWV4YW1wbGVAaXhz\neXN0ZW1zLmNvbTAeFw0xNzA1MDQxODE1NTNaFw0yNzA1MDIxODE1NTNaMHkxCzAJ\nBgNVBAYTAlVTMQswCQYDVQQIDAJDQTERMA8GA1UEBwwIU2FuIEpvc2UxEjAQBgNV\nBAoMCWlYc3lzdGVtczEQMA4GA1UEAwwHRnJlZU5BUzEkMCIGCSqGSIb3DQEJARYV\nZXhhbXBsZUBpeHN5c3RlbXMuY29tMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIB\nCgKCAQEAySegmnWADTiNIDGlLD8310ZHUBGWr1Z58Mxx7Hd4C2aNeSOzWeuvJXps\nDnXAeyTJCZTF0o02dzjy5vTOEojXIwniyTDlHPsvDYl4nYyKexgWWtBqhssJlUzG\nrdL211huXzzPNZHClWz8f5KJRz0mSwF7v80WIN4P+xVa9G71xqAikv1f42QHUWch\nAzwKMHNg+fgny6o7y4s2thP6kphiPHHBaHjGh4C2pzuUHt23HM2cC7e8xHHwTilc\nyQksdTZNHrKp36wQWDRegx8+j5GIHGB0AAG9klFU2SygI5VDkcLR1xEQ4uEgB6nO\npBwotwchrXMiannRdM7AN/7M1jNOIQIDAQABo14wXDAaBgNVHREEEzARhg9odHRw\nczovL0ZyZWVOQVMwDwYDVR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8EBAMCAQYwHQYD\nVR0OBBYEFIkAJ+kCRkF7S9Uiv6XsU7wyzJbNMA0GCSqGSIb3DQEBCwUAA4IBAQCm\nktWJxOtOn032Tp9nyyKjm2zcotIHCldoM28YrH7wE901hRZBVWsc+786q5nzFxxc\nu9T0H/8GgRhVe4vXyzCrtdUhr9vkJ+/LiXFkbTbF87o/BgbSCKRsqlYpXsZ0+Arl\n7UD5ISbN7M4yPyeUFfHB8B/OEryr8QOP1ZXQjg/lQJR7+Jg3LGuN3UpUTWDIFwpW\n4DECEuLzlwvbkgXxgOvjZtSgsJncwS7luOtBv45/uqYG1Ya51HHortuW4MzSbBgO\nVDc+lczPglq+O1Ig5rewBWx9AXW9EqvR6lMey4rIOXD4P+/h663V+rYSfsYYGABA\nwIM8nUIcfgI5Vn9aeDx9\n-----END CERTIFICATE-----",
                "cert_chain": false,
                "cert_city": "San Jose",
                "cert_common": "FreeNAS",
                "cert_country": "US",
                "cert_digest_algorithm": "SHA256",
                "cert_email": "example@ixsystems.com",
                "cert_from": "Thu May  4 18:15:53 2017",
                "cert_internal": "NO",
                "cert_issuer": "external",
                "cert_key_length": 2048,
                "cert_lifetime": 3650,
                "cert_name": "importca",
                "cert_ncertificates": 0,
                "cert_organization": "iXsystems",
                "cert_privatekey": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDJJ6CadYANOI0g\nMaUsPzfXRkdQEZavVnnwzHHsd3gLZo15I7NZ668lemwOdcB7JMkJlMXSjTZ3OPLm\n9M4SiNcjCeLJMOUc+y8NiXidjIp7GBZa0GqGywmVTMat0vbXWG5fPM81kcKVbPx/\nkolHPSZLAXu/zRYg3g/7FVr0bvXGoCKS/V/jZAdRZyEDPAowc2D5+CfLqjvLiza2\nE/qSmGI8ccFoeMaHgLanO5Qe3bcczZwLt7zEcfBOKVzJCSx1Nk0esqnfrBBYNF6D\nHz6PkYgcYHQAAb2SUVTZLKAjlUORwtHXERDi4SAHqc6kHCi3ByGtcyJqedF0zsA3\n/szWM04hAgMBAAECggEBAILisQKv39E6ccF37CSdQeVmSjKULzsJhrCjJqGZnte0\nM+uVyjaBP2aggLzr64F1DwaX8hwtXDo5KPwUYB35Qhr/bLxCf2HbIuOpBn1lHBo6\nMxmGMTph1Gt8GG60LX8zgCWh+KW/oR//WVBc9cwPwuHdJjtH49UhCL70R0lzBaLm\nGbWm1gkFTeNw4eEMQbWASTbg150d/pcrY9+auoFPb3nugpAkf3UNN6+/phEe3F2h\ni/lfsDcsvqJtiN7zp5RROU11P16uuvka3FvyBRkWL+y/5ZSSad5gsA984xFK+TLy\nEiml1NOEbduRusNtcqH++/vA/6Sfk9gCmMPvtZnWDBECgYEA784mQUYNMEHVC+/3\ngETk1Iz3f4WL3NYNe1jllQB0cmRbWKNycSWVqHKEznf0oBmUI8ujT9FnJuj4kb5b\nirrw9wkB3lLWsmjs+NO3D/Bo60GPHMqhecbGS0DCkadHl5xCeIVSkDLv+XsztD4g\nASeOf1fnMLYEcWMT0vnjOqZMVYUCgYEA1r1F2M2AfFiVomZrRhDitHYE7DhG/cCG\nHL55PVeh3TCFzdgBxHPrCf9usPKpNJ45mSGK+c5sDDw9qZggJF9MLSTYgI6Ub94c\nQSZrsyaMzuenZ8lxNB2a9KeaX8Hvj4Dx8XmzzUmkyr7qchaMMrS5ZGS0hjeyKw5r\ncakuJGIIOu0CgYALyiDLWLxRQQtOWO/cGIb/hCau2Ev2AXgMNmSjHLCc5x4uj2qS\n8XwYGfk5hWA7dsZ3tA1FYVAm85E06RzrByHNo126JmxzvQDZgt8fI3ylBEYa7kNe\nD020aWynaIf2hjImZreWa0qtA0eZduxv4hf5XsL4/Bnf0TUqTCrFuWNLWQKBgQCa\npXJQwSY/5pfUfcfRjMWHStsetyTBB85NkwrDF4IVRiWGaYJUVVq2N4Mi4Y7juvMm\nCZcJchQz94o8wbacGxlEBZ35bzUNHzrf3GiBe0i6lO/leZgR/SQj/zPYtFTu1uDm\nk0vekqOf8z/p670Jo0dEOpYbdq7T/S15jGoTf5oHvQKBgFbz42qNU3aHiu92Yr0e\nmGXGZVYZPZhPBofxFWzGolkCBFKS0hPhQj2SgieO3FvOHb00z+cwUn69Gb4JHIMc\nqzGmH5oUC0+mOYBLoixSDQYJ3KuHv1OylPjUi8oMCJbSXRLLysOznObFh6ovPO78\nnOQPi/2+C2qiu0mzKc41L31e\n-----END PRIVATE KEY-----",
                "cert_serial": 2,
                "cert_state": "CA",
                "cert_type": 1,
                "cert_until": "Sun May  2 18:15:53 2027",
                "id": 1

        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 20
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create Internal CA
++++++++++++++++++

.. http:post:: /api/v1.0/system/certificateauthority/internal/

   Creates a CA and returns the object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/certificateauthority/internal/ HTTP/1.1
      Content-Type: application/json

        {
                "cert_city": "San Jose",
                "cert_email": "example@ixsystems.com",
                "cert_common": "FreeNAS",
                "cert_country": "US",
                "cert_digest_algorithm": "SHA256",
                "cert_lifetime": 3650,
                "cert_name": "internalca",
                "cert_organization": "iXsystems",
                "cert_state": "CA",
                "cert_key_length": 2048
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        Certificate Authority created.

   :json string cert_name: identifier
   :json string cert_common: certificate common name
   :json string cert_city: certificate city
   :json string cert_state: certificate state
   :json string cert_country: certificate country (2 chars)
   :json string cert_email: cetificate email
   :json string cert_organization: certificate organization
   :json string cert_digest_algorithm: digest algorithm (SHA1, SHA224, SHA256, SHA384, SHA512)
   :json integer cert_lifetime: certificate lifetime in days
   :json integer cert_key_length: certificate key length (1024, 2048, 4096)
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Create Intermediate CA
++++++++++++++++++++++

.. http:post:: /api/v1.0/system/certificateauthority/intermediate/

   Creates a CA and returns the object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/certificateauthority/intermediate/ HTTP/1.1
      Content-Type: application/json

        {
                "cert_city": "San Jose",
                "cert_email": "example@ixsystems.com",
                "cert_common": "FreeNAS",
                "cert_country": "US",
                "cert_digest_algorithm": "SHA256",
                "cert_lifetime": 3650,
                "cert_name": "intermediateca",
                "cert_organization": "iXsystems",
                "cert_state": "CA",
                "cert_key_length": 2048,
                "cert_signedby": 1
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        Certificate Authority created.

   :json string cert_name: identifier
   :json string cert_common: certificate common name
   :json string cert_city: certificate city
   :json string cert_state: certificate state
   :json string cert_country: certificate country (2 chars)
   :json string cert_email: cetificate email
   :json string cert_organization: certificate organization
   :json string cert_digest_algorithm: digest algorithm (SHA1, SHA224, SHA256, SHA384, SHA512)
   :json integer cert_lifetime: certificate lifetime in days
   :json integer cert_key_length: certificate key length (1024, 2048, 4096)
   :json integer cert_signedby: id of the certificate authority
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Import CA
+++++++++

.. http:post:: /api/v1.0/system/certificateauthority/import/

   Creates a CA and returns the object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/certificateauthority/import/ HTTP/1.1
      Content-Type: application/json

        {
                "cert_name": "importca",
                "cert_certificate": "-----BEGIN CERTIFICATE-----\nMIIDyzCCArOgAwIBAgIBATANBgkqhkiG9w0BAQsFADB5MQswCQYDVQQGEwJVUzEL\nMAkGA1UECAwCQ0ExETAPBgNVBAcMCFNhbiBKb3NlMRIwEAYDVQQKDAlpWHN5c3Rl\nbXMxEDAOBgNVBAMMB0ZyZWVOQVMxJDAiBgkqhkiG9w0BCQEWFWV4YW1wbGVAaXhz\neXN0ZW1zLmNvbTAeFw0xNzA1MDQxODE1NTNaFw0yNzA1MDIxODE1NTNaMHkxCzAJ\nBgNVBAYTAlVTMQswCQYDVQQIDAJDQTERMA8GA1UEBwwIU2FuIEpvc2UxEjAQBgNV\nBAoMCWlYc3lzdGVtczEQMA4GA1UEAwwHRnJlZU5BUzEkMCIGCSqGSIb3DQEJARYV\nZXhhbXBsZUBpeHN5c3RlbXMuY29tMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIB\nCgKCAQEAySegmnWADTiNIDGlLD8310ZHUBGWr1Z58Mxx7Hd4C2aNeSOzWeuvJXps\nDnXAeyTJCZTF0o02dzjy5vTOEojXIwniyTDlHPsvDYl4nYyKexgWWtBqhssJlUzG\nrdL211huXzzPNZHClWz8f5KJRz0mSwF7v80WIN4P+xVa9G71xqAikv1f42QHUWch\nAzwKMHNg+fgny6o7y4s2thP6kphiPHHBaHjGh4C2pzuUHt23HM2cC7e8xHHwTilc\nyQksdTZNHrKp36wQWDRegx8+j5GIHGB0AAG9klFU2SygI5VDkcLR1xEQ4uEgB6nO\npBwotwchrXMiannRdM7AN/7M1jNOIQIDAQABo14wXDAaBgNVHREEEzARhg9odHRw\nczovL0ZyZWVOQVMwDwYDVR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8EBAMCAQYwHQYD\nVR0OBBYEFIkAJ+kCRkF7S9Uiv6XsU7wyzJbNMA0GCSqGSIb3DQEBCwUAA4IBAQCm\nktWJxOtOn032Tp9nyyKjm2zcotIHCldoM28YrH7wE901hRZBVWsc+786q5nzFxxc\nu9T0H/8GgRhVe4vXyzCrtdUhr9vkJ+/LiXFkbTbF87o/BgbSCKRsqlYpXsZ0+Arl\n7UD5ISbN7M4yPyeUFfHB8B/OEryr8QOP1ZXQjg/lQJR7+Jg3LGuN3UpUTWDIFwpW\n4DECEuLzlwvbkgXxgOvjZtSgsJncwS7luOtBv45/uqYG1Ya51HHortuW4MzSbBgO\nVDc+lczPglq+O1Ig5rewBWx9AXW9EqvR6lMey4rIOXD4P+/h663V+rYSfsYYGABA\nwIM8nUIcfgI5Vn9aeDx9\n-----END CERTIFICATE-----\n",
                "cert_privatekey": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDJJ6CadYANOI0g\nMaUsPzfXRkdQEZavVnnwzHHsd3gLZo15I7NZ668lemwOdcB7JMkJlMXSjTZ3OPLm\n9M4SiNcjCeLJMOUc+y8NiXidjIp7GBZa0GqGywmVTMat0vbXWG5fPM81kcKVbPx/\nkolHPSZLAXu/zRYg3g/7FVr0bvXGoCKS/V/jZAdRZyEDPAowc2D5+CfLqjvLiza2\nE/qSmGI8ccFoeMaHgLanO5Qe3bcczZwLt7zEcfBOKVzJCSx1Nk0esqnfrBBYNF6D\nHz6PkYgcYHQAAb2SUVTZLKAjlUORwtHXERDi4SAHqc6kHCi3ByGtcyJqedF0zsA3\n/szWM04hAgMBAAECggEBAILisQKv39E6ccF37CSdQeVmSjKULzsJhrCjJqGZnte0\nM+uVyjaBP2aggLzr64F1DwaX8hwtXDo5KPwUYB35Qhr/bLxCf2HbIuOpBn1lHBo6\nMxmGMTph1Gt8GG60LX8zgCWh+KW/oR//WVBc9cwPwuHdJjtH49UhCL70R0lzBaLm\nGbWm1gkFTeNw4eEMQbWASTbg150d/pcrY9+auoFPb3nugpAkf3UNN6+/phEe3F2h\ni/lfsDcsvqJtiN7zp5RROU11P16uuvka3FvyBRkWL+y/5ZSSad5gsA984xFK+TLy\nEiml1NOEbduRusNtcqH++/vA/6Sfk9gCmMPvtZnWDBECgYEA784mQUYNMEHVC+/3\ngETk1Iz3f4WL3NYNe1jllQB0cmRbWKNycSWVqHKEznf0oBmUI8ujT9FnJuj4kb5b\nirrw9wkB3lLWsmjs+NO3D/Bo60GPHMqhecbGS0DCkadHl5xCeIVSkDLv+XsztD4g\nASeOf1fnMLYEcWMT0vnjOqZMVYUCgYEA1r1F2M2AfFiVomZrRhDitHYE7DhG/cCG\nHL55PVeh3TCFzdgBxHPrCf9usPKpNJ45mSGK+c5sDDw9qZggJF9MLSTYgI6Ub94c\nQSZrsyaMzuenZ8lxNB2a9KeaX8Hvj4Dx8XmzzUmkyr7qchaMMrS5ZGS0hjeyKw5r\ncakuJGIIOu0CgYALyiDLWLxRQQtOWO/cGIb/hCau2Ev2AXgMNmSjHLCc5x4uj2qS\n8XwYGfk5hWA7dsZ3tA1FYVAm85E06RzrByHNo126JmxzvQDZgt8fI3ylBEYa7kNe\nD020aWynaIf2hjImZreWa0qtA0eZduxv4hf5XsL4/Bnf0TUqTCrFuWNLWQKBgQCa\npXJQwSY/5pfUfcfRjMWHStsetyTBB85NkwrDF4IVRiWGaYJUVVq2N4Mi4Y7juvMm\nCZcJchQz94o8wbacGxlEBZ35bzUNHzrf3GiBe0i6lO/leZgR/SQj/zPYtFTu1uDm\nk0vekqOf8z/p670Jo0dEOpYbdq7T/S15jGoTf5oHvQKBgFbz42qNU3aHiu92Yr0e\nmGXGZVYZPZhPBofxFWzGolkCBFKS0hPhQj2SgieO3FvOHb00z+cwUn69Gb4JHIMc\nqzGmH5oUC0+mOYBLoixSDQYJ3KuHv1OylPjUi8oMCJbSXRLLysOznObFh6ovPO78\nnOQPi/2+C2qiu0mzKc41L31e\n-----END PRIVATE KEY-----\n",
                "cert_serial": 2
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        Certificate Authority imported.

   :json string cert_name: identifier
   :json string cert_certificate: encoded certificate
   :json string cert_privatekey: encoded private key (if any)
   :json integer cert_serial: certificate serial
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/system/certificateauthority/(int:id)/

   Delete CA `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/system/certificateauthority/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


Certificate
-----------

The Certificate resource represents SSL Certificates.

List resource
+++++++++++++

.. http:get:: /api/v1.0/system/certificate/

   Returns a list of certificates.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/certificate/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {

        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 20
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create Internal Certificate
+++++++++++++++++++++++++++

.. http:post:: /api/v1.0/system/certificate/internal/

   Creates a Certificate and returns the object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/certificate/internal/ HTTP/1.1
      Content-Type: application/json

        {
                "cert_city": "San Jose",
                "cert_email": "example@ixsystems.com",
                "cert_common": "FreeNAS",
                "cert_country": "US",
                "cert_digest_algorithm": "SHA256",
                "cert_lifetime": 3650,
                "cert_name": "internalcert",
                "cert_organization": "iXsystems",
                "cert_state": "CA",
                "cert_key_length": 2048,
                "cert_signedby": 1
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        Certificate created.

   :json string cert_name: identifier
   :json string cert_common: certificate common name
   :json string cert_city: certificate city
   :json string cert_state: certificate state
   :json string cert_country: certificate country (2 chars)
   :json string cert_email: cetificate email
   :json string cert_organization: certificate organization
   :json string cert_digest_algorithm: digest algorithm (SHA1, SHA224, SHA256, SHA384, SHA512)
   :json integer cert_lifetime: certificate lifetime in days
   :json integer cert_key_length: certificate key length (1024, 2048, 4096)
   :json integer cert_signedby: id of the certificate authority
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Create CSR
++++++++++

.. http:post:: /api/v1.0/system/certificate/csr/

   Creates a CSR and returns the object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/certificate/csr/ HTTP/1.1
      Content-Type: application/json

        {
                "cert_city": "San Jose",
                "cert_email": "example@ixsystems.com",
                "cert_common": "FreeNAS",
                "cert_country": "US",
                "cert_digest_algorithm": "SHA256",
                "cert_lifetime": 3650,
                "cert_name": "csr",
                "cert_organization": "iXsystems",
                "cert_state": "CA",
                "cert_key_length": 2048
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        Certificate Signing Request created.

   :json string cert_name: identifier
   :json string cert_common: certificate common name
   :json string cert_city: certificate city
   :json string cert_state: certificate state
   :json string cert_country: certificate country (2 chars)
   :json string cert_email: cetificate email
   :json string cert_organization: certificate organization
   :json string cert_digest_algorithm: digest algorithm (SHA1, SHA224, SHA256, SHA384, SHA512)
   :json integer cert_lifetime: certificate lifetime in days
   :json integer cert_key_length: certificate key length (1024, 2048, 4096)
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Import CA
+++++++++

.. http:post:: /api/v1.0/system/certificate/import/

   Imports a Certificate and returns the object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/certificate/import/ HTTP/1.1
      Content-Type: application/json

        {
                "cert_name": "importcertificate",
                "cert_certificate": "-----BEGIN CERTIFICATE-----\nMIIDqjCCApKgAwIBAgIBAjANBgkqhkiG9w0BAQsFADB5MQswCQYDVQQGEwJVUzEL\nMAkGA1UECAwCQ0ExETAPBgNVBAcMCFNhbiBKb3NlMRIwEAYDVQQKDAlpWHN5c3Rl\nbXMxEDAOBgNVBAMMB0ZyZWVOQVMxJDAiBgkqhkiG9w0BCQEWFWV4YW1wbGVAaXhz\neXN0ZW1zLmNvbTAeFw0xNzA1MDQxOTEzMzVaFw0yNzA1MDIxOTEzMzVaMHkxCzAJ\nBgNVBAYTAlVTMQswCQYDVQQIDAJDQTERMA8GA1UEBwwIU2FuIEpvc2UxEjAQBgNV\nBAoMCWlYc3lzdGVtczEQMA4GA1UEAwwHRnJlZU5BUzEkMCIGCSqGSIb3DQEJARYV\nZXhhbXBsZUBpeHN5c3RlbXMuY29tMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIB\nCgKCAQEAz6ok2HVC6Pl/Ezv67nZncgyr6US5479bzIsRXZLuXS8NIElVbTlIOAOD\nQobXEZnuAhg4gNk5KaU4yAg79pKE6VbKBQs0DI1kULjkUEL7Z9Hd9p31wvGUJJQm\nPwHMLMnfmzyy8M4b+bpeSafjjk3zOopBP2/mJcnY/4q/Qi++lkY7yz+GW3YgHL3c\nh2XkoA1Q+oMN39uZ+HnGhmjiiIyfwbtgCRfsw70bg20XsrvnX9lSAFZyAzgYt6nP\n4Ms27Z3hCFuXm05azM9/loTZU++egxR3rJ9j9xzd/FOW5PYXCFh7UiMKKPWQjYi4\nit2GyPAsrkyHgsrkuINEKQJ7fmHIvwIDAQABoz0wOzAaBgNVHREEEzARhg9odHRw\nczovL0ZyZWVOQVMwHQYDVR0OBBYEFBcQve6AOOh9DWK6ctdV+b/uQAWfMA0GCSqG\nSIb3DQEBCwUAA4IBAQBYSLv0VliKo9QTPkT2qgZr9TVhjSjx0G+EmlnOdUuAYe2b\nhj8myxdzNNa5nrHcXN/aVRI7vcRQy575jpGIvZ914U4l28XHgLFtfgkxjh/FLZii\nFv3bwqZKLZYQgt/4r301+FMMJK3bpR3WSyiDYdDvcuYRMGX76mNbJ/V6q2pI0lqi\nFXebaYXyIOaAORzC/ltlZxgF23zNqqMB16MzS/u5kvdcTHwI3peiPDr0FjM2zyOv\nZrQ3Dk7KyQ/bvNwu1wHIigY9xinEnzyv5iuZ4p55zugw8kbe0QnlIgUO6YY4wjdC\nXGFhV/08YraeY9rkB6X+ygRDzaFtg9Jve1cFploo\n-----END CERTIFICATE-----\n",
                "cert_privatekey": "-----BEGIN PRIVATE KEY-----\nMIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQDPqiTYdULo+X8T\nO/rudmdyDKvpRLnjv1vMixFdku5dLw0gSVVtOUg4A4NChtcRme4CGDiA2TkppTjI\nCDv2koTpVsoFCzQMjWRQuORQQvtn0d32nfXC8ZQklCY/Acwsyd+bPLLwzhv5ul5J\np+OOTfM6ikE/b+Ylydj/ir9CL76WRjvLP4ZbdiAcvdyHZeSgDVD6gw3f25n4ecaG\naOKIjJ/Bu2AJF+zDvRuDbReyu+df2VIAVnIDOBi3qc/gyzbtneEIW5ebTlrMz3+W\nhNlT756DFHesn2P3HN38U5bk9hcIWHtSIwoo9ZCNiLiK3YbI8CyuTIeCyuS4g0Qp\nAnt+Yci/AgMBAAECggEBAKiE2zepGO40obG7J+vhvBqqO8ul0PAHtvgrFqGH/dUy\nvIUp3aAwLvH9r8QJ5nfLIYEjpJ6zKJcqFAUH4Zk7143/txsWt1tEVlbHY8faQ2hB\nv81E7E4RevWgH9VboRPrkoDIZjHSIJOscJ13F8vAaBRmY4KWTP73aRgewQx18ETD\nLJ/uwL/XD4wQ0GzxTregJYdjg6ePB4tVoTwR0jxF/8QUj/xHluGGxqhkwkSpTCMY\n6o0L1hj6Zqvq1kkH/xkOqiP6Bs8o0Aa+i8jqbm4o6575LAPnoJ1Dq5TdIK/ph1Jx\n4zKnNbo7ep8gY6mcznzF6bWmKlip4KUwddaZcA+sNAkCgYEA+VOSjXsbX9RQWVNH\nf20qi7d2/gHYeiErfhWZQU7/tRFF3vsfmI9bpqdimrSf3ItEyIBjz28fZzk3dvCF\nVVg0pwD8KL8HhITJh1fouT2QivDQVoCnAxTl72Xn20FnvMUK7cPtGzl0Ai14PxNJ\ndp8GPFSfWPaEvp2zQNFYVeErKG0CgYEA1TkY86ByFxmOa6bnhHfRGCnVXEIaLRJg\nh0m+be+PWivQklr0mjoev8lmnKi4C9RoHAyPVJl+sJF1M21T/67ANPd2kDLGBmoS\nXe3RYYjdgEWYu5/VpCiaHcW9VuymKMx+UiiFp2E3TEW9KE42jyDgd9+kvSVaokew\nXle4mBXF0lsCgYAeH3i/WzZNd6tVf3hN7vSK+NmJitOKveMxUo63k0HVsIaOkCyb\nFAbwtZx2MIh37uOajdiBQV277O/EkP6q9wM1gir1CU9xNVHb5kUZzFRgVQP2z4he\nGPJG4DsJBHfyGKRfYaKN/X0EnlW+2SexCzmHpHm0F+Sl2wvDMwfHKHM8aQKBgQCe\nPUKcQ52IMSo2EGbPM5CU6y7xygjdHD9RB9RwiBIOLGgcxa2z66A4WwJxDvGPrfIZ\npuSUN1oDNeAR63gkT49Lf7+Y4mV+CyhYVw9F4CnqcTwZOlR2AL/nioGqyfPCYYj5\n9iLChm5gh30LNYheDlsn+2yqBtfNiYCFc3qGO9pU8wKBgQC/XpN2+wUQp+pv4YgC\np/Is/Lve2C/Rp/C3Za7Dx05uqTG9xnktISufXTuM0jU3EP7ismjtNQOy+alcu+7t\n27nuoLf6EWiUeIIEPovFLNxvKnHaIdjNpuIyY1oup7RSSGx1IfeuRdBi+3e4pi2N\njJOOCAmlr2acAI3jR3ZLOsSPzA==\n-----END PRIVATE KEY-----\n",
                "cert_serial": null
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        Certificate imported.

   :json string cert_name: identifier
   :json string cert_certificate: encoded certificate
   :json string cert_privatekey: encoded private key (if any)
   :json integer cert_serial: certificate serial
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/system/certificate/(int:id)/

   Delete Certificate `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/system/certificate/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


Shutdown
--------

Shutdown the machine.

List resource
+++++++++++++

.. http:post:: /api/v1.0/system/shutdown/

   Shutdown the machine.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/shutdown/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

      Shutdown process started.

   :resheader Content-Type: content type of the response
   :statuscode 202: no error


Tunable
----------

The Tunable resource represents sysctl.conf(5) and loader.conf(5) tunables.

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
                "tun_type": "loader",
                "tun_enabled": true
                "id": 1,
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 20
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
                "tun_type": "loader"
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
                "tun_enabled": true,
                "tun_type": "loader",
                "id": 1
        }

   :json string tun_var: name of the tunable
   :json string tun_value: value of the tunable
   :json string tun_type: type of the tunable (sysctl/loader/rc)
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

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "tun_var": "xhci_load",
                "tun_comment": "",
                "tun_value": "YES",
                "tun_enabled": false,
                "tun_type": "loader",
                "id": 1
        }

   :json string tun_var: name of the tunable
   :json string tun_value: value of the tunable
   :json string tun_type: type of the tunable (sysctl/loader/rc)
   :json string tun_comment: user comment for the entry
   :json boolean tun_enabled: whether the entry is enabled
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 200: no error


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


Version
--------

Version of the software installed.

List resource
+++++++++++++

.. http:get:: /api/v1.0/system/version/

   Returns the version dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/version/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "fullversion": "FreeNAS-9.2.2-ALPHA-a346239-x64",
                "name": "FreeNAS",
                "version": "9.2.2-ALPHA"
        }

   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Configuration
-------------

Configuration handling.

Factory Restore
+++++++++++++++

.. http:post:: /api/v1.0/system/config/factory_restore/

   Perform a factory restore. A reboot is necessary after this operation.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/config/factory_restore/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        Factory restore completed. Reboot is required.

   :resheader Content-Type: content type of the response
   :statuscode 202: no error


Update
------

Manage updates.

Check pending updates
+++++++++++++++++++++

.. http:get:: /api/v1.0/system/update/check/

   Return an array of updates downloaded and waiting to be applied.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/update/check/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        []

   :resheader Content-Type: content type of the response
   :statuscode 200: no error

Perform Update
++++++++++++++

.. http:post:: /api/v1.0/system/update/update/

   Download and apply update.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/update/update/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        "Successfully updated."

   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Debug
-----

Generate debug
++++++++++++++

.. http:post:: /api/v1.0/system/debug/

   Returns url to download the tarball.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/debug/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "url": "/system/debug/download/"
        }

   :resheader Content-Type: content type of the response
   :statuscode 200: no error

