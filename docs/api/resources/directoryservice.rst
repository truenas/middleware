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
                "ad_certificate": null,
                "ad_allow_dns_updates": true,
                "ad_allow_trusted_doms": false,
                "ad_bindname": "",
                "ad_bindpw": "",
                "ad_dcname": null,
                "ad_disable_freenas_cache": false,
                "ad_dns_timeout": 60,
                "ad_domainname": "vovomain",
                "ad_enable_monitor": false,
                "ad_gcname": null,
                "ad_groupdn": "",
                "ad_idmap_backend": "rid",
                "ad_kerberos_principal": null,
                "ad_kerberos_realm": null,
                "ad_ldap_sasl_wrapping": "plain",
                "ad_monitor_frequency": 60,
                "ad_nss_info": null,
                "ad_netbiosalias": "",
                "ad_netbiosname_a": "NAS",
                "ad_recover_retry": 10,
                "ad_site": "",
                "ad_ssl": "off",
                "ad_timeout": 60,
                "ad_unix_extensions": false,
                "ad_use_default_domain": false,
                "ad_userdn": "",
                "ad_verbose_logging": false,
                "id": 1
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
                "ad_netbiosname_a": "mynas",
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
                "ad_certficate": "",
                "ad_ssl": "off",
                "ad_gcname": "",
                "ad_use_default_domain": true,
                "ad_dcname": "",
                "ad_bindname": "admin",
                "ad_bindpw": "mypw",
                "ad_unix_extensions": false,
                "ad_timeout": 10,
                "ad_kerberos_principal": "",
                "ad_kerberos_realm": "",
                "ad_domainname": "mydomain",
                "ad_dns_timeout": 10,
                "ad_verbose_logging": false,
                "ad_allow_trusted_doms": false,
                "ad_netbiosname_a": "mynas",
                "id": 1
        }

   :json boolean ad_allow_dns_updates: allow DNS updates
   :json boolean ad_allow_trusted_doms: allow Trusted Domains
   :json string ad_bindname: domain account name
   :json string ad_bindpw: domain account password
   :json string ad_certificate: SSL certificate
   :json string ad_dcname: hostname of the domain controller to use
   :json boolean ad_disable_freenas_cache: disable AD user/group cache
   :json integer ad_dns_timeout: timeout for AD DNS queries
   :json string ad_domainname: AD domain name
   :json boolean ad_enable_monitor: enable monitoring
   :json string ad_enable: enable active directory
   :json string ad_gcname: hostname of the global catalog server to use
   :json string ad_groupdn: DN of the group container in AD
   :json string ad_idmap_backend: IDmap backend
   :json string ad_kerberos_principal: Kerberos principal
   :json string ad_kerberos_realm: Kerberos realm
   :json string ad_ldap_sasl_wrapping: LDAP SASL wrapping mode (plain/signed/sealed)
   :json integer ad_monitor_frequency: AD check connectivity frequency in seconds
   :json string ad_netbiosalias: NetBIOS alias
   :json string ad_netbiosname_a: NetBIOS system hostname
   :json string ad_nss_info: winbind NSS info
   :json integer ad_recover_retry: how many recovery attempts
   :json string ad_site: site name
   :json string ad_ssl: encryption mode (on/off/start_tls)
   :json integer ad_timeout: timeout for AD operations
   :json boolean ad_unix_extensions: unix extensions
   :json boolean ad_use_default_domain: use default domain for users and groups
   :json string ad_userdn: DN of the user container in AD
   :json boolean ad_verbose_logging: verbose logging
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
            "id": 1,
            "ldap_anonbind": false,
            "ldap_auxiliary_parameters": "",
            "ldap_basedn": "",
            "ldap_binddn": "",
            "ldap_bindpw": "",
            "ldap_certificate": null,
            "ldap_dns_timeout": 10,
            "ldap_enable": false,
            "ldap_groupsuffix": "",
            "ldap_has_samba_schema": false,
            "ldap_hostname": "",
            "ldap_idmap_backend": "ldap",
            "ldap_kerberos_principal": null,
            "ldap_kerberos_realm": null,
            "ldap_machinesuffix": "",
            "ldap_netbiosalias": "",
            "ldap_netbiosname_a": "NAS",
            "ldap_passwordsuffix": "",
            "ldap_schema": "rfc2307",
            "ldap_ssl": "off",
            "ldap_sudosuffix": "",
            "ldap_timeout": 10,
            "ldap_usersuffix": ""
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

   :json boolean ldap_anonbind: allow anonymous binding
   :json string ldap_auxiliary_parameters: parameters to add to sssd.conf
   :json string ldap_basedn: default base Distinguished Name (DN) to use for searches
   :json string ldap_binddn: Distinguished Name with which to bind to the directory server
   :json string ldap_bindpw: credentials with which to bind
   :json string ldap_certificate: id of your certificate
   :json integer ldap_dns_timeout: timeout for LDAP DNS queries
   :json boolean ldap_enable: enable LDAP directory service
   :json string ldap_groupsuffix: suffix that is used for groups
   :json boolean ldap_has_samba_schema: does LDAP have Samba schema
   :json string ldap_hostname: name or IP address of the LDAP server
   :json string ldap_idmap_backend: IDmap backend
   :json string ldap_kerberos_principal: Kerberos principal
   :json string ldap_kerberos_realm: Kerberos realm
   :json string ldap_machinesuffix: suffix that is used for machines
   :json string ldap_netbiosalias: NetBIOS alias
   :json string ldap_netbiosname_a: NetBIOS hostname
   :json string ldap_passwordsuffix: suffix that is used for passwords
   :json string ldap_schema: LDAP schema type
   :json string ldap_ssl: encryption mode (off/on/start_tls)
   :json string ldap_sudosuffix: suffix that is used for SUDO users
   :json integer ldap_timeout: timeout for LDAP commands
   :json string ldap_usersuffix: suffix that is used for users
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


Idmap
-----

.. toctree::
   :glob:

   directoryservice/idmap
