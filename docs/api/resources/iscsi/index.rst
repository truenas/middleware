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



Extent
----------

The Extent resource represents extents for the iSCSI targets.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/iscsi/extent/

   Returns a list of all extents.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/iscsi/extent/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "iscsi_target_extent_comment": "",
                "iscsi_target_extent_type": "File",
                "iscsi_target_extent_name": "extent",
                "iscsi_target_extent_filesize": "10MB",
                "id": 1,
                "iscsi_target_extent_path": "/mnt/tank/iscsi"
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/services/iscsi/extent/

   Creates a new extent and returns the new extent object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/services/iscsi/extent/ HTTP/1.1
      Content-Type: application/json

        {
                "iscsi_target_extent_type": "File",
                "iscsi_target_extent_name": "extent",
                "iscsi_target_extent_filesize": "10MB",
                "iscsi_target_extent_path": "/mnt/tank/iscsi"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "iscsi_target_extent_comment": "",
                "iscsi_target_extent_type": "File",
                "iscsi_target_extent_name": "extent",
                "iscsi_target_extent_filesize": "10MB",
                "id": 1,
                "iscsi_target_extent_path": "/mnt/tank/iscsi"
        }

   :json string iscsi_target_extent_name: identifier of the extent
   :json string iscsi_target_extent_type: File, Device, ZFS Volume
   :json string iscsi_target_extent_path: path to the extent
   :json string iscsi_target_extent_filesize: size of extent, 0 means auto, a raw number is bytes, or suffix with KB, MB, TB for convenience
   :json string iscsi_target_extent_comment: user description
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/iscsi/extent/(int:id)/

   Update extent `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/iscsi/extent/1/ HTTP/1.1
      Content-Type: application/json

        {
                "iscsi_target_extent_filesize": "20MB"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "iscsi_target_extent_comment": "",
                "iscsi_target_extent_type": "File",
                "iscsi_target_extent_name": "extent",
                "iscsi_target_extent_filesize": "20MB",
                "id": 1,
                "iscsi_target_extent_path": "/mnt/tank/iscsi"
        }

   :json string iscsi_target_extent_name: identifier of the extent
   :json string iscsi_target_extent_type: File, Device, ZFS Volume
   :json string iscsi_target_extent_path: path to the extent
   :json string iscsi_target_extent_filesize: size of extent, 0 means auto, a raw number is bytes, or suffix with KB, MB, TB for convenience
   :json string iscsi_target_extent_comment: user description
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/services/iscsi/extent/(int:id)/

   Delete extent `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/services/iscsi/extent/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


Authorized Initiator
--------------------

The Authorized Initiator resource represents network authorized to access to the iSCSI target.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/iscsi/authorizedinitiator/

   Returns a list of all authorized initiators.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/iscsi/authorizedinitiator/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "iscsi_target_initiator_initiators": "ALL",
                "iscsi_target_initiator_comment": "",
                "iscsi_target_initiator_auth_network": "ALL",
                "id": 1,
                "iscsi_target_initiator_tag": 1
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/services/iscsi/authorizedinitiator/

   Creates a new authorized initiator and returns the new object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/services/iscsi/authorizedinitiator/ HTTP/1.1
      Content-Type: application/json

        {
                "iscsi_target_initiator_initiators": "ALL",
                "iscsi_target_initiator_auth_network": "ALL",
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "iscsi_target_initiator_initiators": "ALL",
                "iscsi_target_initiator_comment": "",
                "iscsi_target_initiator_auth_network": "ALL",
                "id": 1,
                "iscsi_target_initiator_tag": 1
        }

   :json string iscsi_target_initiator_initiators: initiator authorized to access to the iSCSI target
   :json string iscsi_target_initiator_auth_network: network authorized to access to the iSCSI target, it takes IP or CIDR addresses or "ALL" for any IPs
   :json string scsi_target_initiator_comment: description for your reference
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/iscsi/authorizedinitiator/(int:id)/

   Update authorized initiator `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/iscsi/authorizedinitiator/1/ HTTP/1.1
      Content-Type: application/json

        {
                "iscsi_target_initiator_auth_network": "192.168.3.0/24"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "iscsi_target_initiator_initiators": "ALL",
                "iscsi_target_initiator_comment": "",
                "iscsi_target_initiator_auth_network": "192.168.3.0/24",
                "id": 1,
                "iscsi_target_initiator_tag": 1
        }

   :json string iscsi_target_initiator_initiators: initiator authorized to access to the iSCSI target
   :json string iscsi_target_initiator_auth_network: network authorized to access to the iSCSI target, it takes IP or CIDR addresses or "ALL" for any IPs
   :json string scsi_target_initiator_comment: description for your reference
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/services/iscsi/authorizedinitiator/(int:id)/

   Delete authorized initiator `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/services/iscsi/authorizedinitiator/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


Auth Credential
--------------------

The Auth Credential resource represents user credentials to access the iSCSI target.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/iscsi/authcredential/

   Returns a list of all auth credentials.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/iscsi/authcredential/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "iscsi_target_auth_secret": "secret",
                "iscsi_target_auth_peeruser": "peeruser",
                "iscsi_target_auth_peersecret": "peersecret",
                "iscsi_target_auth_user": "user",
                "iscsi_target_auth_tag": 1,
                "id": 1
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/services/iscsi/authcredential/

   Creates a new auth credential and returns the new object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/services/iscsi/authcredential/ HTTP/1.1
      Content-Type: application/json

        {
                "iscsi_target_auth_secret": "secret",
                "iscsi_target_auth_peeruser": "peeruser",
                "iscsi_target_auth_peersecret": "peersecret",
                "iscsi_target_auth_user": "user",
                "iscsi_target_auth_tag": 1
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "iscsi_target_auth_secret": "secret",
                "iscsi_target_auth_peeruser": "peeruser",
                "iscsi_target_auth_peersecret": "peersecret",
                "iscsi_target_auth_user": "user",
                "iscsi_target_auth_tag": 1,
                "id": 1
        }

   :json string iscsi_target_auth_tag: group id
   :json string iscsi_target_auth_user: target side user name
   :json string iscsi_target_auth_secret: target side secret
   :json string iscsi_target_auth_peeruser: initiator side user name
   :json string iscsi_target_auth_peersecret: initiator side secret
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/iscsi/authcredential/(int:id)/

   Update auth credential `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/iscsi/authcredential/1/ HTTP/1.1
      Content-Type: application/json

        {
                "iscsi_target_auth_peeruser": "myuser"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "iscsi_target_auth_secret": "secret",
                "iscsi_target_auth_peeruser": "myuser",
                "iscsi_target_auth_peersecret": "peersecret",
                "iscsi_target_auth_user": "user",
                "iscsi_target_auth_tag": 1,
                "id": 1
        }

   :json string iscsi_target_auth_tag: group id
   :json string iscsi_target_auth_user: target side user name
   :json string iscsi_target_auth_secret: target side secret
   :json string iscsi_target_auth_peeruser: initiator side user name
   :json string iscsi_target_auth_peersecret: initiator side secret
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/services/iscsi/authcredential/(int:id)/

   Delete auth credential `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/services/iscsi/authcredential/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


Target
--------------------

The Target resource represents user credentials to access the iSCSI target.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/iscsi/target/

   Returns a list of all targets.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/iscsi/target/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "iscsi_target_logical_blocksize": 512,
                "iscsi_target_portalgroup": 1,
                "iscsi_target_initialdigest": "Auto",
                "iscsi_target_queue_depth": 32,
                "iscsi_target_name": "target",
                "iscsi_target_initiatorgroup": 1,
                "iscsi_target_alias": null,
                "iscsi_target_type": "Disk",
                "iscsi_target_authgroup": null,
                "iscsi_target_authtype": "Auto",
                "iscsi_target_serial": "10000001",
                "iscsi_target_flags": "rw",
                "id": 1
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/services/iscsi/target/

   Creates a new target and returns the new object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/services/iscsi/target/ HTTP/1.1
      Content-Type: application/json

        {
                "iscsi_target_name": "target",
                "iscsi_target_portalgroup": 1,
                "iscsi_target_initiatorgroup": 1
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "iscsi_target_logical_blocksize": 512,
                "iscsi_target_portalgroup": 1,
                "iscsi_target_initialdigest": "Auto",
                "iscsi_target_queue_depth": 32,
                "iscsi_target_name": "target",
                "iscsi_target_initiatorgroup": 1,
                "iscsi_target_alias": null,
                "iscsi_target_type": "Disk",
                "iscsi_target_authgroup": null,
                "iscsi_target_authtype": "Auto",
                "iscsi_target_serial": "10000001",
                "iscsi_target_flags": "rw",
                "id": 1
        }

   :json string iscsi_target_name: Base Name will be appended automatically when starting without 'iqn.'.
   :json string iscsi_target_alias: optional user-friendly string of the target
   :json string iscsi_target_serial: serial number for the logical unit
   :json string iscsi_target_flags: rw, ro
   :json integer iscsi_target_portalgroup: id of a portal group
   :json integer iscsi_target_initiatorgroup: id of a initiator group
   :json string iscsi_target_authtype: None, Auto, CHAP, CHAP Mutual
   :json integer iscsi_target_authgroup: Authentication Group ID
   :json string iscsi_target_initialdigest: the method can be accepted by the target. Auto means both none and authentication
   :json integer iscsi_target_queue_depth: 0=disabled, 1-255=enabled command queuing with specified depth. The recommended queue depth is 32
   :json integer iscsi_target_logical_blocksize: yYou may specify logical block length (512 by default)
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/iscsi/target/(int:id)/

   Update target `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/iscsi/target/1/ HTTP/1.1
      Content-Type: application/json

        {
                "iscsi_target_queue_depth": 64
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "iscsi_target_logical_blocksize": 512,
                "iscsi_target_portalgroup": 1,
                "iscsi_target_initialdigest": "Auto",
                "iscsi_target_queue_depth": 64,
                "iscsi_target_name": "target",
                "iscsi_target_initiatorgroup": 1,
                "iscsi_target_alias": null,
                "iscsi_target_type": "Disk",
                "iscsi_target_authgroup": null,
                "iscsi_target_authtype": "Auto",
                "iscsi_target_serial": "10000001",
                "iscsi_target_flags": "rw",
                "id": 1
        }

   :json string iscsi_target_name: Base Name will be appended automatically when starting without 'iqn.'.
   :json string iscsi_target_alias: optional user-friendly string of the target
   :json string iscsi_target_serial: serial number for the logical unit
   :json string iscsi_target_flags: rw, ro
   :json integer iscsi_target_portalgroup: id of a portal group
   :json integer iscsi_target_initiatorgroup: id of a initiator group
   :json string iscsi_target_authtype: None, Auto, CHAP, CHAP Mutual
   :json integer iscsi_target_authgroup: Authentication Group ID
   :json string iscsi_target_initialdigest: the method can be accepted by the target. Auto means both none and authentication
   :json integer iscsi_target_queue_depth: 0=disabled, 1-255=enabled command queuing with specified depth. The recommended queue depth is 32
   :json integer iscsi_target_logical_blocksize: yYou may specify logical block length (512 by default)
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/services/iscsi/target/(int:id)/

   Delete target `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/services/iscsi/target/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error
