=========
System
=========

Resources related to system.

CronJob
----------

The CronJob resource represents cron(8) to execute scheduled commands.

List resource
+++++++++++++

.. http:get:: /api/v1.0/system/cronjob/

   Returns a list of all cronjobs.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/system/cronjob/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "cron_command": "touch /tmp/xx",
                "cron_daymonth": "*",
                "cron_dayweek": "*",
                "cron_description": "",
                "cron_enabled": true,
                "cron_hour": "*",
                "cron_minute": "*",
                "cron_month": "1,2,3,4,6,7,8,9,10,11,12",
                "cron_stderr": false,
                "cron_stdout": true,
                "cron_user": "root",
                "id": 1
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/system/cronjob/

   Creates a new cronjob and returns the new cronjob object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/system/cronjob/ HTTP/1.1
      Content-Type: application/json

        {
                "cron_user": "root",
                "cron_command": "/data/myscript.sh",
                "cron_minute": "*/20",
                "cron_hour": "*",
                "cron_daymonth": "*",
                "cron_month": "*",
                "cron_dayweek": "*",
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "cron_command": "/data/myscript.sh",
                "cron_daymonth": "*",
                "cron_dayweek": "*",
                "cron_description": "",
                "cron_enabled": true,
                "cron_hour": "*",
                "cron_minute": "*/20",
                "cron_month": "*",
                "cron_stderr": false,
                "cron_stdout": true,
                "cron_user": "root",
                "id": 2
        }

   :json string cron_command: command to execute
   :json string cron_daymonth: days of the month to run
   :json string cron_dayweek: days of the week to run
   :json string cron_description: description of the job
   :json boolean cron_enabled: job enabled?
   :json string cron_hour: hours to run
   :json string cron_minute: minutes to run
   :json string cron_month: months to run
   :json string cron_user: user to run
   :json boolean cron_stderr: redirect stderr to /dev/null
   :json boolean cron_stdout: redirect stdout to /dev/null
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/system/cronjob/(int:id)/

   Update cronjob `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/system/cronjob/2/ HTTP/1.1
      Content-Type: application/json

        {
                "cron_enabled": false,
                "cron_stderr": true
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "cron_command": "/data/myscript.sh",
                "cron_daymonth": "*",
                "cron_dayweek": "*",
                "cron_description": "",
                "cron_enabled": false,
                "cron_hour": "*",
                "cron_minute": "*/20",
                "cron_month": "*",
                "cron_stderr": true,
                "cron_stdout": true,
                "cron_user": "root",
                "id": 2
        }

   :json string cron_command: command to execute
   :json string cron_daymonth: days of the month to run
   :json string cron_dayweek: days of the week to run
   :json string cron_description: description of the job
   :json boolean cron_enabled: job enabled?
   :json string cron_hour: hours to run
   :json string cron_minute: minutes to run
   :json string cron_month: months to run
   :json string cron_user: user to run
   :json boolean cron_stderr: redirect stderr to /dev/null
   :json boolean cron_stdout: redirect stdout to /dev/null
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/system/cronjob/(int:id)/

   Delete cronjob `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/system/cronjob/2/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error
