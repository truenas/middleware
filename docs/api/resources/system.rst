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


SSL
---

The SSL resource represents the WebGUI SSL certificate settings.

List resource
+++++++++++++

.. http:get:: /api/v1.0/system/ssl/

   Returns the SSL settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/ssl/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "ssl_certfile": "",
                "ssl_city": null,
                "ssl_common": null,
                "ssl_country": null,
                "ssl_email": null,
                "ssl_org": null,
                "ssl_passphrase": null,
                "ssl_state": null,
                "ssl_unit": null
        }

   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/system/ssl/

   Update SSL certificate settings.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/system/ssl/ HTTP/1.1
      Content-Type: application/json

        {
                "ssl_city": "Curitiba",
                "ssl_common": "iXsystems",
                "ssl_country": "BR",
                "ssl_email": "william.spam@ixsystems.com",
                "ssl_org": "iXsystems",
                "ssl_state": "Parana",
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "ssl_city": "Curitiba",
                "ssl_common": "iXsystems",
                "ssl_country": "BR",
                "ssl_email": "william.spam@ixsystems.com",
                "ssl_org": "iXsystems",
                "ssl_state": "Parana",
                "ssl_unit": "",
                "ssl_certfile": "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA7kHKPIs/xj8FRJ6TY21tKhGRQ7tcKKMDlPLUHy0s/uwy3NNX\n8r9CWvtX7k+bJz7bnbDKFOuqLYRPFdS9bpB7ib2u9xFdSOWfa10DxpX8XECmNqC8\n6pt8eJhTCil/uXWZLZnPedh5F2NK0gW8mfU2iignSPrS+Cq9c0ftPP6BNNHCX/PU\n8ReGP+OCF2m9QHPwgQSxJzJIZzGRyLQA5Wvy6pzBFSfR6md9ZHoA0no/K+lfLLNR\nXJKXdMcHKU6n6Bq28iPQ+rF5gF/s2LHFlO38Y+0E1fH3EMxDS8pMYSeFKPrmW4Bd\nuarzjPL1hQ92KL4zC95jwUtP1h3BDTGhQJaqQQIDAQABAoIBAQDkbT0o+NSHDErP\ntD1Y+UPNLpSYXJyJ9WhsuLd4wIZATlKhdxr+CDLlKc7vE3GMme5S7HmCv0MkapKs\nOo/33hwjPjHufL50Mnq6o64ICiqug+kXvNoDEFmxAVG0D39+XuoiVzIc/tdx/edx\nHsDo1rmYkdDAXoJAHjIOwaoJbXSRHqTrhxvEozvlxEPP6kvXSGNcM/qfH2YOhsNr\ne3eyeTA5qOXKkNQscXroW7CS1UvOumjZ24P/6ZXnVwEnoNahe3sIJl7J/QVJ1m1J\nkD4CrFNNVGzA8vveisJx+gx+z9kvnRx5ebwAQpUUcA1dLFMIRiXoVBSP/fknaN7C\nN16f42fBAoGBAPg1GUCe15wAuTgz0eYdgjjWMwRFq1x9GgKxEM+X+hrCo82ax66l\n/YxqVjzZSodz5OhKVAFHmULWkXUyLoX8LHL4MIvV/rCnA9ZQr8+4sSPQc56isuJP\nojqt2sDsbTL40VgnFPFiXIRyYGQIOgGP3Dp6VRtw/ea7QqKLJktpevsJAoGBAPW8\nt6pidhWqnadn0ND3Nbb6+axhITTDWKNJoBuM1DUHvotVSe8WMDYT6Dx/ORX+Z24/\n79topCd1d3pdTPcHvMCs+A22Dbi9aUanHNtFldUs6cWdUENaqidmN79Xt6svYgdl\ncdm6R+GTNSyTG/bdvdfudWzA/Kpn9jmJVz+IT6t5AoGBAJjtRljNRXTl8TjSnMHW\nbpSMTTSVpGZA4hTEeeId9kgkon4cnmlZ9mVcYzPsgYIBgwkoOqfrMF/BCjAWMhn1\nbIGNr4OI3vqCfNfAMQKf/exeE86q2eKcRA05bu2s/f8I1RsmQT4UZ4JnYkJf2zV5\nKKyTEPruXFGcEQtLBtYx8EbZAoGAcF4rXi5H8QBjtvkx81wXo+R/5uNDW+03yvMP\n04lCQD2aU/xcIofy48eWmpNSd0wt36w88geXiLOePsYLO6q+FR0DEMH+5Es4qKYh\n++KF8UToYQTefu4mgH2tYEGsKwsvuFIbDYSw+eVmm0tprikXdnYEHAbjgsinPwge\nbV7Xj4ECgYA4L+lvjaVD3+D3896PKCUcGKRRNYfDBcCL1BcogtrOYqr4wPpTQSZ5\nb5J6al98ECi9TMz/r0wc+zqBgh8O69QiQkGtk4CHwneNu15V6y7gHUMADoydFdCd\nRS9VJrh9ZFnWAyyqWrdnGEB8b/SEwgZCDQzipxffditKTqiLc8V7Vg==\n-----END RSA PRIVATE KEY-----\n-----BEGIN CERTIFICATE-----\nMIIDpjCCAo4CCQCZcuP48SVpozANBgkqhkiG9w0BAQUFADCBlDEYMBYGA1UEChMP\naVhzeXN0ZW1zLCBJbmMuMRAwDgYDVQQLEwdTeXN0ZW1zMR0wGwYJKoZIhvcNAQkB\nFg5yb290QGxvY2FsaG9zdDERMA8GA1UEBxMIU2FuIEpvc2UxEzARBgNVBAgTCkNh\nbGlmb3JuaWExCzAJBgNVBAYTAlVTMRIwEAYDVQQDEwlsb2NhbGhvc3QwHhcNMTQw\nNjIwMTY1ODU2WhcNMTQwNzIwMTY1ODU2WjCBlDEYMBYGA1UEChMPaVhzeXN0ZW1z\nLCBJbmMuMRAwDgYDVQQLEwdTeXN0ZW1zMR0wGwYJKoZIhvcNAQkBFg5yb290QGxv\nY2FsaG9zdDERMA8GA1UEBxMIU2FuIEpvc2UxEzARBgNVBAgTCkNhbGlmb3JuaWEx\nCzAJBgNVBAYTAlVTMRIwEAYDVQQDEwlsb2NhbGhvc3QwggEiMA0GCSqGSIb3DQEB\nAQUAA4IBDwAwggEKAoIBAQDuQco8iz/GPwVEnpNjbW0qEZFDu1woowOU8tQfLSz+\n7DLc01fyv0Ja+1fuT5snPtudsMoU66othE8V1L1ukHuJva73EV1I5Z9rXQPGlfxc\nQKY2oLzqm3x4mFMKKX+5dZktmc952HkXY0rSBbyZ9TaKKCdI+tL4Kr1zR+08/oE0\n0cJf89TxF4Y/44IXab1Ac/CBBLEnMkhnMZHItADla/LqnMEVJ9HqZ31kegDSej8r\n6V8ss1Fckpd0xwcpTqfoGrbyI9D6sXmAX+zYscWU7fxj7QTV8fcQzENLykxhJ4Uo\n+uZbgF25qvOM8vWFD3YovjML3mPBS0/WHcENMaFAlqpBAgMBAAEwDQYJKoZIhvcN\nAQEFBQADggEBAAhxxD8Xn9+5rD5U/ep7+Ccv8DM8cqkVkz1u6BAnQVl2fs7QjqPr\nvuNdk43HeUf0rQTklY+fH4PlpNa83mZ6wBl1VqGf5hUhQyRVeZIDPI+eO3qX1yXO\nRlKFDqkwicLPoNupp+Fk+eJs7769d9E1hGLYdqHQW2U5ft7sUzzun4wV6EutMnOK\nuLCDcfWVh4qb0IXsYA17KE2xyPa8XUNQpLqFQIexTYYPpkzsu7wzanD8HFAiE/9l\nxVo8o8fs7epZhGcsc0oDMjOgBF7xsRe7aGC9ivcQsFmkOMeizpNaaCx+0n4CpS4m\nbJPjbCgrVRr3qePov4K5Olk//xs81qckDMU=\n-----END CERTIFICATE-----"
                "id": 1,
        }

   :json string ssl_city: locality name, eg city
   :json string ssl_common: common name
   :json string ssl_country: country name, 2 letter code
   :json string ssl_state: state or province name
   :json string ssl_org: organization name
   :json string ssl_email: email address
   :json string ssl_unit: organizational unit name
   :json string ssl_passphrase: private key passphrase
   :json string ssl_certfile: private and public certificates
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 200: no error


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

