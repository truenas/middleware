Jobs
----

Tasks that require significant time to execute or process a large amount of input or output are categorized as jobs.
Job execution can be time-consuming, but its progress can be monitored.

To monitor the progress of running jobs, subscribe to the `core.get_jobs event <api_events_core.get_jobs.html>`_.

When a new job is initiated through a JSON-RPC 2.0 API call, its ``message_ids`` field will include the ``id`` of the call.
Therefore, when starting a new job, the client should listen for the "added" event in the :doc:`core.get_jobs <api_methods_core.get_jobs>` subscription.
Additionally, the client should monitor "changed" events because a "changed" event with a new ``message_ids`` field value
may be emitted if a method call triggers a job that has already been scheduled.

Example of Calling a Job Method
###############################

The client initiates a method call:

.. code:: json

    {
        "jsonrpc": "2.0",
        "id": "6841f242-840a-11e6-a437-00e04d680384",
        "method": "filesystem.copy",
        "params": ["/mnt/tank/src", "/mnt/tank/dst"]
    }

The server responds with the newly added job (e.g. id 101):

.. code:: json

    {
        "jsonrpc": "2.0",
        "method": "collection_update",
        "params": {
            "msg": "added",
            "collection": "core.get_jobs",
            "fields": {
                "id": 101,
                "message_ids": ["6841f242-840a-11e6-a437-00e04d680384"],
                ...
            }
        }
    }

Then, it updates the progress:

.. code:: json

    {
        "jsonrpc": "2.0",
        "method": "collection_update",
        "params": {
            "msg": "changed",
            "collection": "core.get_jobs",
            "fields": {
                "id": 101,
                "progress": {
                    "percent": 50,
                    "description": "Copied 1000000 of 2000000 bytes"
                },
                ...
            }
        }
    }

Finally, it sends the method execution result as usual:

.. code:: json

    {
        "jsonrpc": "2.0",
        "id": "6841f242-840a-11e6-a437-00e04d680384",
        "result": true
    }

Query Job Status
################

Job status can be queried with the :doc:`core.get_jobs <api_methods_core.get_jobs>` method.

.. code-block:: json
    :caption: Request

    {
        "id": "d8e715be-6bc7-11e6-8c28-00e04d680384",
        "msg": "method",
        "method": "core.get_jobs",
        "params": [
            [["id", "=", 53]]
        ]
    }

.. code-block:: json
    :caption: Response

    {
        "id": "d8e715be-6bc7-11e6-8c28-00e04d680384",
        "msg": "result",
        "result": [
            {
                "id": 53,
                "method": "catalog.sync_all",
                "arguments": [],
                "logs_path": null,
                "logs_excerpt": null,
                "progress": {"percent": 100, "description": "Syncing TEST catalog", "extra": null},
                "result": null,
                "error": null,
                "exception": null,
                "exc_info": null,
                "state": "SUCCESS",
                "time_started": {"$date": 1571300596053},
                "time_finished": null
            }
        ]
    }

Uploading / Downloading Files
#############################

There are some jobs which require input or output as files which can
be uploaded or downloaded.

Downloading a File
******************

If a job gives a file as an output, this endpoint is to be used to download
the output file. See :doc:`core.download <api_methods_core.download>` for full API documentation.

.. code-block:: json
    :caption: Request

    {
        "id": "d8e715be-6bc7-11e6-8c28-00e04d680384",
        "msg": "method",
        "method": "core.download",
        "params": [
            "config.save",
            [
                {}
            ],
            "freenas-FreeNAS-11.3-MASTER-201910090828-20191017122016.db"
        ]
    }

.. code-block:: json
    :caption: Response

    {
        "id": "cdc8740a-336b-b0cd-b850-47568fe94223",
        "msg": "result",
        "result": [
            86,
            "/_download/86?auth_token=9WIqYg4jAYEOGQ4g319Bkr64Oj8CZk1VACfyN68M7hgjGTdeSSgZjSf5lJEshS8M"
        ]
    }

In the response, the first value "86" is the job ID for :doc:`config.save <api_methods_config.save>`. This can be used to query
the status of the job. The second value is a REST endpoint used to download the file.

The download endpoint has a special format:

`http://system_ip/_download/{job_id}?auth_token={token}`

:doc:`core.download <api_methods_core.download>` takes responsibility for providing the download URI with the ``job_id`` and ``token`` values.

`job_id` and `token` are parameters being passed.

`core.download` takes responsibility for providing the download URI with the `job_id` and `token` values.

Note:
1) Job output is not buffered, so execution would be blocked if a file download is not started.
2) File download must begin within 60 seconds or the job is canceled.
3) The file can only be downloaded once.

.. _uploading-files:

Uploading a File
****************

Files can be uploaded to jobs that accept input via the ``/_upload`` HTTP endpoint. Eligible job methods are described
as such on their corresponding doc pages. 

The upload endpoint only accepts HTTP POST requests with ``multipart/form-data`` encoding.

1. Make an HTTP POST request to ``http://system_ip/_upload`` with form data
2. Receive a response containing the job ID
3. Monitor job progress using :doc:`core.get_jobs <api_methods_core.get_jobs>` if needed
4. Wait for job completion to get the final result

Form data parameters:

- ``data``: JSON-encoded object specifying the method to call and its parameters. This must be the first
  form field. Format:

    .. code:: json
        {
            "method": "config.upload",
            "params": []
        }

- ``file``: The file to upload. Can be specified multiple times to upload multiple files if the job
  supports it.

Example using curl:

.. code-block:: console
    :caption: Request

    curl -X POST -u root:freenas \
         -H "Content-Type: multipart/form-data" \
         -F 'data={"method": "config.upload", "params": []}' \
         -F "file=@/home/user/Desktop/config.db" \
         http://system_ip/_upload/

.. code-block:: json
    :caption: Response

    {
        "job_id": 20
    }

After receiving the job ID, you can monitor the job's progress and retrieve its result using :doc:`core.get_jobs <api_methods_core.get_jobs>`
or :doc:`core.job_wait <api_methods_core.job_wait>`.
