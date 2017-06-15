=================
Directory Service
=================

Resources related to directory service.


ActiveDirectory
---------------

The ActiveDirectory resource represents the configuration settings for the
Active Directory service integration.

List resource
+++++++++++++

.. http:get:: /api/v1.0/directoryservice/activedirectory/

   Returns the active directory settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/directoryservice/activedirectory/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "ad_enable": false,
                "ad_certfile": "",
                "ad_ssl": "off",
                "ad_gcname": "",
                "ad_keytab": "",
                "ad_use_keytab": false,
                "ad_use_default_domain": true,
                "ad_dcname": "",
                "ad_adminname": "",
                "ad_unix_extensions": false,
                "ad_timeout": 10,
                "ad_domainname": "",
                "id": 1,
                "ad_kpwdname": "",
                "ad_krbname": "",
                "ad_dns_timeout": 10,
                "ad_bindpw": "",
                "ad_verbose_logging": false,
                "ad_allow_trusted_doms": false,
                "ad_netbiosname": "NAS"
        }

   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/directoryservice/activedirectory/

   Update active directory.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/directoryservice/activedirectory/ HTTP/1.1
      Content-Type: application/json

        {
                "ad_netbiosname": "mynas",
                "ad_domainname": "mydomain",
                "ad_bindname": "admin",
                "ad_bindpw": "mypw"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "ad_enable": false,
                "ad_certfile": "",
                "ad_ssl": "off",
                "ad_gcname": "",
                "ad_keytab": "",
                "ad_use_keytab": false,
                "ad_use_default_domain": true,
                "ad_dcname": "",
                "ad_bindname": "admin",
                "ad_bindpw": "mypw",
                "ad_unix_extensions": false,
                "ad_timeout": 10,
                "ad_domainname": "mydomain",
                "id": 1,
                "ad_kpwdname": "",
                "ad_krbname": "",
                "ad_dns_timeout": 10,
                "ad_verbose_logging": false,
                "ad_allow_trusted_doms": false,
                "ad_netbiosname": "mynas"
        }

   :json string ad_enable: enable active directory
   :json string ad_certfile: ssl certificate
   :json string ad_ssl: encryption mode (on/off/start_tls)
   :json string ad_domainname: domain name
   :json string ad_netbiosname: system hostname
   :json string ad_bindpw: domain account password
   :json string ad_dcname: hostname of the domain controller to use
   :json string ad_gcname: hostname of the global catalog server to use
   :json string ad_keytab: kerberos keytab file
   :json boolean ad_use_keytab: use keytab
   :json string ad_krbname: hostname of the kerberos server to use
   :json boolean ad_verbose_logging: verbose logging
   :json boolean ad_unix_extensions: unix extensions
   :json boolean ad_allow_trusted_doms: allow Trusted Domains
   :json boolean ad_use_default_domain: use the default domain for users and groups
   :json integer ad_dns_timeout: timeout for AD DNS queries
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 200: no error


LDAP
----------

The LDAP resource represents the configuration settings for LDAP service.

List resource
+++++++++++++

.. http:get:: /api/v1.0/directoryservice/ldap/

   Returns the LDAP settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/directoryservice/ldap/ HTTP/1.1
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

.. http:put:: /api/v1.0/directoryservice/ldap/

   Update LDAP.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/directoryservice/ldap/ HTTP/1.1
      Content-Type: application/json

        {
                "ldap_hostname": "ldaphostname",
                "ldap_basedn": "dc=test,dc=org"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "ldap_hostname": "ldaphostname",
                "ldap_groupsuffix": "",
                "ldap_passwordsuffix": "",
                "ldap_anonbind": false,
                "ldap_ssl": "off",
                "ldap_machinesuffix": "",
                "ldap_basedn": "dc=test,dc=org",
                "ldap_usersuffix": "",
                "ldap_bindpw": "",
                "ldap_binddn": "",
                "ldap_enable": false,
                "ldap_certificate": "",
                "id": 1
        }

   :json string ldap_hostname: name or IP address of the LDAP server
   :json string ldap_basedn: default base Distinguished Name (DN) to use for searches
   :json boolean ldap_anonbind: allow anonymous binding
   :json string ldap_bindpw: credentials with which to bind
   :json string ldap_binddn: distinguished name with which to bind to the directory server
   :json string ldap_usersuffix: suffix that is used for users
   :json string ldap_groupsuffix: suffix that is used for groups
   :json string ldap_passwordsuffix: suffix that is used for password
   :json string ldap_machinesuffix: suffix that is used for machines
   :json string ldap_ssl: off, on, start_tls
   :json string ldap_certificate: id of your self signed certificate
   :json boolean ldap_enable: enable ldap directory service
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 200: no error


NIS
----------

The NIS resource represents the configuration settings for NIS service.

List resource
+++++++++++++

.. http:get:: /api/v1.0/directoryservice/nis/

   Returns the NIS settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/directoryservice/nis/ HTTP/1.1
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
                "nis_enable": false,
                "nis_domain": ""
        }

   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/directoryservice/nis/

   Update NIS.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/directoryservice/nis/ HTTP/1.1
      Content-Type: application/json

        {
                "nis_domain": "nisdomain"
        }

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
                "nis_enable": false,
                "nis_domain": "nisdomain"
        }

   :json string nis_domain: nis domain name
   :json string nis_servers: comma delimited list of NIS servers
   :json boolean nis_secure_mode: cause ypbind to run in secure mode
   :json boolean nis_manycast: cause ypbind to use "many-cast" instead of broadcast
   :json boolean nis_enable: enable nis
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 200: no error


NT4
----------

The NT4 resource represents the configuration settings for NT4 service.

List resource
+++++++++++++

.. http:get:: /api/v1.0/directoryservice/nt4/

   Returns the NT4 settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/directoryservice/nt4/ HTTP/1.1
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
                "nt4_netbiosname": "NAS",
                "nt4_adminpw": "",
                "nt4_enable": "false",
                "id": 1
        }

   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/directoryservice/nt4/

   Update NT4.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/directoryservice/nt4/ HTTP/1.1
      Content-Type: application/json

        {
                "nt4_adminname": "admin",
                "nt4_dcname": "mydcname",
                "nt4_workgroup": "WORKGROUP",
                "nt4_netbiosname": "netbios",
                "nt4_adminpw": "mypw"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "nt4_adminname": "admin",
                "nt4_dcname": "mydcname",
                "nt4_workgroup": "WORKGROUP",
                "nt4_netbiosname": "netbios",
                "nt4_adminpw": "mypw",
                "nt4_enable": "false",
                "id": 1
        }

   :json string nt4_dcname: hostname of the domain controller to use
   :json string nt4_netbiosname: system hostname
   :json string nt4_workgroup: workgroup or domain name in old format
   :json string nt4_adminname: domain Administrator account name
   :json string nt4_adminpw: domain Administrator account password
   :json string nt4_enable: enable NT4
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 200: no error


Idmap
-----

.. toctree::
   :glob:

   directoryservice/idmap
