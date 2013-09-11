=========
Sharing
=========

Resources related to sharing.

CIFS
----------

The CIFS resource represents CIFS shares using samba.

List resource
+++++++++++++

.. http:get:: /api/v1.0/sharing/cifs/

   Returns a list of all CIFS shares.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/sharing/cifs/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "cifs_inheritperms": false,
                "cifs_hostsallow": "",
                "cifs_name": "My Test Share",
                "cifs_guestok": false,
                "cifs_showhiddenfiles": false,
                "cifs_hostsdeny": "",
                "cifs_recyclebin": false,
                "cifs_auxsmbconf": "",
                "cifs_comment": "",
                "cifs_path": "/mnt/tank/MyShare",
                "cifs_ro": false,
                "cifs_inheritowner": false,
                "cifs_guestonly": true,
                "id": 1,
                "cifs_browsable": true
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/sharing/cifs/

   Creates a new CIFS share and returns the new CIFS share object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/sharing/cifs/ HTTP/1.1
      Content-Type: application/json

        {
                "cifs_name": "My Test Share",
                "cifs_path": "/mnt/tank/MyShare"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "cifs_inheritperms": false,
                "cifs_hostsallow": "",
                "cifs_name": "My Test Share",
                "cifs_guestok": false,
                "cifs_showhiddenfiles": false,
                "cifs_hostsdeny": "",
                "cifs_recyclebin": false,
                "cifs_auxsmbconf": "",
                "cifs_comment": "",
                "cifs_path": "/mnt/tank/MyShare",
                "cifs_ro": false,
                "cifs_inheritowner": false,
                "cifs_guestonly": true,
                "id": 1,
        }

   :json string cifs_name: name of the share
   :json string cifs_path: path to share
   :json string cifs_comment: user comment
   :json string cifs_hostsallow: explictly allowed hosts
   :json string cifs_hostsdeny: explicitly denied hosts
   :json string cifs_auxsmbconf: auxiliar parameters to append to smb.conf
   :json boolean cifs_inheritperms: inherit permissions
   :json boolean cifs_guestok: allow guests
   :json boolean cifs_guestonly: only guests are allowed
   :json boolean cifs_showhiddenfiles: show hidden files
   :json boolean cifs_recyclebin: enable recycle bin
   :json boolean cifs_ro: readonly share
   :json boolean cifs_inheritowner: inherit owners
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/sharing/cifs/(int:id)/

   Update CIFS share `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/sharing/cifs/1/ HTTP/1.1
      Content-Type: application/json

        {
                "cifs_guestok": true
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "cifs_inheritperms": false,
                "cifs_hostsallow": "",
                "cifs_name": "My Test Share",
                "cifs_guestok": true,
                "cifs_showhiddenfiles": false,
                "cifs_hostsdeny": "",
                "cifs_recyclebin": false,
                "cifs_auxsmbconf": "",
                "cifs_comment": "",
                "cifs_path": "/mnt/tank/MyShare",
                "cifs_ro": false,
                "cifs_inheritowner": false,
                "cifs_guestonly": true,
                "id": 1,
        }

   :json string cifs_name: name of the share
   :json string cifs_path: path to share
   :json string cifs_comment: user comment
   :json string cifs_hostsallow: explictly allowed hosts
   :json string cifs_hostsdeny: explicitly denied hosts
   :json string cifs_auxsmbconf: auxiliar parameters to append to smb.conf
   :json boolean cifs_inheritperms: inherit permissions
   :json boolean cifs_guestok: allow guests
   :json boolean cifs_guestonly: only guests are allowed
   :json boolean cifs_showhiddenfiles: show hidden files
   :json boolean cifs_recyclebin: enable recycle bin
   :json boolean cifs_ro: readonly share
   :json boolean cifs_inheritowner: inherit owners
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/sharing/cifs/(int:id)/

   Delete CIFS share `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/sharing/cifs/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


NFS
----------

The NFS resource represents NFS shares.

List resource
+++++++++++++

.. http:get:: /api/v1.0/sharing/nfs/

   Returns a list of all NFS shares.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/sharing/nfs/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "nfs_inheritperms": false,
                "nfs_hostsallow": "",
                "nfs_name": "My Test Share",
                "nfs_guestok": false,
                "nfs_showhiddenfiles": false,
                "nfs_hostsdeny": "",
                "nfs_recyclebin": false,
                "nfs_auxsmbconf": "",
                "nfs_comment": "",
                "nfs_path": "/mnt/tank/MyShare",
                "nfs_ro": false,
                "nfs_inheritowner": false,
                "nfs_guestonly": true,
                "id": 1,
                "nfs_browsable": true
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/sharing/nfs/

   Creates a new NFS share and returns the new NFS share object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/sharing/nfs/ HTTP/1.1
      Content-Type: application/json

        {
                "nfs_comment": "My Test Share",
                "nfs_paths": ["/mnt/tank"]
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "nfs_mapall_user": "",
                "nfs_maproot_group": "",
                "nfs_maproot_user": "",
                "nfs_network": "",
                "nfs_ro": false,
                "nfs_hosts": "",
                "nfs_alldirs": false,
                "nfs_mapall_group": "",
                "nfs_comment": "My Test Share",
                "nfs_paths": [
                        "/mnt/tank"
                ],
                "id": 1,
                "nfs_quiet": false
        }

   :json list(string) nfs_paths: paths to share
   :json string nfs_comment: user comment
   :json string nfs_hosts: allowed hosts or ip addresses
   :json string nfs_network: allowed networks
   :json string nfs_maproot_user: limit root to this user permissions
   :json string nfs_maproot_group: limit root to this group permissions
   :json string nfs_mapall_user: user used by all clients
   :json string nfs_mapall_group: group used by all clients
   :json boolean nfs_alldirs: allow mounting of any subdirectory
   :json boolean nfs_ro: readonly share
   :json boolean nfs_quiet: inhibit syslog warnings
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/sharing/nfs/(int:id)/

   Update NFS share `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/sharing/nfs/1/ HTTP/1.1
      Content-Type: application/json

        {
                "nfs_ro": true
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "nfs_mapall_user": "",
                "nfs_maproot_group": "",
                "nfs_maproot_user": "",
                "nfs_network": "",
                "nfs_ro": true,
                "nfs_hosts": "",
                "nfs_alldirs": false,
                "nfs_mapall_group": "",
                "nfs_comment": "My Test Share",
                "nfs_paths": [
                        "/mnt/tank"
                ],
                "id": 1,
                "nfs_quiet": false
        }

   :json list(string) nfs_paths: paths to share
   :json string nfs_comment: user comment
   :json string nfs_hosts: allowed hosts or ip addresses
   :json string nfs_network: allowed networks
   :json string nfs_maproot_user: limit root to this user permissions
   :json string nfs_maproot_group: limit root to this group permissions
   :json string nfs_mapall_user: user used by all clients
   :json string nfs_mapall_group: group used by all clients
   :json boolean nfs_alldirs: allow mounting of any subdirectory
   :json boolean nfs_ro: readonly share
   :json boolean nfs_quiet: inhibit syslog warnings
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/sharing/nfs/(int:id)/

   Delete NFS share `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/sharing/nfs/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error
