=========
Services
=========

Resources related to services.

Services
----------

The Services resource is used to control services.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/services/

   Returns a list of all available services.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/services/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "srv_service": "rsync",
                "id": 16,
                "srv_enable": false
        },
        {
                "srv_service": "directoryservice",
                "id": 17,
                "srv_enable": false
        },
        {
                "srv_service": "smartd",
                "id": 18,
                "srv_enable": false
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/services/(int:id|string:srv_service)/

   Update service with id `id` or name `srv_service`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/services/cifs/ HTTP/1.1
      Content-Type: application/json

        {
                "srv_enable": true
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "srv_service": "cifs",
                "id": 4,
                "srv_enable": true
        }

   :json string srv_service: name of the service
   :json boolean srv_enable: service enable
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error



ActiveDirectory
---------------

The ActiveDirectory resource represents the configuration settings for the
Active Directory service integration.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/activedirectory/

   Returns the active directory settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/activedirectory/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "ad_gcname": "",
                "ad_use_default_domain": true,
                "ad_workgroup": "",
                "ad_dcname": "",
                "ad_adminname": "",
                "ad_unix_extensions": false,
                "ad_timeout": 10,
                "ad_domainname": "",
                "id": 1,
                "ad_kpwdname": "",
                "ad_krbname": "",
                "ad_dns_timeout": 10,
                "ad_adminpw": "",
                "ad_verbose_logging": false,
                "ad_allow_trusted_doms": false,
                "ad_netbiosname": ""
        }

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/activedirectory/

   Update active directory.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/activedirectory/ HTTP/1.1
      Content-Type: application/json

        {
                "ad_netbiosname": "mynas",
                "ad_domainname": "mydomain",
                "ad_workgroup": "WORKGROUP",
                "ad_adminname": "admin",
                "ad_adminpw": "mypw"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "ad_gcname": "",
                "ad_use_default_domain": true,
                "ad_workgroup": "WORKGROUP",
                "ad_dcname": "",
                "ad_adminname": "admin",
                "ad_unix_extensions": false,
                "ad_timeout": 10,
                "svc": "activedirectory",
                "ad_domainname": "mydomain",
                "id": 1,
                "ad_kpwdname": "",
                "ad_krbname": "",
                "ad_dns_timeout": 10,
                "ad_adminpw": "mypw",
                "ad_verbose_logging": false,
                "ad_allow_trusted_doms": false,
                "ad_netbiosname": "mynas"
        }

   :json string ad_domainname: domain name
   :json string ad_netbiosname: system hostname
   :json string ad_workgroup: workgroup or domain name in old format
   :json string ad_adminname: domain Administrator account nam
   :json string ad_adminpw: domain Administrator account password
   :json string ad_dcname: hostname of the domain controller to use
   :json string ad_gcname: hostname of the global catalog server to use
   :json string ad_krbname: hostname of the kerberos server to use
   :json boolean ad_verbose_logging: verbose logging
   :json boolean ad_unix_extensions: unix extensions
   :json boolean ad_allow_trusted_doms: allow Trusted Domains
   :json boolean ad_use_default_domain: use the default domain for users and groups
   :json integer ad_dns_timeout: timeout for AD DNS queries
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


AFP
----

The AFP resource represents the configuration settings for Apple Filing
Protocol (AFP).

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/afp/

   Returns the AFP settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/afp/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "afp_srv_guest_user": "nobody",
                "afp_srv_guest": false,
                "id": 1,
                "afp_srv_connections_limit": 50,
                "afp_srv_name": "freenas"
        }

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/afp/

   Update AFP.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/afp/ HTTP/1.1
      Content-Type: application/json

        {
                "afp_srv_guest": true
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "afp_srv_guest_user": "nobody",
                "afp_srv_guest": true,
                "id": 1,
                "afp_srv_connections_limit": 50,
                "afp_srv_name": "freenas"
        }

   :json string afp_srv_name: name of the server
   :json string afp_srv_guest_user: guest account
   :json boolean afp_srv_guest: allow guest access
   :json integer afp_srv_connections_limit: maximum number of connections permitted
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


CIFS
----

The CIFS resource represents the configuration settings for Apple Filing
Protocol (CIFS).

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/cifs/

   Returns the CIFS settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/cifs/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "cifs_srv_dirmask": "",
                "cifs_srv_description": "FreeNAS Server",
                "cifs_srv_loglevel": "1",
                "cifs_srv_guest": "nobody",
                "cifs_srv_filemask": "",
                "cifs_srv_easupport": false,
                "cifs_srv_smb_options": "",
                "id": 1,
                "cifs_srv_aio_ws": 4096,
                "cifs_srv_unixext": true,
                "cifs_srv_homedir": null,
                "cifs_srv_dosattr": true,
                "cifs_srv_homedir_browseable_enable": false,
                "cifs_srv_homedir_enable": false,
                "cifs_srv_aio_enable": false,
                "cifs_srv_homedir_aux": "",
                "cifs_srv_aio_rs": 4096,
                "cifs_srv_localmaster": true,
                "cifs_srv_timeserver": true,
                "cifs_srv_workgroup": "WORKGROUP",
                "cifs_srv_doscharset": "CP437",
                "cifs_srv_hostlookup": true,
                "cifs_srv_netbiosname": "freenas",
                "cifs_srv_nullpw": false,
                "cifs_srv_zeroconf": true,
                "cifs_srv_authmodel": "user",
                "cifs_srv_unixcharset": "UTF-8"
        }

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/cifs/

   Update CIFS.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/cifs/ HTTP/1.1
      Content-Type: application/json

        {
                "cifs_srv_dosattr": false
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "cifs_srv_dirmask": "",
                "cifs_srv_description": "FreeNAS Server",
                "cifs_srv_loglevel": "1",
                "cifs_srv_guest": "nobody",
                "cifs_srv_filemask": "",
                "cifs_srv_easupport": false,
                "cifs_srv_smb_options": "",
                "id": 1,
                "cifs_srv_aio_ws": 4096,
                "cifs_srv_unixext": true,
                "cifs_srv_homedir": null,
                "cifs_srv_dosattr": false,
                "cifs_srv_homedir_browseable_enable": false,
                "cifs_srv_homedir_enable": false,
                "cifs_srv_aio_enable": false,
                "cifs_srv_homedir_aux": "",
                "cifs_srv_aio_rs": 4096,
                "cifs_srv_localmaster": true,
                "cifs_srv_timeserver": true,
                "cifs_srv_workgroup": "WORKGROUP",
                "cifs_srv_doscharset": "CP437",
                "cifs_srv_hostlookup": true,
                "cifs_srv_netbiosname": "freenas",
                "cifs_srv_nullpw": false,
                "cifs_srv_zeroconf": true,
                "cifs_srv_authmodel": "user",
                "cifs_srv_unixcharset": "UTF-8"
        }

   :json string cifs_srv_authmodel: user, share
   :json string cifs_srv_netbiosname: netbios name
   :json string cifs_srv_workgroup: workgroup
   :json string cifs_srv_description: server description
   :json string cifs_srv_doscharset: CP437, CP850, CP852, CP866, CP932, CP949, CP950, CP1026, CP1251, ASCII
   :json string cifs_srv_unixcharset: UTF-8, iso-8859-1, iso-8859-15, gb2312, EUC-JP, ASCII
   :json string cifs_srv_loglevel: 1, 2, 3, 10
   :json boolean cifs_srv_localmaster: local master
   :json boolean cifs_srv_timeserver: time server for domain
   :json string cifs_srv_guest: guest account
   :json string cifs_srv_filemask: file mask
   :json string cifs_srv_dirmask: directory mask
   :json boolean cifs_srv_easupport: ea support
   :json boolean cifs_srv_dosattr: support dos file attributes
   :json boolean cifs_srv_nullpw: allow empty password
   :json string cifs_srv_smb_options: auxiliary parameters added to [global] section
   :json boolean cifs_srv_homedir_enable: enable home directory
   :json boolean cifs_srv_homedir_browseable_enable: enable home directory browsing
   :json string cifs_srv_homedir: home directories path
   :json string cifs_srv_homedir_aux: homes auxiliary parameters
   :json boolean cifs_srv_unixext: unix extensions
   :json boolean cifs_srv_aio_enable: enable aio
   :json integer cifs_srv_aio_rs: minimum aio read size
   :json integer cifs_srv_aio_ws: minimum aio write size
   :json boolean cifs_srv_zeroconf: zeroconf share discovery
   :json boolean cifs_srv_hostlookup: hostname lookups
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


DynamicDNS
----------

The DynamicDNS resource represents the configuration settings for DynamicDNS.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/dynamicdns/

   Returns the DynamicDNS settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/dynamicdns/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "ddns_options": "",
                "ddns_password": "freenas",
                "id": 1,
                "ddns_username": "admin",
                "ddns_provider": "dyndns@dyndns.org",
                "ddns_fupdateperiod": "",
                "ddns_domain": "",
                "ddns_updateperiod": ""
        }

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/dynamicdns/

   Update DynamicDNS.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/dynamicdns/ HTTP/1.1
      Content-Type: application/json

        {
                "ddns_provider": "default@no-ip.com"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "ddns_options": "",
                "ddns_password": "freenas",
                "id": 1,
                "ddns_username": "admin",
                "ddns_provider": "default@no-ip.com",
                "ddns_fupdateperiod": "",
                "ddns_domain": "",
                "ddns_updateperiod": ""
        }

   :json string ddns_provider: dyndns@dyndns.org, default@freedns.afraid.org, default@zoneedit.com, default@no-ip.com, default@easydns.com, dyndns@3322.org, default@sitelutions.com, default@dnsomatic.com, ipv6tb@he.net, default@tzo.com, default@dynsip.org, default@dhis.org, default@majimoto.net, default@zerigo.com
   :json string ddns_domain: host name alias
   :json string ddns_username: username
   :json string ddns_password: password
   :json string ddns_updateperiod: time in seconds
   :json string ddns_fupdateperiod: forced update period
   :json string ddns_options: auxiliary parameters to global settings in inadyn-mt.conf
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


FTP
----------

The FTP resource represents the configuration settings for FTP service.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/ftp/

   Returns the FTP settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/ftp/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "ftp_anonuserbw": 0,
                "ftp_ident": false,
                "ftp_timeout": 600,
                "ftp_resume": false,
                "ftp_options": "",
                "ftp_masqaddress": "",
                "ftp_rootlogin": false,
                "id": 1,
                "ftp_passiveportsmax": 0,
                "ftp_ipconnections": 2,
                "ftp_defaultroot": true,
                "ftp_dirmask": "022",
                "ftp_passiveportsmin": 0,
                "ftp_onlylocal": false,
                "ftp_loginattempt": 1,
                "ftp_localuserbw": 0,
                "ftp_port": 21,
                "ftp_onlyanonymous": false,
                "ftp_reversedns": false,
                "ftp_anonuserdlbw": 0,
                "ftp_clients": 5,
                "ftp_tls": false,
                "ftp_fxp": false,
                "ftp_filemask": "077",
                "ftp_localuserdlbw": 0,
                "ftp_banner": "",
                "ftp_ssltls_certfile": "",
                "ftp_anonpath": null
        }

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/ftp/

   Update FTP.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/ftp/ HTTP/1.1
      Content-Type: application/json

        {
                "ftp_clients": 10
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "ftp_anonuserbw": 0,
                "ftp_ident": false,
                "ftp_timeout": 600,
                "ftp_resume": false,
                "ftp_options": "",
                "ftp_masqaddress": "",
                "ftp_rootlogin": false,
                "id": 1,
                "ftp_passiveportsmax": 0,
                "ftp_ipconnections": 2,
                "ftp_defaultroot": true,
                "ftp_dirmask": "022",
                "ftp_passiveportsmin": 0,
                "ftp_onlylocal": false,
                "ftp_loginattempt": 1,
                "ftp_localuserbw": 0,
                "ftp_port": 21,
                "ftp_onlyanonymous": false,
                "ftp_reversedns": false,
                "ftp_anonuserdlbw": 0,
                "ftp_clients": 5,
                "ftp_tls": false,
                "ftp_fxp": false,
                "ftp_filemask": "077",
                "ftp_localuserdlbw": 0,
                "ftp_banner": "",
                "ftp_ssltls_certfile": "",
                "ftp_anonpath": null
        }

   :json integer ftp_port: port to bind FTP server
   :json integer ftp_clients: maximum number of simultaneous clients
   :json integer ftp_ipconnections: maximum number of connections per IP address
   :json integer ftp_loginattempt: maximum number of allowed password attempts before disconnection
   :json integer ftp_timeout: maximum idle time in seconds
   :json boolean ftp_rootlogin: allow root login
   :json boolean ftp_onlyanonymous: allow anonymous login
   :json string ftp_anonpath: path for anonymous login
   :json boolean ftp_onlylocal: allow only local user login
   :json string ftp_banner: message which will be displayed to the user when they initially login
   :json string ftp_filemask: file creation mask
   :json string ftp_dirmask: directory creation mask
   :json boolean ftp_fxp: enable fxp
   :json boolean ftp_resume: allow transfer resumption
   :json boolean ftp_defaultroot: only allow access to user home unless member of wheel
   :json boolean ftp_ident: require IDENT authentication
   :json boolean ftp_reversedns: perform reverse dns lookup
   :json string ftp_masqaddress: causes the server to display the network information for the specified address to the client
   :json integer ftp_passiveportsmin: the minimum port to allocate for PASV style data connections
   :json integer ftp_passiveportsmax: the maximum port to allocate for PASV style data connections
   :json integer ftp_localuserbw: local user upload bandwidth in KB/s
   :json integer ftp_localuserdlbw: local user download bandwidth in KB/s
   :json integer ftp_anonuserbw: anonymous user upload bandwidth in KB/s
   :json integer ftp_anonuserdlbw: anonymous user download bandwidth in KB/s
   :json boolean ftp_tls: enable TLS
   :json string ftp_ssltls_certfile: certificate and private key
   :json string ftp_options: these parameters are added to proftpd.conf
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


LDAP
----------

The LDAP resource represents the configuration settings for LDAP service.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/ldap/

   Returns the LDAP settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/ldap/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
        }

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/ldap/

   Update LDAP.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/ldap/ HTTP/1.1
      Content-Type: application/json

        {
                "ldap_hostname": "ldaphostname",
                "ldap_basedn": "dc=test,dc=org"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "ldap_hostname": "ldaphostname",
                "ldap_tls_cacertfile": "",
                "ldap_groupsuffix": "",
                "ldap_rootbindpw": "",
                "ldap_options": "ldap_version 3\ntimelimit 30\nbind_timelimit 30\nbind_policy soft\npam_ldap_attribute uid",
                "ldap_pwencryption": "clear",
                "ldap_passwordsuffix": "",
                "ldap_anonbind": false,
                "ldap_ssl": "off",
                "ldap_machinesuffix": "",
                "ldap_basedn": "dc=test,dc=org",
                "ldap_usersuffix": "",
                "ldap_rootbasedn": "",
                "id": 1
        }

   :json string ldap_hostname: name or IP address of the LDAP server
   :json string ldap_basedn: default base Distinguished Name (DN) to use for searches
   :json boolean ldap_anonbind: allow anonymous binding
   :json string ldap_rootbasedn: distinguished name with which to bind to the directory server
   :json string ldap_rootbindpw: credentials with which to bind
   :json string ldap_pwencryption: clear, crypt, md5, nds, racf, ad, exop
   :json string ldap_usersuffix: suffix that is used for users
   :json string ldap_groupsuffix: suffix that is used for groups
   :json string ldap_passwordsuffix: suffix that is used for password
   :json string ldap_machinesuffix: suffix that is used for machines
   :json string ldap_ssl: off, on, start_tls
   :json string ldap_tls_cacertfile: contents of your self signed certificate
   :json string ldap_options: parameters are added to ldap.conf
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


NFS
----------

The NFS resource represents the configuration settings for NFS service.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/nfs/

   Returns the NFS settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/nfs/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "nfs_srv_bindip": "",
                "nfs_srv_mountd_port": null,
                "nfs_srv_allow_nonroot": false,
                "nfs_srv_servers": 4,
                "nfs_srv_rpcstatd_port": null,
                "nfs_srv_rpclockd_port": null,
                "id": 1
        }

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/nfs/

   Update NFS.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/nfs/ HTTP/1.1
      Content-Type: application/json

        {
                "nfs_srv_servers": 10
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "nfs_srv_bindip": "",
                "nfs_srv_mountd_port": null,
                "nfs_srv_allow_nonroot": false,
                "nfs_srv_servers": 10,
                "nfs_srv_rpcstatd_port": null,
                "nfs_srv_rpclockd_port": null,
                "id": 1
        }

   :json string nfs_srv_servers: how many servers to create
   :json boolean nfs_srv_allow_nonroot: allow non-root mount requests to be served.
   :json string nfs_srv_bindip: IP addresses (separated by commas) to bind to for TCP and UDP requests
   :json integer nfs_srv_mountd_port: force mountd to bind to the specified port
   :json integer nfs_srv_rpcstatd_port: forces the rpc.statd daemon to bind to the specified port
   :json integer nfs_srv_rpclockd_port: forces rpc.lockd the daemon to bind to the specified port
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


NIS
----------

The NIS resource represents the configuration settings for NIS service.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/nis/

   Returns the NIS settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/nis/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "nis_servers": "",
                "nis_secure_mode": false,
                "nis_manycast": false,
                "id": 1,
                "nis_domain": ""
        }

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/nis/

   Update NIS.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/nis/ HTTP/1.1
      Content-Type: application/json

        {
                "nis_domain": "nisdomain"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "nis_servers": "",
                "nis_secure_mode": false,
                "nis_manycast": false,
                "id": 1,
                "nis_domain": "nisdomain"
        }

   :json string nis_domain: nis domain name
   :json string nis_servers: comma delimited list of NIS servers
   :json boolean nis_secure_mode: cause ypbind to run in secure mode
   :json boolean nis_manycast: cause ypbind to use 'many-cast' instead of broadcast
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


NT4
----------

The NT4 resource represents the configuration settings for NT4 service.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/nt4/

   Returns the NT4 settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/nt4/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "nt4_adminname": "",
                "nt4_dcname": "",
                "nt4_workgroup": "",
                "nt4_netbiosname": "",
                "nt4_adminpw": "",
                "id": 1
        }

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/nt4/

   Update NT4.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/nt4/ HTTP/1.1
      Content-Type: application/json

        {
                "nt4_adminname": "admin",
                "nt4_dcname": "mydcname",
                "nt4_workgroup": "WORKGROUP",
                "nt4_netbiosname": "netbios",
                "nt4_adminpw": "mypw",
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "nt4_adminname": "admin",
                "nt4_dcname": "mydcname",
                "nt4_workgroup": "WORKGROUP",
                "nt4_netbiosname": "netbios",
                "nt4_adminpw": "mypw",
                "id": 1
        }

   :json string nt4_dcname: hostname of the domain controller to use
   :json string nt4_netbiosname: system hostname
   :json string nt4_workgroup: workgroup or domain name in old format
   :json string nt4_adminname: domain Administrator account name
   :json string nt4_adminpw: domain Administrator account password
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error
