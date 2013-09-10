=========
Sharing
=========

Resources related to sharing.

CIFS_Share
----------

The CIFS_Share resource represents CIFS shares using samba.

List resource
+++++++++++++

.. http:get:: /api/v1.0/sharing/cifs_share/

   Returns a list of all CIFS shares.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/sharing/cifs_share/ HTTP/1.1
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

.. http:post:: /api/v1.0/sharing/cifs_share/

   Creates a new CIFS share and returns the new CIFS share object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/sharing/cifs_share/ HTTP/1.1
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

.. http:put:: /api/v1.0/sharing/cifs_share/(int:id)/

   Update CIFS share `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/sharing/cifs_share/2/ HTTP/1.1
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

.. http:delete:: /api/v1.0/sharing/cifs_share/(int:id)/

   Delete CIFS share `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/sharing/cifs_share/2/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error
