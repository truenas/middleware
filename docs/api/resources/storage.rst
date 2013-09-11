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



Task
----------

The Task resource represents Periodic Snapshot Tasks for ZFS Volumes.

List resource
+++++++++++++

.. http:get:: /api/v1.0/storage/task/

   Returns a list of all periodic snapshot tasks.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/storage/task/ HTTP/1.1
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

.. http:post:: /api/v1.0/storage/task/

   Creates a new Task and returns the new Task object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/storage/task/ HTTP/1.1
      Content-Type: application/json

        {
                "task_filesystem": "tank",
                "task_recursive": false,
                "task_ret_unit": "week",
                "task_interval": 60,
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "task_ret_count": 2,
                "task_repeat_unit": "weekly",
                "task_enabled": true,
                "task_recursive": false,
                "task_end": "18:00:00",
                "task_interval": 60,
                "task_byweekday": "1,2,3,4,5",
                "task_begin": "09:00:00",
                "task_filesystem": "tank",
                "id": 1,
                "task_ret_unit": "week"
        }

   :json string task_repeat_unit: daily, weekly
   :json string task_begin: do not snapshot before
   :json string task_end: do not snapshot after
   :json string task_filesystem: name of the ZFS filesystem
   :json string task_ret_unit: hour, day, week, month, year
   :json string task_byweekday: days of week to snapshot, [1..7]
   :json integer task_interval: how much time has been passed between two snapshot attempts [5, 10, 15, 30, 60, 120, 180, 240, 360, 720, 1440, 10080]
   :json integer task_ret_count: snapshot lifetime value
   :json boolean task_enabled: enabled task
   :json boolean task_recursive: snapshot all children datasets recursively
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/storage/task/(int:id)/

   Update Task `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/storage/task/1/ HTTP/1.1
      Content-Type: application/json

        {
                "task_interval": 30
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "task_ret_count": 2,
                "task_repeat_unit": "weekly",
                "task_enabled": true,
                "task_recursive": false,
                "task_end": "18:00:00",
                "task_interval": 30,
                "task_byweekday": "1,2,3,4,5",
                "task_begin": "09:00:00",
                "task_filesystem": "tank",
                "id": 1,
                "task_ret_unit": "week"
        }

   :json string task_repeat_unit: daily, weekly
   :json string task_begin: do not snapshot before
   :json string task_end: do not snapshot after
   :json string task_filesystem: name of the ZFS filesystem
   :json string task_ret_unit: hour, day, week, month, year
   :json string task_byweekday: days of week to snapshot, [1..7]
   :json integer task_interval: how much time has been passed between two snapshot attempts [5, 10, 15, 30, 60, 120, 180, 240, 360, 720, 1440, 10080]
   :json integer task_ret_count: snapshot lifetime value
   :json boolean task_enabled: enabled task
   :json boolean task_recursive: snapshot all children datasets recursively
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/storage/task/(int:id)/

   Delete Task `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/storage/task/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error
