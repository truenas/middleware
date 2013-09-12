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
