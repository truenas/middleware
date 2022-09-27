Development process
###################

.. contents:: Table of Contents
    :depth: 4

Middleware daemon is a software component that receives much of the attention in the TrueNAS development process. This
section gathers a number of tips that will help developers to work on middleware daemon more efficiently.

Substituting the middleware code in an already-built image
**********************************************************

All of the middleware python code is located in the system-wide python installation dist-packages directory. The easiest
way to substitute that code with a code from your local branch is to export your git sources root from your development
machine via NFS and then mount it directly into the TrueNAS VM. For example, if your middleware repo is checked out at
`/home/user/truenas/middleware`, then add `/home/user/truenas` to your `/etc/exports` file:

.. code-block:: text

    /home/user/truenas  192.168.0.0/24(rw,async,no_root_squash,no_subtree_check,anonuid=1000,anongid=1000)

and mount the middleware code on your NAS:

.. code-block:: bash

    mount 192.168.0.3:/home/user/truenas/middleware/src/middlewared/middlewared \
        /usr/lib/python3/dist-packages/middlewared

Starting the middleware on the console
**************************************

By default the middleware daemon outputs its logs to `/var/log/middlewared.log`. This is not ideal for development
purposes. You can redirect the middleware logs to your console. First, stop the system-wide middleware daemon.

.. code-block:: bash

    systemctl stop middlewared

Then start the middleware on your console:

.. code-block:: bash

    middlewared --log-handler=console --debug-level DEBUG

The logs will be printed on your console, and you will be able to stop the middleware by pressing Ctrl-C in order to
restart it after making the code changes.

The middleware started this way should behave equally to the middleware started by systemd on boot.
