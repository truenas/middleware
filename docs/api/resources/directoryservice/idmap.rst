=====
Idmap
=====


AD Idmap
--------

Active Directory Idmap.

List resource
+++++++++++++

.. http:get:: /api/v1.0/directoryservice/idmap/ad/

   Returns a list of all AD Idmaps.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/directoryservice/idmap/ad/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "id": 1,
                "idmap_ad_range_high": 90000000,
                "idmap_ad_range_low": 10000,
                "idmap_ad_schema_mode": "rfc2307",
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 20
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/directoryservice/idmap/ad/

   Creates a new idmap and returns the new object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/directoryservice/idmap/ad/ HTTP/1.1
      Content-Type: application/json

        {
                "idmap_ad_range_low": 10000,
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "idmap_ad_range_high": 90000000,
                "idmap_ad_range_low": 10000,
                "idmap_ad_schema_mode": "rfc2307",
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }

   :json string idmap_ad_schema_mode: defines the schema that idmap_ad should use when querying Active Directory (rfc2307, sfu, sfu20)
   :json integer idmap_ad_range_low: range low
   :json integer idmap_ad_range_high: range high
   :json integer idmap_ds_type: type of the directory service (ad, ldap, nis, cifs)
   :json integer idmap_ds_id: id of the directory service object
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/directoryservice/idmap/ad/(int:id)/

   Update idmap ad `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/directoryservice/idmap/ad/1/ HTTP/1.1
      Content-Type: application/json

        {
                "idmap_ad_range_high": 80000000
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "idmap_ad_range_high": 80000000,
                "idmap_ad_range_low": 10000,
                "idmap_ad_schema_mode": "rfc2307",
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }

   :json string idmap_ad_schema_mode: defines the schema that idmap_ad should use when querying Active Directory (rfc2307, sfu, sfu20)
   :json integer idmap_ad_range_low: range low
   :json integer idmap_ad_range_high: range high
   :json integer idmap_ds_type: type of the directory service (ad, ldap, nis, cifs)
   :json integer idmap_ds_id: id of the directory service object
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 200: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/directoryservice/idmap/ad/(int:id)/

   Delete idmap ad `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/directoryservice/idmap/ad/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


ADEX Idmap
----------

ADEX Idmap.

List resource
+++++++++++++

.. http:get:: /api/v1.0/directoryservice/idmap/adex/

   Returns a list of all ADEX Idmaps.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/directoryservice/idmap/adex/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "id": 1,
                "idmap_adex_range_high": 90000000,
                "idmap_adex_range_low": 10000,
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 20
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/directoryservice/idmap/adex/

   Creates a new idmap adex and returns the new object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/directoryservice/idmap/adex/ HTTP/1.1
      Content-Type: application/json

        {
                "idmap_adex_range_low": 10000,
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "idmap_adex_range_high": 90000000,
                "idmap_adex_range_low": 10000,
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }

   :json integer idmap_adex_range_low: range low
   :json integer idmap_adex_range_high: range high
   :json integer idmap_ds_type: type of the directory service (ad, ldap, nis, cifs)
   :json integer idmap_ds_id: id of the directory service object
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/directoryservice/idmap/adex/(int:id)/

   Update idmap adex `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/directoryservice/idmap/adex/1/ HTTP/1.1
      Content-Type: application/json

        {
                "idmap_adex_range_high": 80000000
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "idmap_adex_range_high": 80000000,
                "idmap_adex_range_low": 10000,
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }

   :json integer idmap_adex_range_low: range low
   :json integer idmap_adex_range_high: range high
   :json integer idmap_ds_type: type of the directory service (ad, ldap, nis, cifs)
   :json integer idmap_ds_id: id of the directory service object
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 200: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/directoryservice/idmap/adex/(int:id)/

   Delete idmap adex `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/directoryservice/idmap/adex/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


Hash Idmap
----------

Hash Idmap.

List resource
+++++++++++++

.. http:get:: /api/v1.0/directoryservice/idmap/hash/

   Returns a list of all Hash Idmaps.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/directoryservice/idmap/hash/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "id": 1,
                "idmap_hash_range_high": 100000000,
                "idmap_hash_range_low": 90000001,
                "idmap_hash_range_name_map": "",
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 20
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/directoryservice/idmap/hash/

   Creates a new idmap hash and returns the new object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/directoryservice/idmap/hash/ HTTP/1.1
      Content-Type: application/json

        {
                "idmap_hash_range_high": 100000000,
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "idmap_hash_range_high": 100000000,
                "idmap_hash_range_low": 90000001,
                "idmap_hash_range_name_map": "",
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }

   :json integer idmap_hash_range_low: range low
   :json integer idmap_hash_range_high: range high
   :json string idmap_hash_range_name_map: absolute path to the name mapping file
   :json integer idmap_ds_type: type of the directory service (ad, ldap, nis, cifs)
   :json integer idmap_ds_id: id of the directory service object
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/directoryservice/idmap/hash/(int:id)/

   Update idmap hash `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/directoryservice/idmap/hash/1/ HTTP/1.1
      Content-Type: application/json

        {
                "idmap_hash_range_high": 110000000
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "idmap_hash_range_high": 110000000,
                "idmap_hash_range_low": 90000001,
                "idmap_hash_range_name_map": "",
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }

   :json integer idmap_hash_range_low: range low
   :json integer idmap_hash_range_high: range high
   :json string idmap_hash_range_name_map: absolute path to the name mapping file
   :json integer idmap_ds_type: type of the directory service (ad, ldap, nis, cifs)
   :json integer idmap_ds_id: id of the directory service object
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 200: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/directoryservice/idmap/hash/(int:id)/

   Delete idmap hash `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/directoryservice/idmap/hash/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


LDAP Idmap
----------

LDAP Idmap.

List resource
+++++++++++++

.. http:get:: /api/v1.0/directoryservice/idmap/ldap/

   Returns a list of all LDAP Idmaps.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/directoryservice/idmap/ldap/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "id": 1,
                "idmap_ldap_range_low": 10000,
                "idmap_ldap_range_high": 90000000,
                "idmap_ldap_ldap_base_dn": "",
                "idmap_ldap_ldap_user_dn": "",
                "idmap_ldap_ldap_url": "",
                "idmap_ds_id": 1,
                "idmap_ds_type": 4
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 20
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/directoryservice/idmap/ldap/

   Creates a new idmap ldap and returns the new object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/directoryservice/idmap/ldap/ HTTP/1.1
      Content-Type: application/json

        {
                "idmap_ldap_ldap_url": "ldap://ldap.example.org",
                "idmap_ds_id": 1,
                "idmap_ds_type": 4
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "idmap_ldap_range_low": 10000,
                "idmap_ldap_range_high": 90000000,
                "idmap_ldap_ldap_base_dn": "",
                "idmap_ldap_ldap_user_dn": "",
                "idmap_ldap_ldap_url": "ldap://ldap.example.org",
                "idmap_ds_id": 1,
                "idmap_ds_type": 4
        }

   :json integer idmap_ldap_range_low: range low
   :json integer idmap_ldap_range_high: range high
   :json string idmap_ldap_ldap_base_dn: directory base suffix to use for SID/uid/gid
   :json string idmap_ldap_ldap_user_dn: user DN to be used for authentication
   :json string idmap_ldap_ldap_url: Specifies the LDAP server to use for SID/uid/gid map entries
   :json integer idmap_ds_type: type of the directory service (ad, ldap, nis, cifs)
   :json integer idmap_ds_id: id of the directory service object
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/directoryservice/idmap/ldap/(int:id)/

   Update idmap ldap `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/directoryservice/idmap/ldap/1/ HTTP/1.1
      Content-Type: application/json

        {
                "idmap_ldap_range_high": 110000000
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "idmap_ldap_range_high": 110000000,
                "idmap_ldap_range_low": 10000,
                "idmap_ldap_ldap_base_dn": "",
                "idmap_ldap_ldap_user_dn": "",
                "idmap_ldap_ldap_url": "ldap://ldap.example.org",
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }

   :json integer idmap_ldap_range_low: range low
   :json integer idmap_ldap_range_high: range high
   :json string idmap_ldap_ldap_base_dn: directory base suffix to use for SID/uid/gid
   :json string idmap_ldap_ldap_user_dn: user DN to be used for authentication
   :json string idmap_ldap_ldap_url: Specifies the LDAP server to use for SID/uid/gid map entries
   :json integer idmap_ds_type: type of the directory service (ad, ldap, nis, cifs)
   :json integer idmap_ds_id: id of the directory service object
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 200: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/directoryservice/idmap/ldap/(int:id)/

   Delete idmap ldap `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/directoryservice/idmap/ldap/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


NSS Idmap
---------

NSS Idmap.

List resource
+++++++++++++

.. http:get:: /api/v1.0/directoryservice/idmap/nss/

   Returns a list of all NSS Idmaps.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/directoryservice/idmap/nss/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "id": 1,
                "idmap_ad_range_high": 90000000,
                "idmap_ad_range_low": 10000,
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 20
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/directoryservice/idmap/nss/

   Creates a new idmap nss and returns the new object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/directoryservice/idmap/nss/ HTTP/1.1
      Content-Type: application/json

        {
                "idmap_ad_range_low": 10000,
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "idmap_ad_range_high": 90000000,
                "idmap_ad_range_low": 10000,
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }

   :json integer idmap_ad_range_low: range low
   :json integer idmap_ad_range_high: range high
   :json integer idmap_ds_type: type of the directory service (ad, ldap, nis, cifs)
   :json integer idmap_ds_id: id of the directory service object
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/directoryservice/idmap/nss/(int:id)/

   Update idmap nss `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/directoryservice/idmap/nss/1/ HTTP/1.1
      Content-Type: application/json

        {
                "idmap_ad_range_high": 80000000
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "idmap_ad_range_high": 80000000,
                "idmap_ad_range_low": 10000,
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }

   :json integer idmap_ad_range_low: range low
   :json integer idmap_ad_range_high: range high
   :json integer idmap_ds_type: type of the directory service (ad, ldap, nis, cifs)
   :json integer idmap_ds_id: id of the directory service object
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 200: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/directoryservice/idmap/nss/(int:id)/

   Delete idmap nss `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/directoryservice/idmap/nss/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


RFC2307 Idmap
-------------

RFC2307 Idmap.

List resource
+++++++++++++

.. http:get:: /api/v1.0/directoryservice/idmap/rfc2307/

   Returns a list of all RFC2307 Idmaps.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/directoryservice/idmap/rfc2307/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "id": 1,
                "idmap_rfc2307_range_low": 10000,
                "idmap_rfc2307_range_high": 90000000,
                "idmap_rfc2307_bind_path_user": "",
                "idmap_rfc2307_bind_path_group": "",
                "idmap_rfc2307_user_cn": "",
                "idmap_rfc2307_cn_realm": "",
                "idmap_rfc2307_ldap_server": "",
                "idmap_rfc2307_ldap_domain": "",
                "idmap_rfc2307_ldap_url": "",
                "idmap_rfc2307_ldap_user_dn": "",
                "idmap_rfc2307_ldap_realm": "",
                "idmap_ds_id": 1,
                "idmap_ds_type": 2
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 20
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/directoryservice/idmap/rfc2307/

   Creates a new idmap rfc2307 and returns the new object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/directoryservice/idmap/rfc2307/ HTTP/1.1
      Content-Type: application/json

        {
                "idmap_rfc2307_bind_path_group": "dc=user",
                "idmap_rfc2307_bind_path_user": "dc=group",
                "idmap_ds_id": 1
                "idmap_ds_type": 2
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "idmap_rfc2307_range_high": 90000000,
                "idmap_rfc2307_range_low": 10000,
                "idmap_rfc2307_bind_path_group": "dc=user",
                "idmap_rfc2307_bind_path_user": "dc=group",
                "idmap_rfc2307_cn_realm": false,
                "idmap_rfc2307_ldap_domain": "",
                "idmap_rfc2307_ldap_realm": "",
                "idmap_rfc2307_ldap_server": "ad",
                "idmap_rfc2307_ldap_url": "",
                "idmap_rfc2307_ldap_user_dn": "",
                "idmap_ds_id": 1,
                "idmap_ds_type": 2
        }

   :json integer idmap_rfc2307_range_low: range low
   :json integer idmap_rfc2307_range_high: range high
   :json string idmap_rfc2307_bind_path_user: bind path where user objects "can be found in the LDAP server
   :json string idmap_rfc2307_bind_path_group: bind path where group objects can be found in the LDAP server
   :json boolean idmap_rfc2307_user_cn: query cn attribute instead of uid attribute for the user name in LDAP
   :json string idmap_rfc2307_cn_realm: append @realm to cn for groups
   :json string idmap_rfc2307_ldap_server: type of LDAP server to use (ad)
   :json string idmap_rfc2307_ldap_domain: allows to specify the domain where to access the Active Directory server
   :json string idmap_rfc2307_ldap_url: ldap URL for accessing the LDAP server
   :json string idmap_rfc2307_ldap_user_dn:  user DN to be used for authentication
   :json string idmap_rfc2307_ldap_realm: realm to use in the user and group names
   :json integer idmap_ds_type: type of the directory service (ad, ldap, nis, cifs)
   :json integer idmap_ds_id: id of the directory service object
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/directoryservice/idmap/rfc2307/(int:id)/

   Update idmap rfc2307 `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/directoryservice/idmap/rfc2307/1/ HTTP/1.1
      Content-Type: application/json

        {
                "idmap_rfc2307_range_high": 110000000
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "idmap_rfc2307_range_high": 110000000,
                "idmap_rfc2307_range_low": 10000,
                "idmap_rfc2307_bind_path_group": "dc=user",
                "idmap_rfc2307_bind_path_user": "dc=group",
                "idmap_rfc2307_cn_realm": false,
                "idmap_rfc2307_ldap_domain": "",
                "idmap_rfc2307_ldap_realm": "",
                "idmap_rfc2307_ldap_server": "ad",
                "idmap_rfc2307_ldap_url": "",
                "idmap_rfc2307_ldap_user_dn": "",
                "idmap_ds_id": 1,
                "idmap_ds_type": 2
        }

   :json integer idmap_rfc2307_range_low: range low
   :json integer idmap_rfc2307_range_high: range high
   :json string idmap_rfc2307_bind_path_user: bind path where user objects "can be found in the LDAP server
   :json string idmap_rfc2307_bind_path_group: bind path where group objects can be found in the LDAP server
   :json boolean idmap_rfc2307_user_cn: query cn attribute instead of uid attribute for the user name in LDAP
   :json string idmap_rfc2307_cn_realm: append @realm to cn for groups
   :json string idmap_rfc2307_ldap_server: type of LDAP server to use (ad)
   :json string idmap_rfc2307_ldap_domain: allows to specify the domain where to access the Active Directory server
   :json string idmap_rfc2307_ldap_url: ldap URL for accessing the LDAP server
   :json string idmap_rfc2307_ldap_user_dn:  user DN to be used for authentication
   :json string idmap_rfc2307_ldap_realm: realm to use in the user and group names
   :json integer idmap_ds_type: type of the directory service (ad, ldap, nis, cifs)
   :json integer idmap_ds_id: id of the directory service object
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 200: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/directoryservice/idmap/rfc2307/(int:id)/

   Delete idmap rfc2307 `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/directoryservice/idmap/rfc2307/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


TDB Idmap
----------

TDB Idmap.

List resource
+++++++++++++

.. http:get:: /api/v1.0/directoryservice/idmap/tdb/

   Returns a list of all TDB Idmaps.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/directoryservice/idmap/tdb/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "id": 1,
                "idmap_tdb_range_low": 90000001,
                "idmap_tdb_range_high": 100000000,
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 20
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/directoryservice/idmap/tdb/

   Creates a new idmap tdb and returns the new object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/directoryservice/idmap/tdb/ HTTP/1.1
      Content-Type: application/json

        {
                "idmap_tdb_range_low": 10000,
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "idmap_tdb_range_low": 10000,
                "idmap_tdb_range_high": 100000000,
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }

   :json integer idmap_tdb_range_low: range low
   :json integer idmap_tdb_range_high: range high
   :json integer idmap_ds_type: type of the directory service (ad, ldap, nis, cifs)
   :json integer idmap_ds_id: id of the directory service object
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/directoryservice/idmap/tdb/(int:id)/

   Update idmap tdb `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/directoryservice/idmap/tdb/1/ HTTP/1.1
      Content-Type: application/json

        {
                "idmap_tdb_range_high": 110000000
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "idmap_tdb_range_high": 110000000,
                "idmap_tdb_range_low": 90000001,
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }

   :json integer idmap_tdb_range_low: range low
   :json integer idmap_tdb_range_high: range high
   :json integer idmap_ds_type: type of the directory service (ad, ldap, nis, cifs)
   :json integer idmap_ds_id: id of the directory service object
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 200: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/directoryservice/idmap/tdb/(int:id)/

   Delete idmap tdb `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/directoryservice/idmap/tdb/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


TDB2 Idmap
----------

TDB2 Idmap.

List resource
+++++++++++++

.. http:get:: /api/v1.0/directoryservice/idmap/tdb2/

   Returns a list of all TDB2 Idmaps.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/directoryservice/idmap/tdb2/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "id": 1,
                "idmap_tdb2_script": "/mnt/tank/tdbscript",
                "idmap_tdb2_range_low": 90000001,
                "idmap_tdb2_range_high": 100000000,
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 20
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/directoryservice/idmap/tdb2/

   Creates a new idmap tdb2 and returns the new object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/directoryservice/idmap/tdb2/ HTTP/1.1
      Content-Type: application/json

        {
                "idmap_tdb2_script": "/mnt/tank/tdbscript",
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "idmap_tdb2_script": "/mnt/tank/tdbscript",
                "idmap_tdb2_range_low": 90000001,
                "idmap_tdb2_range_high": 100000000,
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }

   :json integer idmap_tdb2_range_low: range low
   :json integer idmap_tdb2_range_high: range high
   :json integer idmap_ds_type: type of the directory service (ad, ldap, nis, cifs)
   :json integer idmap_ds_id: id of the directory service object
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/directoryservice/idmap/tdb2/(int:id)/

   Update idmap tdb2 `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/directoryservice/idmap/tdb2/1/ HTTP/1.1
      Content-Type: application/json

        {
                "idmap_tdb2_range_high": 110000000
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "idmap_tdb2_script": "/mnt/tank/tdbscript",
                "idmap_tdb2_range_high": 110000000,
                "idmap_tdb2_range_low": 90000001,
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }

   :json integer idmap_tdb2_range_low: range low
   :json integer idmap_tdb2_range_high: range high
   :json integer idmap_ds_type: type of the directory service (ad, ldap, nis, cifs)
   :json integer idmap_ds_id: id of the directory service object
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 200: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/directoryservice/idmap/tdb2/(int:id)/

   Delete idmap tdb2 `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/directoryservice/idmap/tdb2/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error
