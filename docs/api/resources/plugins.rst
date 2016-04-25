=========
Plugins
=========

Resources related to Plugins.


Plugins
--------

The Plugins resource represents a plugin installed in the system.

List resource
+++++++++++++

.. http:get:: /api/v1.0/plugins/plugins/

   Returns a list of all plugins.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/plugins/plugins/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
          "id": 1,
          "plugin_api_version": "2",
          "plugin_arch": "amd64",
          "plugin_enabled": true,
          "plugin_ip": "-",
          "plugin_jail": "transmission_1",
          "plugin_name": "transmission",
          "plugin_path": "/usr/pbi/transmission-amd64",
          "plugin_pbiname": "transmission-2.82-amd64",
          "plugin_port": 12346,
          "plugin_version": "2.82"
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 20
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Start plugin
+++++++++++++++

.. http:post:: /api/v1.0/plugins/plugins/(int:id)/start/

   Starts a plugin service.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/plugins/plugins/1/start/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        Plugin started.

   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Stop plugin
+++++++++++++++

.. http:post:: /api/v1.0/plugins/plugins/(int:id)/stop/

   Stops a plugin service.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/plugins/plugins/1/stop/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        Plugin stopped.

   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/plugins/plugins/(int:id)/

   Delete plugin `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/plugins/plugins/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error
