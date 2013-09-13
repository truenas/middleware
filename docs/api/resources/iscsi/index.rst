===============
iSCSI Resources
===============


GlobalConfiguration
-------------------

The Global Configuration resource represents the configuration settings for
iSCSI.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/iscsi/globalconfiguration/

   Returns the iSCSI Global Configuration settings dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/iscsi/globalconfiguration/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "iscsi_maxconnect": 8,
                "iscsi_luc_authnetwork": "",
                "iscsi_iotimeout": 30,
                "iscsi_lucip": "127.0.0.1",
                "iscsi_firstburst": 65536,
                "iscsi_r2t": 32,
                "iscsi_discoveryauthmethod": "None",
                "iscsi_defaultt2w": 2,
                "iscsi_maxrecdata": 262144,
                "iscsi_basename": "iqn.2011-03.org.example.istgt",
                "iscsi_defaultt2r": 60,
                "iscsi_nopinint": 20,
                "iscsi_discoveryauthgroup": null,
                "iscsi_maxburst": 262144,
                "iscsi_toggleluc": false,
                "iscsi_lucport": 3261,
                "iscsi_luc_authgroup": null,
                "iscsi_maxsesh": 16,
                "iscsi_luc_authmethod": "",
                "iscsi_maxoutstandingr2t": 16,
                "id": 1
        }

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/iscsi/globalconfiguration/

   Update Global Configuration.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/iscsi/globalconfiguration/ HTTP/1.1
      Content-Type: application/json

        {
                "iscsi_maxconnect": 16
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "iscsi_maxconnect": 16,
                "iscsi_luc_authnetwork": "",
                "iscsi_iotimeout": 30,
                "iscsi_lucip": "127.0.0.1",
                "iscsi_firstburst": 65536,
                "iscsi_r2t": 32,
                "iscsi_discoveryauthmethod": "None",
                "iscsi_defaultt2w": 2,
                "iscsi_maxrecdata": 262144,
                "iscsi_basename": "iqn.2011-03.org.example.istgt",
                "iscsi_defaultt2r": 60,
                "iscsi_nopinint": 20,
                "iscsi_discoveryauthgroup": null,
                "iscsi_maxburst": 262144,
                "iscsi_toggleluc": false,
                "iscsi_lucport": 3261,
                "iscsi_luc_authgroup": null,
                "iscsi_maxsesh": 16,
                "iscsi_luc_authmethod": "",
                "iscsi_maxoutstandingr2t": 16,
                "id": 1
        }

   :json string iscsi_basename: base name (e.g. iqn.2007-09.jp.ne.peach.istgt, see RFC 3720 and 3721 for details)
   :json string iscsi_discoveryauthmethod: None, Auto, CHAP, CHAP Mutual
   :json string iscsi_discoveryauthgroup: id of auth group
   :json string iscsi_iotimeout: I/O timeout in seconds
   :json string iscsi_nopinint: NOPIN sending interval in seconds
   :json string iscsi_maxsesh: maximum number of sessions holding at same time
   :json string iscsi_maxconnect: maximum number of connections in each session
   :json string iscsi_r2t: maximum number of pre-send R2T in each connection
   :json string iscsi_maxoutstandingr2t: MaxOutstandingR2T
   :json string iscsi_firstburst: first burst length
   :json string iscsi_maxburst: max burst length
   :json string iscsi_maxrecdata: max receive data segment length
   :json string iscsi_defaultt2w: DefaultTime2Wait
   :json string iscsi_defaultt2r: DefaultTime2Retain
   :json string iscsi_toggleluc: Enable LUC
   :json string iscsi_lucip: Controller IP address
   :json string iscsi_lucport: Controller TCP port
   :json string iscsi_luc_authnetwork: Controller Authorized Network
   :json string iscsi_luc_authmethod: None, Auto, CHAP, CHAP Mutual
   :json string iscsi_luc_authgroup: id of auth group
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error
