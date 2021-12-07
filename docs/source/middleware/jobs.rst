Jobs
####

.. contents:: Table of Contents
    :depth: 4

Jobs are middleware methods that might run for a long amount of time. This implies a certain infrastructure: we can
obtain a list of currently running jobs, jobs can report their completion progress...

Defining a job method
*********************

Methods that must be jobs should be wrapped with a `@job` decorator:

.. automodule:: middlewared.service
   :members: job,

Performing a job
****************

Using the job object
====================

Inside a job method, a `job` object is available:

.. autoclass:: middlewared.job.Job
   :members: pipes, logs_fd, check_pipe, set_description, set_progress, wrap

Using the pipes in the job object
=================================

.. automodule:: middlewared.pipe
    :members: Pipes

.. automodule:: middlewared.pipe
    :members: Pipe
    :noindex:

Calling a job
*************

From midclt
===========

Calling a job method will immediately print its job ID and exit. To wait for a job to complete (and observe its progress
meanwhile) use `-job` parameter. At the end the job return value will be printed:

.. code-block:: text

    root@truenas[~]# midclt call -job core.job_test '{"sleep": 5}'
    Status: (none)
    Total Progress: [########################################] 100.00%
    True

From another middleware method
==============================

Calling a job method will immediately return its job ID.

To wait for a job to complete and get its result use `wait`/`wait_sync`:

.. code-block:: python

    test_job = await self.middleware.call("core.job_test")
    result = await add_spn_job.wait(raise_error=True)

.. code-block:: python

    test_job = self.middleware.call_sync("core.job_test")
    result = test_job.wait_sync(raise_error=True)

This should only be done within another job (there is no such requirement though).

Use :meth:`middlewared.job.Job.wrap` to wait for a job and copy its progress report to the one of the current job

.. code-block:: python

    test_job = await self.middleware.call("core.job_test")
    result = await job.wrap(test_job)

Using the pipes when calling a job
----------------------------------

It is the caller's responsibility to open all the job's pipes. Pipes are passed in the :class:`middlewared.pipe.Pipes`
object. The typical syntax for starting a job with a pipe is:

.. code-block:: python

    job = await self.middleware.call('plugin.method', pipes=Pipes(output=self.middleware.pipe()))

.. automethod:: middlewared.main.Middleware.pipe

From the REST API
=================

Using the pipes with the REST API
---------------------------------

Uploading a file to the job's `input` pipe
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can upload a file to the job's `input` pipe using `/_upload` API endpoint.

`data` must be the first part of the multipart request.

.. code-block:: bash

    curl localhost/_upload \
        -u root:abcd1234 \
        -F 'data={"method": "config.upload", "params": []}' \
        -F 'file=@config.tar'

    {"job_id": 4501}

Downloading the job's `output` pipe
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`core.download` API method allows to launch a job with specified parameters and get a download URL (with a specified
file name) for its `output` pipe. Both unbuffered and buffered read are supported; in the latter case it's the caller's
responsibility to wait for the job to complete first.

.. code-block:: bash

    wget --content-disposition "localhost"$(midclt call \
        core.download system.debug '[]' 'debug.txz' | cut -d '"' -f 2)
