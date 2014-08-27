=====
Idmap
=====


AD Idmap
--------

Active Directory Idmap.

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
   :query limit: limit number. default is 30
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

   Update extent `id`.

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
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/directoryservice/idmap/ad/(int:id)/

   Delete extent `id`.

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
--------

Active Directory Ex. Idmap.

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
                "idmap_ad_range_high": 90000000,
                "idmap_ad_range_low": 10000,
                "idmap_ds_id": 1,
                "idmap_ds_type": 1
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/directoryservice/idmap/adex/

   Creates a new idmap and returns the new object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/directoryservice/idmap/adex/ HTTP/1.1
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

.. http:put:: /api/v1.0/directoryservice/idmap/adex/(int:id)/

   Update extent `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/directoryservice/idmap/adex/1/ HTTP/1.1
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
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/directoryservice/idmap/adex/(int:id)/

   Delete extent `id`.

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
