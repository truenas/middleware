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


AFP
----------

The AFP resource represents AFP shares.

List resource
+++++++++++++

.. http:get:: /api/v1.0/sharing/afp/

   Returns a list of all AFP shares.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/sharing/afp/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "afp_inheritperms": false,
                "afp_hostsallow": "",
                "afp_name": "My Test Share",
                "afp_guestok": false,
                "afp_showhiddenfiles": false,
                "afp_hostsdeny": "",
                "afp_recyclebin": false,
                "afp_auxsmbconf": "",
                "afp_comment": "",
                "afp_path": "/mnt/tank/MyShare",
                "afp_ro": false,
                "afp_inheritowner": false,
                "afp_guestonly": true,
                "id": 1,
                "afp_browsable": true
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/sharing/afp/

   Creates a new AFP share and returns the new AFP share object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/sharing/afp/ HTTP/1.1
      Content-Type: application/json

        {
                "afp_name": "My Test Share",
                "afp_path": "/mnt/tank"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "afp_adouble": true,
                "afp_upriv": true,
                "afp_mswindows": false,
                "afp_prodos": false,
                "afp_nofileid": false,
                "id": 1,
                "afp_comment": "",
                "afp_fperm": "755",
                "afp_deny": "",
                "afp_diskdiscovery": false,
                "afp_sharecharset": "",
                "afp_nostat": false,
                "afp_name": "test share",
                "afp_discoverymode": "default",
                "afp_nohex": false,
                "afp_nodev": false,
                "afp_rw": "",
                "afp_allow": "",
                "afp_dperm": "644",
                "afp_ro": "",
                "afp_sharepw": "",
                "afp_dbpath": "",
                "afp_cachecnid": false,
                "afp_path": "/mnt/tank",
                "afp_crlf": false
        }

   :json string afp_path: paths to share
   :json string afp_name: share name
   :json string afp_comment: user comment
   :json string afp_fperm: default file permission
   :json string afp_dperm: default file permission
   :json string afp_allow: users and groups allowed to access
   :json string afp_deny: users or groups not allowed to access
   :json string afp_sharecharset: character set for the share
   :json string afp_discoverymode: default, time-machine
   :json string afp_rw: users and groups allowed to read and write
   :json string afp_ro: users and groups allowed to read only
   :json string afp_sharepw: password for the share
   :json string afp_dbpath: path to set database information
   :json boolean afp_adouble: enable automatic creation of .AppleDouble
   :json boolean afp_upriv: use AFP3 unix privileges
   :json boolean afp_mswindows: restrict filenames to charset used by Windows
   :json boolean afp_prodos: compatibility with Apple II clients
   :json boolean afp_nofileid: don't advertise createfileid, resolveid, deleteid calls
   :json boolean afp_diskdiscovery: allow other systems to discover this share as a disk for data, as a Time Machine backup volume or not at all
   :json boolean afp_nostat: don't stat volume path when enumerating volumes list
   :json boolean afp_nohex: disable :hex translations for anything except dot files
   :json boolean afp_nodev: always use 0 for device number
   :json boolean afp_cachecnid:  uses the ID information stored in AppleDouble V2 header files to reduce database load
   :json boolean afp_crlf: crlf translation for TEXT files
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/sharing/afp/(int:id)/

   Update AFP share `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/sharing/afp/1/ HTTP/1.1
      Content-Type: application/json

        {
                "afp_adouble": false
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "afp_adouble": false,
                "afp_upriv": true,
                "afp_mswindows": false,
                "afp_prodos": false,
                "afp_nofileid": false,
                "id": 1,
                "afp_comment": "",
                "afp_fperm": "755",
                "afp_deny": "",
                "afp_diskdiscovery": false,
                "afp_sharecharset": "",
                "afp_nostat": false,
                "afp_name": "test share",
                "afp_discoverymode": "default",
                "afp_nohex": false,
                "afp_nodev": false,
                "afp_rw": "",
                "afp_allow": "",
                "afp_dperm": "644",
                "afp_ro": "",
                "afp_sharepw": "",
                "afp_dbpath": "",
                "afp_cachecnid": false,
                "afp_path": "/mnt/tank",
                "afp_crlf": false
        }

   :json string afp_path: paths to share
   :json string afp_name: share name
   :json string afp_comment: user comment
   :json string afp_fperm: default file permission
   :json string afp_dperm: default file permission
   :json string afp_allow: users and groups allowed to access
   :json string afp_deny: users or groups not allowed to access
   :json string afp_sharecharset: character set for the share
   :json string afp_discoverymode: default, time-machine
   :json string afp_rw: users and groups allowed to read and write
   :json string afp_ro: users and groups allowed to read only
   :json string afp_sharepw: password for the share
   :json string afp_dbpath: path to set database information
   :json boolean afp_adouble: enable automatic creation of .AppleDouble
   :json boolean afp_upriv: use AFP3 unix privileges
   :json boolean afp_mswindows: restrict filenames to charset used by Windows
   :json boolean afp_prodos: compatibility with Apple II clients
   :json boolean afp_nofileid: don't advertise createfileid, resolveid, deleteid calls
   :json boolean afp_diskdiscovery: allow other systems to discover this share as a disk for data, as a Time Machine backup volume or not at all
   :json boolean afp_nostat: don't stat volume path when enumerating volumes list
   :json boolean afp_nohex: disable :hex translations for anything except dot files
   :json boolean afp_nodev: always use 0 for device number
   :json boolean afp_cachecnid:  uses the ID information stored in AppleDouble V2 header files to reduce database load
   :json boolean afp_crlf: crlf translation for TEXT files
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/sharing/afp/(int:id)/

   Delete AFP share `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/sharing/afp/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error
