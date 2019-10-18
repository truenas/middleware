## Jobs

Tasks which require significant time to execute or process significant volume 
of input or output are tagged as jobs.
When client connects to an endpoint marked as a job, he/she receives a job id
from the end point. With this job id, the client can query the status of the job
to see the progress and status of job. If any errors arise, they are reflected
in the output, else the output reflects the result being returned by the end point
on it's completion.

e.g. `ws://freenas.domain/websocket`

### Example of connecting to end point marked as a job

#### Client connects to websocket endpoint and sends a `connect` message.

    :::javascript
    {
        "id": "6841f242-840a-11e6-a437-00e04d680384",
        "msg": "method",
        "method": "jail.start",
        "params": ["jail_name"]
    }

#### Server answers with `job_id`.

    :::javascript
    {
      "msg": "result",
      "id": "c0bb5952-fc60-232a-3d6c-a47961b771a5",
      "result": 53
    }

### Query Job Status

Job status can be queried with `core.get_jobs` method.

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
      "result": [{'id': 53, 'method': 'jail.start', 'arguments': ['abc'], 'logs_path': None, 'logs_excerpt': None, 'progress': {'percent': None, 'description': None, 'extra': None}, 'result': True, 'error': None, 'exception': None, 'exc_info': None, 'state': 'SUCCESS', 'time_started': {"$date": 1571300596053}, 'time_finished': null}]
    }

### Uploading / Downloading Files

There are some jobs which require input / output in the form of files which can
be uploaded / downloaded.

#### Downloading a File

If a job gives a file as an output, following end point is to be used to download
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
 
In the response, first value `86` is the job id for `config.save`. If we want to query the
status of the job, we can do so with this. Second value is a REST endpoint which will be used
to download the file.
 
Download end point is special, it's format is the following:

`http://system_ip/_download/{job_id}?auth_token={token}`

Where `job_id` and `token` and parameters being passed.

`core.download` takes responsibility for providing the download URI with `job_id` and `token` values.

It should be noted that:
1) Job output is not buffered so it's execution would be blocked if file download is not started.
2) File download should be initiated within 60 seconds otherwise job would be canceled.
3) File can only be downloaded once

#### Uploading a File

Files can be uploaded via HTTP POST request only. The upload endpoint is:

`http://system_ip/_upload`

It expects 2 values as form data, `data` and `file`.

`data` is JSON encoded data and it must be the first parameter provided following the format below

    ::: json
    {
        "method": "config.upload",
        "params": []
    }

`file` is the file URI in the form data which reflects the file which will be downloaded.

Following is an example with `curl`,

Request:

    curl -X POST -u root:freenas -H "Content-Type: multipart/form-data" -F 'data={"method": "config.upload", "params": []}' -F "file=@/home/user/Desktop/config" http://system_ip/_upload/
 
 Response:
 
    {"job_id": 20}
