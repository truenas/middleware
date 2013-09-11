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
