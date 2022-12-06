Avoiding "Host Key Verification Failed" error
=============================================

Working on TrueNAS, you'll often connect to local and remote VMs and also to real physical testing hardware that gets
its OS reinstalled (and, therefore, SSH host keys changed) over and over again, resulting in "Host Key Verification
Failed" error almost every time you connect somewhere. To resolve this, you can safely disable host key checking
for iX-hosted VMs and hardware, and also for you local VM IP address pool by adding these lines to your `~/.ssh/config`
file:

.. code-block:: text

    Host 10.*
        StrictHostKeyChecking no
        UserKnownHostsFile=/dev/null

    Host *.tn.ixsystems.net
        StrictHostKeyChecking no
        UserKnownHostsFile=/dev/null

    Host 192.168.0.2*  # Replace this with your VM IP address pool
        StrictHostKeyChecking no
        UserKnownHostsFile=/dev/null
