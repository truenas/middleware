## Jobs

Tasks which require significant time to execute or process a significant amount 
of input or output are tagged as jobs.
When a client connects to an endpoint marked as a job, they receive a job id
from the endpoint. With this job id, the client can query the status of the job
to see the progress and status. Errors are shown
in the output, or the output contains the result returned by the endpoint on completion.

e.g. `ws://truenas.domain/websocket`

### Example of connecting to endpoint marked as a job

#### Client connects to websocket endpoint and sends a `connect` message.

    :::javascript
    {
        "id": "6841f242-840a-11e6-a437-00e04d680384",
        "msg": "method",
        "method": "catalog.sync_all",
        "params": []
    }

#### Server answers with `job_id`.

    :::javascript
    {
      "msg": "result",
      "id": "c0bb5952-fc60-232a-3d6c-a47961b771a5",
      "result": 53
    }

### Query Job Status

Job status can be queried with the `core.get_jobs` method.

Request:

    :::javascript
    {
      "id": "d8e715be-6bc7-11e6-8c28-00e04d680384",
      "msg": "method",
      "method": "core.get_jobs",
      "params": [[["id", "=", 53]]]
    }

Response:

    :::javascript
    {
      "id": "d8e715be-6bc7-11e6-8c28-00e04d680384",
      "msg": "result",
      "result": [{"id": 53, "method": "catalog.sync_all", "arguments": [], "logs_path": null, "logs_excerpt": null, "progress": {"percent": 100, "description": "Syncing TEST catalog", "extra": null}, "result": null, "error": null, "exception": null, "exc_info": null, "state": "SUCCESS", "time_started": {"$date": 1571300596053}, "time_finished": null}]
    }

### Uploading / Downloading Files

There are some jobs which require input or output as files which can
be uploaded or downloaded.

#### Downloading a File

If a job gives a file as an output, this endpoint is to be used to download
the output file.

Request:

    :::javascript
    {
        "id": "d8e715be-6bc7-11e6-8c28-00e04d680384",
        "msg": "method",
        "method": "core.download",
        "params": ["config.save", [{}], "freenas-FreeNAS-11.3-MASTER-201910090828-20191017122016.db"]
    }

Response:

    :::javascript
    {
        "id": "cdc8740a-336b-b0cd-b850-47568fe94223",
        "msg": "result",
        "result": [86, "/_download/86?auth_token=9WIqYg4jAYEOGQ4g319Bkr64Oj8CZk1VACfyN68M7hgjGTdeSSgZjSf5lJEshS8M"]
    }
 
In the response, the first value `86` is the job id for `config.save`. This can be used to query
the status of the job. The second value is a REST endpoint used to download the file.
 
The download endpoint has a special format:

`http://system_ip/_download/{job_id}?auth_token={token}`

`job_id` and `token` are parameters being passed.

`core.download` takes responsibility for providing the download URI with the `job_id` and `token` values.

Note:
1) Job output is not buffered, so execution would be blocked if a file download is not started.
2) File download must begin within 60 seconds or the job is canceled.
3) The file can only be downloaded once.

#### Uploading a File

Files can be uploaded via HTTP POST request only. The upload endpoint is:

`http://system_ip/_upload`

It expects two values as form data, `data` and `file`.

`data` is JSON-encoded data. It must be the first parameter provided and in this format:

    ::: json
    {
        "method": "config.upload",
        "params": []
    }

`file` is the URI of the file to download.

This example uses `curl`,

Request:

    curl -X POST -u root:freenas -H "Content-Type: multipart/form-data" -F 'data={"method": "config.upload", "params": []}' -F "file=@/home/user/Desktop/config" http://system_ip/_upload/
 
 Response:
 
    {"job_id": 20}
