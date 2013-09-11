=========
Storage
=========

Resources related to storage.

Volume
----------

The Volume resource represents ZFS pools and UFS volumes.

List resource
+++++++++++++

.. http:get:: /api/v1.0/storage/volume/

   Returns a list of all interfaces.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/storage/volume/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "status": "HEALTHY",
                "vol_guid": "8443409799014097611",
                "vol_fstype": "ZFS",
                "used": "192.0 KiB (0%)",
                "name": "tank",
                "used_pct": "0%",
                "used_si": "192.0 KiB",
                "id": 1,
                "vol_encryptkey": "",
                "vol_name": "tank",
                "is_decrypted": true,
                "avail_si": "4.9 GiB",
                "mountpoint": "/mnt/tank",
                "vol_encrypt": 0,
                "children": [],
                "total_si": "4.9 GiB"
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/storage/volume/

   Creates a new volume and returns the new volume object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/storage/volume/ HTTP/1.1
      Content-Type: application/json

        {
                "volume_name": "tank",
                "layout": [
                        {
                                "vdevtype": "stripe",
                                "disks": ["ada1", "ada2"]
                        }
                ]
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "status": "HEALTHY",
                "vol_guid": "8443409799014097611",
                "vol_fstype": "ZFS",
                "used": "192.0 KiB (0%)",
                "name": "tank",
                "used_pct": "0%",
                "used_si": "192.0 KiB",
                "id": 1,
                "vol_encryptkey": "",
                "vol_name": "tank",
                "is_decrypted": true,
                "avail_si": "4.9 GiB",
                "mountpoint": "/mnt/tank",
                "vol_encrypt": 0,
                "children": [],
                "total_si": "4.9 GiB"
        }

   :json string volume_name: name of the volume
   :json list layout: list of vdevs composed of "vdevtype" (stripe, mirror, raidz, raidz2, raidz3) and disks (list of disk names)
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/storage/volume/(int:id)/

   Delete volume `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/storage/volume/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error
