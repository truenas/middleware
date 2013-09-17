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


iSCSI
-----

.. toctree::
   :glob:

   iscsi/*


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
   :json boolean nis_manycast: cause ypbind to use "many-cast" instead of broadcast
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


Rsyncd
----------

The Rsyncd resource represents the configuration settings for Rsyncd service.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/rsyncd/

   Returns the Rsyncd settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/rsyncd/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "rsyncd_auxiliary": "",
                "id": 1,
                "rsyncd_port": 873
        }

   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/rsyncd/

   Update Rsyncd.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/rsyncd/ HTTP/1.1
      Content-Type: application/json

        {
                "rsyncd_port": 874
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "rsyncd_auxiliary": "",
                "id": 1,
                "rsyncd_port": 874
        }

   :json integer rsyncd_port: alternate TCP port. Default is 873
   :json string rsyncd_auxiliary: parameters will be added to [global] settings in rsyncd.conf
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


RsyncMod
----------

The RsyncMod resource represents loader.conf(5).

List resource
+++++++++++++

.. http:get:: /api/v1.0/system/rsyncmod/

   Returns a list of all rsyncmods.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/rsyncmod/ HTTP/1.1
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

.. http:post:: /api/v1.0/system/rsyncmod/

   Creates a new rsyncmod and returns the new rsyncmod object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/rsyncmod/ HTTP/1.1
      Content-Type: application/json

        {
                "rsyncmod_name": "testmod",
                "rsyncmod_path": "/mnt/tank"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "rsyncmod_maxconn": 0,
                "rsyncmod_mode": "rw",
                "rsyncmod_hostsallow": "",
                "rsyncmod_path": "/mnt/tank",
                "id": 1,
                "rsyncmod_user": "nobody",
                "rsyncmod_auxiliary": "",
                "rsyncmod_group": "nobody",
                "rsyncmod_name": "testmod",
                "rsyncmod_comment": "",
                "rsyncmod_hostsdeny": ""
        }

   :json string rsyncmod_name: module name
   :json string rsyncmod_comment: comment
   :json string rsyncmod_path: path to share
   :json string rsyncmod_mode: ro, wo, rw
   :json integer rsyncmod_maxconn: maximum number of simultaneous connections
   :json string rsyncmod_user: user name that file transfers to and from that module should take place
   :json string rsyncmod_group: group name that file transfers to and from that module should take place
   :json string rsyncmod_hostsallow: comma, space, or tab delimited set of hosts which are permitted to access this module
   :json string rsyncmod_hostsdeny: comma, space, or tab delimited set of hosts which are NOT permitted to access this module
   :json string rsyncmod_auxiliary:  parameters will be added to the module configuration in rsyncd.conf
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/system/rsyncmod/(int:id)/

   Update rsyncmod `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/system/rsyncmod/1/ HTTP/1.1
      Content-Type: application/json

        {
                "rsyncmod_user": "root"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "rsyncmod_maxconn": 0,
                "rsyncmod_mode": "rw",
                "rsyncmod_hostsallow": "",
                "rsyncmod_path": "/mnt/tank",
                "id": 1,
                "rsyncmod_user": "root",
                "rsyncmod_auxiliary": "",
                "rsyncmod_group": "nobody",
                "rsyncmod_name": "testmod",
                "rsyncmod_comment": "",
                "rsyncmod_hostsdeny": ""
        }

   :json string rsyncmod_name: module name
   :json string rsyncmod_comment: comment
   :json string rsyncmod_path: path to share
   :json string rsyncmod_mode: ro, wo, rw
   :json integer rsyncmod_maxconn: maximum number of simultaneous connections
   :json string rsyncmod_user: user name that file transfers to and from that module should take place
   :json string rsyncmod_group: group name that file transfers to and from that module should take place
   :json string rsyncmod_hostsallow: comma, space, or tab delimited set of hosts which are permitted to access this module
   :json string rsyncmod_hostsdeny: comma, space, or tab delimited set of hosts which are NOT permitted to access this module
   :json string rsyncmod_auxiliary:  parameters will be added to the module configuration in rsyncd.conf
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/system/rsyncmod/(int:id)/

   Delete rsyncmod `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/system/rsyncmod/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


SMART
----------

The SMART resource represents the configuration settings for SMART service.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/smart/

   Returns the SMART settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/smart/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "smart_critical": 0,
                "smart_interval": 30,
                "smart_powermode": "never",
                "smart_informational": 0,
                "smart_email": "",
                "smart_difference": 0,
                "id": 1
        }

   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/smart/

   Update SMART.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/smart/ HTTP/1.1
      Content-Type: application/json

        {
                "smart_interval": 60,
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "smart_critical": 0,
                "smart_interval": 60,
                "smart_powermode": "never",
                "smart_informational": 0,
                "smart_email": "",
                "smart_difference": 0,
                "id": 1
        }

   :json integer smart_interval: interval between disk checks in minutes
   :json string smart_powermode: never, sleep, standby, idle
   :json integer smart_difference: report if the temperature had changed by at least N degrees Celsius since last report
   :json integer smart_informational: report as informational if the temperature had changed by at least N degrees Celsius since last report
   :json integer smart_critical: report as critical if the temperature had changed by at least N degrees Celsius since last report
   :json string smart_email: destination email address
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


SNMP
----------

The SNMP resource represents the configuration settings for SNMP service.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/snmp/

   Returns the SNMP settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/snmp/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "snmp_options": "",
                "snmp_community": "public",
                "snmp_traps": false,
                "snmp_contact": "",
                "snmp_location": "",
                "id": 1
        }

   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/snmp/

   Update SNMP.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/snmp/ HTTP/1.1
      Content-Type: application/json

        {
                "snmp_contact": "admin@freenas.org"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "snmp_options": "",
                "snmp_community": "public",
                "snmp_traps": false,
                "snmp_contact": "admin@freenas.org",
                "snmp_location": "",
                "id": 1
        }

   :json string snmp_location: location information, e.g. physical location of this system
   :json string snmp_contact: contact information
   :json string snmp_community: in most cases, "public" is used here
   :json string snmp_traps: send SNMP traps
   :json string snmp_options: parameters will be added to /etc/snmpd.config
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


SSH
----------

The SSH resource represents the configuration settings for SSH service.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/ssh/

   Returns the SSH settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/ssh/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "ssh_sftp_log_level": "",
                "ssh_host_rsa_key_pub": "c3NoLXJzYSBBQUFBQjNOemFDMXljMkVBQUFBREFRQUJBQUFCQVFEbGY0b2wyeVhrT0RCSTgz MGduMnpxRGJaSXJncDc2ZzBic0ozT2Z6ZUJaU0lZU3NReS9qY012bjNaOUQyd3ZMcnFFWlRS RXZCSUo3bmZwZzgvWXVuM2JmMEwvdC9LTTNqamM4b3ZLMEhHV056bGZFT0IzbkpGZ3VZdjZI SHNDSi9hTC9JYnhyLysxZ3RYZS8yVFJpN2FDTnhOd09ZZGFzakZDYmRteG5lQlhjRDhSS2Zu NlMrVDlneGFGZzdrbDhHYVVRNkEyMnNDTmREL2JoTnJUWkRLaFRGVm9WcDZRc0Nld0N3a1Bz ZUkrT0tTSzBRNmUvVTBhaHJiUlpuY2FqU0Y2OFFJY3dVclBwUVlhZ0t4S1ExQnZBdjIvK3Vz elJJdDl3c2JJWEZtWWNIcjAvRWhjYzkyY1o2UmtQYkpDYlljOU84dXVUMDEwTkZQUTYrbzE0 dFogcm9vdEBmcmVlbmFzLmxvY2FsCg==",
                "ssh_host_key": "U1NIIFBSSVZBVEUgS0VZIEZJTEUgRk9STUFUIDEuMQoAAAAAAAAAAAQABAD+qfDFkFTQJCy4 5OA8NLCSVObpJ4oHkm6IME0J2kQ+cj6cm46iv4ghK5y5Wdk/5uBH/WECQLiCJMo0LUaHSndF QXUtkmW5nYQtyqfJf50c5iAMEoSx3h5wycFbuV1s8RGHSkzOV5Xh+Ptr0GCtWq84WGTWXzlT LCKMQKcPrsL2uQARAQABAAAAEnJvb3RAZnJlZW5hcy5sb2NhbBLvEu8EAPZVKdngp7mCFGRw t9pk2Rti1s1W+rQiV5qSpiJOp86Dsb7I1arle+ciCYJcv8GJMQ9Rr6F/OzpgHdtkpCE/zacZ GDEe5pK3/TMeveT4e9/SmgV0jpVj4ndiBg2AQsbyebB1K55yDosrt8rRI2LAoW28TfxI7stB eBP1N4XOIAz1AgDFfgGkemepk2vSbLbwBym9poxclqbgggZs6Xv/yG1raKXgLjqL2h7/2kwb 1AbWbUqIC+zw4KHgpScLzq+q+XwgAgD+1NxVVBON1IFJhwQIGll4FjxEUKU0XTcZj63EFydU 7B5/h/wYl7rWxYtXxVZoEBgTnlYB53pKPkmqnUMI0IofAgD/1OIOQRBb9DMHTO1jUN1rHX+L w9l604adrDMPKbVKy8iX3qn2FuHrjmX1Gk3jx7SYtWSOn32n9wQrPlRcXJQnAAAAAA==",
                "ssh_host_ecdsa_key": "LS0tLS1CRUdJTiBFQyBQUklWQVRFIEtFWS0tLS0tCk1IY0NBUUVFSU53Z3NyK2hHbGVBMS9r WGJYVWxVU3k0RWtyQzBZT0dCT01mbEdkVFNxZWtvQW9HQ0NxR1NNNDkKQXdFSG9VUURRZ0FF eDNSM2lCejh5MjBKN21TNG95MHY2SE0xeHJnUFBzWnhIWHJqZU1DRjFQTy9Ha2orYjhkago0 T0JyN0J2QUs0QjYrNTFjcW1JZ3pxaU1BVmdRN2xnS3lnPT0KLS0tLS1FTkQgRUMgUFJJVkFU RSBLRVktLS0tLQo=",
                "ssh_options": "",
                "ssh_host_rsa_key": "LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVktLS0tLQpNSUlFcFFJQkFBS0NBUUVBNVgrS0pk c2w1RGd3U1BOOUlKOXM2ZzIyU0s0S2Urb05HN0Nkem44M2dXVWlHRXJFCk12NDNETDU5MmZR OXNMeTY2aEdVMFJMd1NDZTUzNllQUDJMcDkyMzlDLzdmeWpONDQzUEtMeXRCeGxqYzVYeEQK Z2Q1eVJZTG1MK2h4N0FpZjJpL3lHOGEvL3RZTFYzdjlrMFl1MmdqY1RjRG1IV3JJeFFtM1pz WjNnVjNBL0VTbgo1K2t2ay9ZTVdoWU81SmZCbWxFT2dOdHJBalhRLzI0VGEwMlF5b1V4VmFG YWVrTEFuc0FzSkQ3SGlQamlraXRFCk9udjFOR29hMjBXWjNHbzBoZXZFQ0hNRkt6NlVHR29D c1NrTlFid0w5di9yck0wU0xmY0xHeUZ4Wm1IQjY5UHgKSVhIUGRuR2VrWkQyeVFtMkhQVHZM cms5TmREUlQwT3ZxTmVMV1FJREFRQUJBb0lCQVFDL0pYZ3h5WktJd0FmdgphdVhvR3dFQy9J SzdqRUh0TFdiWGprWVJyTUhWUXgrZnJmNDJIcWhKTkF2c1VkSmo5djJUWVN0YTYvUTNsT2Jx CmtRd1lGbEdhcFFCalVsaWd1RGhTOGFrUG1tN0JQbGhWeHljTzd2Q3NWcmRVWmIwbEE1WG9p NUNTYy9xTHpVbEwKQjFtUHBaLzJOL1VOeWNHZjlNWGQzeGJqUWlCZEhONFNDRzliVllQNXFR Nk1PZWY4dE94a2J5aEp5MlVZSmNqcApqUy8wZTB4akpjU2ZZc09iZVluOFB3M0FnWFNJRlZ0 eDVEYzdsZmQwejgyb0poRU9jUnRhRFdXdE1Lb3Z0SWtmCjBVdUVTWHZwTnE1aDhkM2NoWS80 d0ZEbFJBMGdmN24vRzJYV3NYUkVnQkN0b0ptenFEM0ZScjdLUlQwNU9XV0QKRUVqcVE2RUJB b0dCQVA2b3J4WTByNHMvR3B1YVZXVWNqQ3Q2dmZYQjEyc3FnUEtRY0NnL0VUaHJuVTRyQjRv UgphQStTbElRaXBCVHNvRytSenNaWU1icHNmQlNjbHpBOENXbVZSbXJoalBLNDJNN0FLN3U0 MHdMMUF2K2ZtNXFBClFsbW80TnhXTzB6L3RtTW9PZWdCOFlRRnMvVnVwZmJIU0d1OTFkbnFs VTF1U1JLOU9NZTdneVRoQW9HQkFPYTAKNzMzNXJzQzIwTS9qUDZIOUV5TUIyMHBFYzAwb2hp WEJxUzIxM3JoK1ZrYUF6ek1iclJEVjh6VlBzemlmZjJhOQpvbS9URDVGVzVFektnaDEvUWN4 RmJvS1lHUmpGbC9RMjJDTm5VR0RvL1JkMmhJMUpxT0VpR3JEOTVXQTZXdHhHCjN2OGxxc01n c1FlbENmS0ZwNjFCb2lYTEhkUDVybllIZEw1b3diMTVBb0dBYTRlY3p0cVdXVXpmRmw4M3Vj Y3gKSk5iaVNWaDlkc0h1eXYzVWJob2JVbUNXZnNCS29iRXg2SWx6YnN3VnpzUVFCcXhoekh6 SEdybmVOdkhjSVVEbwpsSTIwdTBMY09rMTFOdkFNUjJzR3B0UUFYU0h2R1hFWkV6VHRKZnkv YzRieVk3SkRxVVRRejNkOUFxQ2pNYTM2ClZZeEdOWXNKV2pXOFkwNUZJSWw4R2VFQ2dZRUEx SG16VUN4U1c3NkRWZE1QV2R0QWNxOVZEWE01VmNpS3M5OUcKTm9rWGxJY1dZbHhqZDhoM2Zk ZnQ1QjJCREJjcE9MQlNGL2Nra1ZDYmRuWFRtK01GOEdISnc1RGRIRWx2QjBZegpqWGVyT1hX YkVxN2VxVms3cGd6STFGVWhtWnhrN2haL2JqRjhzYlU4RmJSVUV2NHhUWW56RWllZFV3clRP SFRwCmVpdjBzdEVDZ1lFQTdPcXhhWVVBQWlRM2hWTngyZnU1QzVkYXYrZk1Uekcxc1RlZk1x NGFxWGxRYTFGbUtxZksKOStONUF2OE80a2ZGMlZCR3YyVEZNQ2xzUHVYMHBCN2RocEFLZUd0 eEtXc0V6Sld3TDNUUFZVbHlkeklpc09NSApKbXVGQmg2cUlyTzZBM0c1ZVh4LzJ5RWxSdkxS V2lGY2pTWS96M3BpY0U0MzZQd05URlkwdXpjPQotLS0tLUVORCBSU0EgUFJJVkFURSBLRVkt LS0tLQo=",
                "ssh_privatekey": "",
                "ssh_compression": false,
                "ssh_host_key_pub": "MTAyNCA2NTUzNyAxNzg4MzEwMjMwOTgyODIzNTY2OTY1NDk4MjM2NDA4MjUzNjc0MjE1MzUy OTI3OTc2MjExMzYyMDUwMDk1NzY1NjExMTM0ODIxNzIxNzY5OTkyNjUyMzk3MTk3MTAzNTEy MzU2NTk1NzMxMTgzMTEwOTU1NjA5MDk1MTMwMDg1NDY3Mjg4NTEwNzk2MTI3OTQwNTA3MTEz MzQ5NDkxMTc3MTM2MjYzMTk5MDA4MjQ3NTgwMzkzMTA4MTkxMjg0ODA2ODAzNTQ2ODU3ODU4 MzYyNjExNTM2NTYxMTQyMDE3MDU0NDUzMjUzMTQ4MDc2MTU0MjI5ODg3MTQwMTY5MTc1NTAx NTk1MjU3Mzg3NzI4NDY2NDAyNzM0NTcwODgyNDI3OTcyODI1OTgyNDUyOTg3OTYyMTcgcm9v dEBmcmVlbmFzLmxvY2FsCg==",
                "ssh_passwordauth": true,
                "ssh_host_dsa_key_pub": "c3NoLWRzcyBBQUFBQjNOemFDMWtjM01BQUFDQkFLOG82amlVUzdxamltNERmSDJSSkIzeTVI ekNib21GRFRENjNscjk0ZnltMWlnTHlaQ0dFREN1U3Z1V2M5RW5wWFhWUDNaa3phZlBteTFF OFZ4OGhzUVpTTzV3blh0azJCZUFnNVNPelRYcDluZlBmNy94c0o3c1JYQUEzd0RuSjNUNjJB ZlNDRmF2TTVZS2pHQlgzRVZVYjJlaDVOQTRGUDl3Z1RhcWxjVmpBQUFBRlFDOUFlSE51cXY0 WU04UG1TVnNTQUNrU1NNdlBRQUFBSUFVeDBlUTE4M0g2Nlo3OG1RanFvT0VRNW5ROXUwWkhu WVNQZnRvN04veHRHQ0NDdG9ldVZSRnhIN1lrd0VJVzZmWm9DNTVqOTRVN2JnR1NaZkJEMzJo YklBbXRnVUFMU0lMVlZaVUJ2aWJjQW5vSEpqY3hlMnRsL09YT05zdi8yVkRLWWt1OTBRZDdD YkFsNlVVOStxQ3FjV3JVVlAzZ3pEOGdSWk9qcU1LZWdBQUFJQXhvbnlndVN6VW54WXh4VC9Y MzhIckIvOXRSeXhZNHBKalFsbVFLcmZveXhSL0ZtWWt2Wk9CL05UTjE5SEpJVExuMDBRZTF4 UkIyTUU1SVJGeXJmTGd2UGRJaUozczJONUQyRERmM3dBVmR0M3ZyQXJRR0t0RnRzL29nRStF dkthd25jQzAvallkaGJmSzNidlRVTFZ5dk11cEpKYzdabjhBNE9rNC9IWlVpUT09IHJvb3RA ZnJlZW5hcy5sb2NhbAo=",
                "ssh_tcpfwd": false,
                "ssh_sftp_log_facility": "",
                "ssh_tcpport": 22,
                "ssh_host_ecdsa_key_pub": "ZWNkc2Etc2hhMi1uaXN0cDI1NiBBQUFBRTJWalpITmhMWE5vWVRJdGJtbHpkSEF5TlRZQUFB QUlibWx6ZEhBeU5UWUFBQUJCQk1kMGQ0Z2MvTXR0Q2U1a3VLTXRMK2h6TmNhNER6N0djUjE2 NDNqQWhkVHp2eHBJL20vSFkrRGdhK3did0N1QWV2dWRYS3BpSU02b2pBRllFTzVZQ3NvPSBy b290QGZyZWVuYXMubG9jYWwK",
                "id": 1,
                "ssh_host_dsa_key": "LS0tLS1CRUdJTiBEU0EgUFJJVkFURSBLRVktLS0tLQpNSUlCdXdJQkFBS0JnUUN2S09vNGxF dTZvNHB1QTN4OWtTUWQ4dVI4d202SmhRMHcrdDVhL2VIOHB0WW9DOG1RCmhoQXdya3I3bG5Q Uko2VjExVDkyWk0ybno1c3RSUEZjZkliRUdVanVjSjE3Wk5nWGdJT1VqczAxNmZaM3ozKy8K OGJDZTdFVndBTjhBNXlkMCt0Z0gwZ2hXcnpPV0NveGdWOXhGVkc5bm9lVFFPQlQvY0lFMnFw WEZZd0lWQUwwQgo0YzI2cS9oZ3p3K1pKV3hJQUtSSkl5ODlBb0dBRk1kSGtOZk54K3VtZS9K a0k2cURoRU9aMFBidEdSNTJFajM3CmFPemY4YlJnZ2dyYUhybFVSY1IrMkpNQkNGdW4yYUF1 ZVkvZUZPMjRCa21Yd1E5OW9XeUFKcllGQUMwaUMxVlcKVkFiNG0zQUo2QnlZM01YdHJaZnps empiTC85bFF5bUpMdmRFSGV3bXdKZWxGUGZxZ3FuRnExRlQ5NE13L0lFVwpUbzZqQ25vQ2dZ QXhvbnlndVN6VW54WXh4VC9YMzhIckIvOXRSeXhZNHBKalFsbVFLcmZveXhSL0ZtWWt2Wk9C Ci9OVE4xOUhKSVRMbjAwUWUxeFJCMk1FNUlSRnlyZkxndlBkSWlKM3MyTjVEMkREZjN3QVZk dDN2ckFyUUdLdEYKdHMvb2dFK0V2S2F3bmNDMC9qWWRoYmZLM2J2VFVMVnl2TXVwSkpjN1pu OEE0T2s0L0haVWlRSVZBSmJuekFlVQpjSzZzdHBmMnFCUnlOZVMvOERWNAotLS0tLUVORCBE U0EgUFJJVkFURSBLRVktLS0tLQo=",
                "ssh_rootlogin": false
        }

   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/ssh/

   Update SSH.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/ssh/ HTTP/1.1
      Content-Type: application/json

        {
                "ssh_rootlogin": true
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "ssh_sftp_log_level": "",
                "ssh_host_rsa_key_pub": "c3NoLXJzYSBBQUFBQjNOemFDMXljMkVBQUFBREFRQUJBQUFCQVFEbGY0b2wyeVhrT0RCSTgz MGduMnpxRGJaSXJncDc2ZzBic0ozT2Z6ZUJaU0lZU3NReS9qY012bjNaOUQyd3ZMcnFFWlRS RXZCSUo3bmZwZzgvWXVuM2JmMEwvdC9LTTNqamM4b3ZLMEhHV056bGZFT0IzbkpGZ3VZdjZI SHNDSi9hTC9JYnhyLysxZ3RYZS8yVFJpN2FDTnhOd09ZZGFzakZDYmRteG5lQlhjRDhSS2Zu NlMrVDlneGFGZzdrbDhHYVVRNkEyMnNDTmREL2JoTnJUWkRLaFRGVm9WcDZRc0Nld0N3a1Bz ZUkrT0tTSzBRNmUvVTBhaHJiUlpuY2FqU0Y2OFFJY3dVclBwUVlhZ0t4S1ExQnZBdjIvK3Vz elJJdDl3c2JJWEZtWWNIcjAvRWhjYzkyY1o2UmtQYkpDYlljOU84dXVUMDEwTkZQUTYrbzE0 dFogcm9vdEBmcmVlbmFzLmxvY2FsCg==",
                "ssh_host_key": "U1NIIFBSSVZBVEUgS0VZIEZJTEUgRk9STUFUIDEuMQoAAAAAAAAAAAQABAD+qfDFkFTQJCy4 5OA8NLCSVObpJ4oHkm6IME0J2kQ+cj6cm46iv4ghK5y5Wdk/5uBH/WECQLiCJMo0LUaHSndF QXUtkmW5nYQtyqfJf50c5iAMEoSx3h5wycFbuV1s8RGHSkzOV5Xh+Ptr0GCtWq84WGTWXzlT LCKMQKcPrsL2uQARAQABAAAAEnJvb3RAZnJlZW5hcy5sb2NhbBLvEu8EAPZVKdngp7mCFGRw t9pk2Rti1s1W+rQiV5qSpiJOp86Dsb7I1arle+ciCYJcv8GJMQ9Rr6F/OzpgHdtkpCE/zacZ GDEe5pK3/TMeveT4e9/SmgV0jpVj4ndiBg2AQsbyebB1K55yDosrt8rRI2LAoW28TfxI7stB eBP1N4XOIAz1AgDFfgGkemepk2vSbLbwBym9poxclqbgggZs6Xv/yG1raKXgLjqL2h7/2kwb 1AbWbUqIC+zw4KHgpScLzq+q+XwgAgD+1NxVVBON1IFJhwQIGll4FjxEUKU0XTcZj63EFydU 7B5/h/wYl7rWxYtXxVZoEBgTnlYB53pKPkmqnUMI0IofAgD/1OIOQRBb9DMHTO1jUN1rHX+L w9l604adrDMPKbVKy8iX3qn2FuHrjmX1Gk3jx7SYtWSOn32n9wQrPlRcXJQnAAAAAA==",
                "ssh_host_ecdsa_key": "LS0tLS1CRUdJTiBFQyBQUklWQVRFIEtFWS0tLS0tCk1IY0NBUUVFSU53Z3NyK2hHbGVBMS9r WGJYVWxVU3k0RWtyQzBZT0dCT01mbEdkVFNxZWtvQW9HQ0NxR1NNNDkKQXdFSG9VUURRZ0FF eDNSM2lCejh5MjBKN21TNG95MHY2SE0xeHJnUFBzWnhIWHJqZU1DRjFQTy9Ha2orYjhkago0 T0JyN0J2QUs0QjYrNTFjcW1JZ3pxaU1BVmdRN2xnS3lnPT0KLS0tLS1FTkQgRUMgUFJJVkFU RSBLRVktLS0tLQo=",
                "ssh_options": "",
                "ssh_host_rsa_key": "LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVktLS0tLQpNSUlFcFFJQkFBS0NBUUVBNVgrS0pk c2w1RGd3U1BOOUlKOXM2ZzIyU0s0S2Urb05HN0Nkem44M2dXVWlHRXJFCk12NDNETDU5MmZR OXNMeTY2aEdVMFJMd1NDZTUzNllQUDJMcDkyMzlDLzdmeWpONDQzUEtMeXRCeGxqYzVYeEQK Z2Q1eVJZTG1MK2h4N0FpZjJpL3lHOGEvL3RZTFYzdjlrMFl1MmdqY1RjRG1IV3JJeFFtM1pz WjNnVjNBL0VTbgo1K2t2ay9ZTVdoWU81SmZCbWxFT2dOdHJBalhRLzI0VGEwMlF5b1V4VmFG YWVrTEFuc0FzSkQ3SGlQamlraXRFCk9udjFOR29hMjBXWjNHbzBoZXZFQ0hNRkt6NlVHR29D c1NrTlFid0w5di9yck0wU0xmY0xHeUZ4Wm1IQjY5UHgKSVhIUGRuR2VrWkQyeVFtMkhQVHZM cms5TmREUlQwT3ZxTmVMV1FJREFRQUJBb0lCQVFDL0pYZ3h5WktJd0FmdgphdVhvR3dFQy9J SzdqRUh0TFdiWGprWVJyTUhWUXgrZnJmNDJIcWhKTkF2c1VkSmo5djJUWVN0YTYvUTNsT2Jx CmtRd1lGbEdhcFFCalVsaWd1RGhTOGFrUG1tN0JQbGhWeHljTzd2Q3NWcmRVWmIwbEE1WG9p NUNTYy9xTHpVbEwKQjFtUHBaLzJOL1VOeWNHZjlNWGQzeGJqUWlCZEhONFNDRzliVllQNXFR Nk1PZWY4dE94a2J5aEp5MlVZSmNqcApqUy8wZTB4akpjU2ZZc09iZVluOFB3M0FnWFNJRlZ0 eDVEYzdsZmQwejgyb0poRU9jUnRhRFdXdE1Lb3Z0SWtmCjBVdUVTWHZwTnE1aDhkM2NoWS80 d0ZEbFJBMGdmN24vRzJYV3NYUkVnQkN0b0ptenFEM0ZScjdLUlQwNU9XV0QKRUVqcVE2RUJB b0dCQVA2b3J4WTByNHMvR3B1YVZXVWNqQ3Q2dmZYQjEyc3FnUEtRY0NnL0VUaHJuVTRyQjRv UgphQStTbElRaXBCVHNvRytSenNaWU1icHNmQlNjbHpBOENXbVZSbXJoalBLNDJNN0FLN3U0 MHdMMUF2K2ZtNXFBClFsbW80TnhXTzB6L3RtTW9PZWdCOFlRRnMvVnVwZmJIU0d1OTFkbnFs VTF1U1JLOU9NZTdneVRoQW9HQkFPYTAKNzMzNXJzQzIwTS9qUDZIOUV5TUIyMHBFYzAwb2hp WEJxUzIxM3JoK1ZrYUF6ek1iclJEVjh6VlBzemlmZjJhOQpvbS9URDVGVzVFektnaDEvUWN4 RmJvS1lHUmpGbC9RMjJDTm5VR0RvL1JkMmhJMUpxT0VpR3JEOTVXQTZXdHhHCjN2OGxxc01n c1FlbENmS0ZwNjFCb2lYTEhkUDVybllIZEw1b3diMTVBb0dBYTRlY3p0cVdXVXpmRmw4M3Vj Y3gKSk5iaVNWaDlkc0h1eXYzVWJob2JVbUNXZnNCS29iRXg2SWx6YnN3VnpzUVFCcXhoekh6 SEdybmVOdkhjSVVEbwpsSTIwdTBMY09rMTFOdkFNUjJzR3B0UUFYU0h2R1hFWkV6VHRKZnkv YzRieVk3SkRxVVRRejNkOUFxQ2pNYTM2ClZZeEdOWXNKV2pXOFkwNUZJSWw4R2VFQ2dZRUEx SG16VUN4U1c3NkRWZE1QV2R0QWNxOVZEWE01VmNpS3M5OUcKTm9rWGxJY1dZbHhqZDhoM2Zk ZnQ1QjJCREJjcE9MQlNGL2Nra1ZDYmRuWFRtK01GOEdISnc1RGRIRWx2QjBZegpqWGVyT1hX YkVxN2VxVms3cGd6STFGVWhtWnhrN2haL2JqRjhzYlU4RmJSVUV2NHhUWW56RWllZFV3clRP SFRwCmVpdjBzdEVDZ1lFQTdPcXhhWVVBQWlRM2hWTngyZnU1QzVkYXYrZk1Uekcxc1RlZk1x NGFxWGxRYTFGbUtxZksKOStONUF2OE80a2ZGMlZCR3YyVEZNQ2xzUHVYMHBCN2RocEFLZUd0 eEtXc0V6Sld3TDNUUFZVbHlkeklpc09NSApKbXVGQmg2cUlyTzZBM0c1ZVh4LzJ5RWxSdkxS V2lGY2pTWS96M3BpY0U0MzZQd05URlkwdXpjPQotLS0tLUVORCBSU0EgUFJJVkFURSBLRVkt LS0tLQo=",
                "ssh_privatekey": "",
                "ssh_compression": false,
                "ssh_host_key_pub": "MTAyNCA2NTUzNyAxNzg4MzEwMjMwOTgyODIzNTY2OTY1NDk4MjM2NDA4MjUzNjc0MjE1MzUy OTI3OTc2MjExMzYyMDUwMDk1NzY1NjExMTM0ODIxNzIxNzY5OTkyNjUyMzk3MTk3MTAzNTEy MzU2NTk1NzMxMTgzMTEwOTU1NjA5MDk1MTMwMDg1NDY3Mjg4NTEwNzk2MTI3OTQwNTA3MTEz MzQ5NDkxMTc3MTM2MjYzMTk5MDA4MjQ3NTgwMzkzMTA4MTkxMjg0ODA2ODAzNTQ2ODU3ODU4 MzYyNjExNTM2NTYxMTQyMDE3MDU0NDUzMjUzMTQ4MDc2MTU0MjI5ODg3MTQwMTY5MTc1NTAx NTk1MjU3Mzg3NzI4NDY2NDAyNzM0NTcwODgyNDI3OTcyODI1OTgyNDUyOTg3OTYyMTcgcm9v dEBmcmVlbmFzLmxvY2FsCg==",
                "ssh_passwordauth": true,
                "ssh_host_dsa_key_pub": "c3NoLWRzcyBBQUFBQjNOemFDMWtjM01BQUFDQkFLOG82amlVUzdxamltNERmSDJSSkIzeTVI ekNib21GRFRENjNscjk0ZnltMWlnTHlaQ0dFREN1U3Z1V2M5RW5wWFhWUDNaa3phZlBteTFF OFZ4OGhzUVpTTzV3blh0azJCZUFnNVNPelRYcDluZlBmNy94c0o3c1JYQUEzd0RuSjNUNjJB ZlNDRmF2TTVZS2pHQlgzRVZVYjJlaDVOQTRGUDl3Z1RhcWxjVmpBQUFBRlFDOUFlSE51cXY0 WU04UG1TVnNTQUNrU1NNdlBRQUFBSUFVeDBlUTE4M0g2Nlo3OG1RanFvT0VRNW5ROXUwWkhu WVNQZnRvN04veHRHQ0NDdG9ldVZSRnhIN1lrd0VJVzZmWm9DNTVqOTRVN2JnR1NaZkJEMzJo YklBbXRnVUFMU0lMVlZaVUJ2aWJjQW5vSEpqY3hlMnRsL09YT05zdi8yVkRLWWt1OTBRZDdD YkFsNlVVOStxQ3FjV3JVVlAzZ3pEOGdSWk9qcU1LZWdBQUFJQXhvbnlndVN6VW54WXh4VC9Y MzhIckIvOXRSeXhZNHBKalFsbVFLcmZveXhSL0ZtWWt2Wk9CL05UTjE5SEpJVExuMDBRZTF4 UkIyTUU1SVJGeXJmTGd2UGRJaUozczJONUQyRERmM3dBVmR0M3ZyQXJRR0t0RnRzL29nRStF dkthd25jQzAvallkaGJmSzNidlRVTFZ5dk11cEpKYzdabjhBNE9rNC9IWlVpUT09IHJvb3RA ZnJlZW5hcy5sb2NhbAo=",
                "ssh_tcpfwd": false,
                "ssh_sftp_log_facility": "",
                "ssh_tcpport": 22,
                "ssh_host_ecdsa_key_pub": "ZWNkc2Etc2hhMi1uaXN0cDI1NiBBQUFBRTJWalpITmhMWE5vWVRJdGJtbHpkSEF5TlRZQUFB QUlibWx6ZEhBeU5UWUFBQUJCQk1kMGQ0Z2MvTXR0Q2U1a3VLTXRMK2h6TmNhNER6N0djUjE2 NDNqQWhkVHp2eHBJL20vSFkrRGdhK3did0N1QWV2dWRYS3BpSU02b2pBRllFTzVZQ3NvPSBy b290QGZyZWVuYXMubG9jYWwK",
                "id": 1,
                "ssh_host_dsa_key": "LS0tLS1CRUdJTiBEU0EgUFJJVkFURSBLRVktLS0tLQpNSUlCdXdJQkFBS0JnUUN2S09vNGxF dTZvNHB1QTN4OWtTUWQ4dVI4d202SmhRMHcrdDVhL2VIOHB0WW9DOG1RCmhoQXdya3I3bG5Q Uko2VjExVDkyWk0ybno1c3RSUEZjZkliRUdVanVjSjE3Wk5nWGdJT1VqczAxNmZaM3ozKy8K OGJDZTdFVndBTjhBNXlkMCt0Z0gwZ2hXcnpPV0NveGdWOXhGVkc5bm9lVFFPQlQvY0lFMnFw WEZZd0lWQUwwQgo0YzI2cS9oZ3p3K1pKV3hJQUtSSkl5ODlBb0dBRk1kSGtOZk54K3VtZS9K a0k2cURoRU9aMFBidEdSNTJFajM3CmFPemY4YlJnZ2dyYUhybFVSY1IrMkpNQkNGdW4yYUF1 ZVkvZUZPMjRCa21Yd1E5OW9XeUFKcllGQUMwaUMxVlcKVkFiNG0zQUo2QnlZM01YdHJaZnps empiTC85bFF5bUpMdmRFSGV3bXdKZWxGUGZxZ3FuRnExRlQ5NE13L0lFVwpUbzZqQ25vQ2dZ QXhvbnlndVN6VW54WXh4VC9YMzhIckIvOXRSeXhZNHBKalFsbVFLcmZveXhSL0ZtWWt2Wk9C Ci9OVE4xOUhKSVRMbjAwUWUxeFJCMk1FNUlSRnlyZkxndlBkSWlKM3MyTjVEMkREZjN3QVZk dDN2ckFyUUdLdEYKdHMvb2dFK0V2S2F3bmNDMC9qWWRoYmZLM2J2VFVMVnl2TXVwSkpjN1pu OEE0T2s0L0haVWlRSVZBSmJuekFlVQpjSzZzdHBmMnFCUnlOZVMvOERWNAotLS0tLUVORCBE U0EgUFJJVkFURSBLRVktLS0tLQo=",
                "ssh_rootlogin": true
        }

   :json string ssh_tcpport: alternate TCP port. Default is 22
   :json string ssh_rootlogin: Disabled: Root can only login via public key authentication; Enabled: Root login permitted with password
   :json string ssh_passwordauth: Allow Password Authentication
   :json string ssh_tcpfwd: Allow TCP Port Forwarding
   :json string ssh_compression: Compress Connections
   :json string ssh_privatekey: RSA PRIVATE KEY in PEM format
   :json string ssh_sftp_log_level: QUIET, FATAL, ERROR, INFO, VERBOSE, DEBUG, DEBUG2, DEBUG3
   :json string ssh_sftp_log_facility: DAEMON, USER, AUTH, LOCAL0, LOCAL1, LOCAL2, LOCAL3, LOCAL4, LOCAL5, LOCAL6, LOCAL7
   :json string ssh_options: extra options to /etc/ssh/sshd_config
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


TFTP
----------

The TFTP resource represents the configuration settings for TFTP service.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/tftp/

   Returns the TFTP settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/tftp/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "tftp_umask": "022",
                "tftp_username": "nobody",
                "tftp_directory": "/tftproot",
                "tftp_port": 69,
                "tftp_options": "",
                "id": 1,
                "tftp_newfiles": false
        }

   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/tftp/

   Update TFTP.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/tftp/ HTTP/1.1
      Content-Type: application/json

        {
                "tftp_contact": "admin@freenas.org"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "tftp_umask": "022",
                "tftp_username": "nobody",
                "tftp_directory": "/tftproot",
                "tftp_port": 69,
                "tftp_options": "",
                "id": 1,
                "tftp_newfiles": false
        }

   :json string tftp_directory: the directory containing the files you want to publish
   :json boolean tftp_newfiles: Allow New Files
   :json integer tftp_port: port to listen to
   :json string tftp_username: username which the service will run as
   :json string tftp_umask: umask for newly created files
   :json string tftp_options: extra command line options
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


UPS
----------

The UPS resource represents the configuration settings for UPS service.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/ups/

   Returns the UPS settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/ups/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "ups_monpwd": "fixmepass",
                "ups_port": "/dev/ugen0.1",
                "ups_options": "",
                "ups_remotehost": "",
                "ups_rmonitor": false,
                "ups_toemail": "",
                "ups_shutdowntimer": 30,
                "ups_extrausers": "",
                "ups_driver": "",
                "ups_mode": "master",
                "ups_identifier": "ups",
                "ups_emailnotify": false,
                "ups_remoteport": 3493,
                "ups_subject": "UPS report generated by %h",
                "ups_shutdown": "batt",
                "id": 1,
                "ups_description": "",
                "ups_monuser": "upsmon"
        }

   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/ups/

   Update UPS.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/ups/ HTTP/1.1
      Content-Type: application/json

        {
                "ups_rmonitor": true
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "ups_monpwd": "fixmepass",
                "ups_port": "/dev/ugen0.1",
                "ups_options": "",
                "ups_remotehost": "",
                "ups_rmonitor": true,
                "ups_toemail": "",
                "ups_shutdowntimer": 30,
                "ups_extrausers": "",
                "ups_driver": "",
                "ups_mode": "master",
                "ups_identifier": "ups",
                "ups_emailnotify": false,
                "ups_remoteport": 3493,
                "ups_subject": "UPS report generated by %h",
                "ups_shutdown": "batt",
                "id": 1,
                "ups_description": "",
                "ups_monuser": "upsmon"
        }

   :json string ups_mode: master, slave
   :json string ups_identifier: name is used to uniquely identify your UPS
   :json string ups_remotehost: Remote Host
   :json integer ups_remoteport: Remote Port
   :json string ups_driver: see /usr/local/etc/nut/driver.list
   :json string ups_port: path to serial or USB port where your UPS is connected
   :json string ups_options: auxiliary parameters (ups.conf)
   :json string ups_description: Description
   :json string ups_shutdown: lowbatt, batt
   :json integer ups_shutdowntimer: time in seconds until shutdown is initiated
   :json string ups_monuser: Monitor User
   :json string ups_monpwd: Monitor Password
   :json string ups_extrausers: Extra users (upsd.users)
   :json boolean ups_rmonitor: Remote Monitor
   :json boolean ups_emailnotify: Send Email Status Updates
   :json string ups_toemail: destination email address
   :json string ups_subject: subject of the email. You can use the following: %d - Date; %h - Hostname
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error
