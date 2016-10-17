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
                "iscsi_basename": "iqn.2011-03.org.example.istgt",
                "iscsi_isns_servers": "",
                "iscsi_pool_avail_threshold": null,
                "id": 1
        }

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

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "iscsi_basename": "iqn.2011-03.org.example.istgt",
                "id": 1
        }

   :json string iscsi_basename: base name (e.g. iqn.2007-09.jp.ne.peach.istgt, see RFC 3720 and 3721 for details)
   :json string iscsi_isns_servers: List of Internet Storage Name Service (iSNS) Servers
   :json integer iscsi_pool_avail_threshold: pool capacity warning threshold when using zvol extents
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error



Extent
------

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
                "iscsi_target_extent_insecure_tpc": true,
                "iscsi_target_extent_naa": "0x3822690834aae6c5",
                "id": 1,
                "iscsi_target_extent_path": "/mnt/tank/iscsi"
                "iscsi_target_extent_xen": false,
                "iscsi_target_extent_avail_threshold": null,
                "iscsi_target_extent_blocksize": 512,
                "iscsi_target_extent_pblocksize": false,
                "iscsi_target_extent_rpm": "SSD",
                "iscsi_target_extent_ro": false,
                "iscsi_target_extent_serial": "08002724ab5601"
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 20
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
                "iscsi_target_extent_insecure_tpc": true,
                "iscsi_target_extent_naa": "0x3822690834aae6c5",
                "id": 1,
                "iscsi_target_extent_path": "/mnt/tank/iscsi"
                "iscsi_target_extent_xen": false,
                "iscsi_target_extent_avail_threshold": null,
                "iscsi_target_extent_blocksize": 512,
                "iscsi_target_extent_pblocksize": false,
                "iscsi_target_extent_rpm": "SSD",
                "iscsi_target_extent_ro": false,
                "iscsi_target_extent_serial": "08002724ab5601"
        }

   :json string iscsi_target_extent_name: identifier of the extent
   :json string iscsi_target_extent_type: File, Disk
   :json string iscsi_target_extent_path: path to the extent (for File type)
   :json string iscsi_target_extent_disk: path to the disk or zvol (for Disk type)  e.g. "zvol/tank/zvol1", "ada1"
   :json string iscsi_target_extent_filesize: size of extent, 0 means auto, a raw number is bytes, or suffix with KB, MB, TB for convenience
   :json boolean iscsi_target_extent_insecure_tpc: allow initiators to xcopy without authenticating to foreign targets
   :json boolean iscsi_target_extent_xen: Xen initiator compat mode
   :json string iscsi_target_extent_comment: user description
   :json integer iscsi_target_extent_avail_threshold: Remaining dataset/zvol capacity warning threshold
   :json integer iscsi_target_extent_blocksize: Logical Block Size
   :json boolean iscsi_target_extent_pblocksize: Disable Physical Block Size Reporting
   :json string iscsi_target_extent_rpm: Unknown, SSD, 5400, 7200, 10000, 15000
   :json string iscsi_target_extent_serial: Serial number for the logical unit
   :json boolean iscsi_target_extent_ro: Read-only extent
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Create extent using zvol.

.. http:post:: /api/v1.0/services/iscsi/extent/

   Creates a new extent using zvol and returns the new extent object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/services/iscsi/extent/ HTTP/1.1
      Content-Type: application/json

        {
                "iscsi_target_extent_type": "Disk",
                "iscsi_target_extent_name": "zvolextent",
                "iscsi_target_extent_disk": "zvol/tank/zvolextent"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "iscsi_target_extent_comment": "",
                "iscsi_target_extent_type": "ZVOL",
                "iscsi_target_extent_name": "zvolextent",
                "iscsi_target_extent_filesize": "0",
                "iscsi_target_extent_insecure_tpc": true,
                "iscsi_target_extent_naa": "0x3822690834aae6c5",
                "id": 1,
                "iscsi_target_extent_path": "/dev/zvol/tank/zvolextent",
                "iscsi_target_extent_xen": false,
                "iscsi_target_extent_avail_threshold": null,
                "iscsi_target_extent_blocksize": 512,
                "iscsi_target_extent_pblocksize": false,
                "iscsi_target_extent_rpm": "SSD",
                "iscsi_target_extent_ro": false,
                "iscsi_target_extent_serial": "08002724ab5601"
        }


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

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "iscsi_target_extent_comment": "",
                "iscsi_target_extent_type": "File",
                "iscsi_target_extent_name": "extent",
                "iscsi_target_extent_filesize": "20MB",
                "iscsi_target_extent_insecure_tpc": true,
                "iscsi_target_extent_naa": "0x3822690834aae6c5",
                "id": 1,
                "iscsi_target_extent_path": "/mnt/tank/iscsi"
                "iscsi_target_extent_xen": false,
                "iscsi_target_extent_avail_threshold": null,
                "iscsi_target_extent_blocksize": 512,
                "iscsi_target_extent_pblocksize": false,
                "iscsi_target_extent_rpm": "SSD",
                "iscsi_target_extent_serial": "08002724ab5601"
        }

   :json string iscsi_target_extent_name: identifier of the extent
   :json string iscsi_target_extent_type: File, Disk
   :json string iscsi_target_extent_path: path to the extent (for File type)
   :json string iscsi_target_extent_disk: path to the disk or zvol (for Disk type)  e.g. "zvol/tank/zvol1", "ada1"
   :json string iscsi_target_extent_filesize: size of extent, 0 means auto, a raw number is bytes, or suffix with KB, MB, TB for convenience
   :json boolean iscsi_target_extent_insecure_tpc: allow initiators to xcopy without authenticating to foreign targets
   :json boolean iscsi_target_extent_xen: Xen initiator compat mode
   :json string iscsi_target_extent_comment: user description
   :json integer iscsi_target_extent_avail_threshold: Remaining dataset/zvol capacity warning threshold
   :json integer iscsi_target_extent_blocksize: Logical Block Size
   :json boolean iscsi_target_extent_pblocksize: Disable Physical Block Size Reporting
   :json string iscsi_target_extent_rpm: Unknown, SSD, 5400, 7200, 10000, 15000
   :json string iscsi_target_extent_serial: Serial number for the logical unit
   :json boolean iscsi_target_extent_ro: Read-only extent
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
   :query limit: limit number. default is 20
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

      HTTP/1.1 200 OK
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
   :query limit: limit number. default is 20
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

      HTTP/1.1 200 OK
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
------

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
                "iscsi_target_name": "target",
                "iscsi_target_alias": null,
                "id": 1
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 20
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
                "iscsi_target_name": "target"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "iscsi_target_name": "target",
                "iscsi_target_alias": null,
                "id": 1
        }

   :json string iscsi_target_name: Base Name will be appended automatically when starting without "iqn.".
   :json string iscsi_target_alias: optional user-friendly string of the target
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
                "iscsi_target_alias": "test"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "iscsi_target_name": "target",
                "iscsi_target_alias": "test",
                "id": 1
        }

   :json string iscsi_target_name: Base Name will be appended automatically when starting without "iqn.".
   :json string iscsi_target_alias: optional user-friendly string of the target
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


TargetGroup
-----------

The TargetGroup resource represents groups associated to iSCSI target.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/iscsi/targetgroup/

   Returns a list of all targets.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/iscsi/targetgroup/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
          "iscsi_target": 1,
          "iscsi_target_authgroup": null,
          "iscsi_target_portalgroup": 1,
          "iscsi_target_initiatorgroup": null,
          "iscsi_target_authtype": "None",
          "iscsi_target_initialdigest": "Auto"
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 20
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/services/iscsi/targetgroup/

   Creates a new target group and returns the new object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/services/iscsi/targetgroup/ HTTP/1.1
      Content-Type: application/json

        {
                "iscsi_target": 1,
                "iscsi_target_authgroup": null,
                "iscsi_target_authtype": "None",
                "iscsi_target_portalgroup": 1,
                "iscsi_target_initiatorgroup": null,
                "iscsi_target_initialdigest": "Auto"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "iscsi_target": 1,
                "iscsi_target_authgroup": null,
                "iscsi_target_authtype": "None",
                "iscsi_target_portalgroup": 1,
                "iscsi_target_initiatorgroup": null,
                "iscsi_target_initialdigest": "Auto"
        }

   :json integer iscsi_target: id of the target object
   :json integer iscsi_target_initiatorgroup: id of the initiator object
   :json integer iscsi_target_portalgroup: id of the portal object
   :json integer iscsi_target_authgroup: number of the authentication group
   :json string iscsi_target_initialdigest: defaults to Auto
   :json string iscsi_target_authtype: None, CHAP, CHAP Mutual
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/iscsi/targetgroup/(int:id)/

   Update target group `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/iscsi/targetgroup/1/ HTTP/1.1
      Content-Type: application/json

        {
                "iscsi_target_initialdigest": "CHAP"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "id": 1,
                "iscsi_target": 1,
                "iscsi_target_authgroup": null,
                "iscsi_target_authtype": "None",
                "iscsi_target_portalgroup": 1,
                "iscsi_target_initiatorgroup": null,
                "iscsi_target_initialdigest": "CHAP"
        }

   :json integer iscsi_target: id of the target object
   :json integer iscsi_target_initiatorgroup: id of the initiator object
   :json integer iscsi_target_portalgroup: id of the portal object
   :json integer iscsi_target_authgroup: number of the authentication group
   :json string iscsi_target_initialdigest: defaults to Auto
   :json string iscsi_target_authtype: None, CHAP, CHAP Mutual
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/services/iscsi/targetgroup/(int:id)/

   Delete target group `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/services/iscsi/targetgroup/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


Target To Extent
----------------

The Target To Extent resource represents association between targets and extents.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/iscsi/targettoextent/

   Returns a list of all target to extent.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/iscsi/targettoextent/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 20
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/services/iscsi/targettoextent/

   Creates a new target to extent and returns the new object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/services/iscsi/targettoextent/ HTTP/1.1
      Content-Type: application/json

        {
                "iscsi_target": 1,
                "iscsi_extent": 1
                "iscsi_lunid": null,
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "iscsi_target": 1,
                "iscsi_extent": 1,
                "iscsi_lunid": null,
                "id": 1
        }

   :json integer iscsi_target: id of the target object
   :json integer iscsi_extent: id of the extent object
   :json integer iscsi_lunid: id of the LUN
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/iscsi/targettoextent/(int:id)/

   Update target to extent `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/iscsi/targettoextent/1/ HTTP/1.1
      Content-Type: application/json

        {
                "iscsi_extent": 2
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "iscsi_target": 1,
                "iscsi_extent": 2,
                "id": 1
        }

   :json integer iscsi_target: id of the target object
   :json integer iscsi_extent: id of the extent object
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/services/iscsi/targettoextent/(int:id)/

   Delete target to extent `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/services/iscsi/targettoextent/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


Portal
--------------------

The Portal resource represents IPs and ports which the daemon will listen to.

List resource
+++++++++++++

.. http:get:: /api/v1.0/services/iscsi/portal/

   Returns a list of all portals.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/services/iscsi/portal/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "iscsi_target_portal_tag": 1,
                "id": 1,
                "iscsi_target_portal_discoveryauthmethod": "None",
                "iscsi_target_portal_discoveryauthgroup": null,
                "iscsi_target_portal_ips": [
                        "0.0.0.0:3260"
                ],
                "iscsi_target_portal_comment": ""
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 20
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/services/iscsi/portal/

   Creates a new portal and returns the new object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/services/iscsi/portal/ HTTP/1.1
      Content-Type: application/json

        {
                "iscsi_target_portal_ips": [
                        "0.0.0.0:3260"
                ]
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "iscsi_target_portal_tag": 1,
                "id": 1,
                "iscsi_target_portal_discoveryauthmethod": "None",
                "iscsi_target_portal_discoveryauthgroup": null,
                "iscsi_target_portal_ips": [
                        "0.0.0.0:3260"
                ],
                "iscsi_target_portal_comment": ""
        }

   :json string iscsi_target_portal_comment: user description
   :json list(string) iscsi_target_portal_ips: IP:PORT to listen to
   :json string iscsi_target_portal_discoveryauthmethod: None, Auto, CHAP, CHAP Mutual
   :json string iscsi_target_portal_discoveryauthgroup: id of auth group
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/services/iscsi/portal/(int:id)/

   Update portal `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/services/iscsi/portal/1/ HTTP/1.1
      Content-Type: application/json

        {
                "iscsi_target_portal_ips": [
                        "192.168.3.20:3260"
                ]
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "iscsi_target_portal_tag": 1,
                "id": 1,
                "iscsi_target_portal_discoveryauthmethod": "None",
                "iscsi_target_portal_discoveryauthgroup": null,
                "iscsi_target_portal_ips": [
                        "192.168.3.20:3260"
                ],
                "iscsi_target_portal_comment": ""
        }

   :json string iscsi_target_portal_comment: user description
   :json list(string) iscsi_target_portal_ips: IP:PORT to listen to
   :json string iscsi_target_portal_discoveryauthmethod: None, Auto, CHAP, CHAP Mutual
   :json string iscsi_target_portal_discoveryauthgroup: id of auth group
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/services/iscsi/portal/(int:id)/

   Delete portal `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/services/iscsi/portal/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error
