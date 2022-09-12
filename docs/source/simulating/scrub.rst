Creating a pool that takes some time to scrub
=============================================

This script can be used to set up a pool or pools that take a couple of minutes to be scrubbed. This can be used to
test various scrub-related middleware code.

Prerequisites: 16 GB pool(s) (single 32 GB disk in a stripe) with name starting with `scrub`.

.. code-block:: bash

    for pool in `zpool status | grep 'pool: scrub' | cut -f 4 -d ' '`; do zfs set checksum=sha256 $pool; done

    for pool in `zpool status | grep 'pool: scrub' | cut -f 4 -d ' '`; do zfs create -V 4g -o volblocksize=8k $pool/zvol8; zfs create -V 4g -o volblocksize=16k $pool/zvol16; zfs create -V 4g -o volblocksize=32k $pool/zvol32; zfs create -V 4g -o volblocksize=64k $pool/zvol64; done

    for pool in `zpool status | grep 'pool: scrub' | cut -f 4 -d ' '`; do echo $pool; sh -c 'dd if=/dev/urandom of=/dev/zvol/'$pool'/zvol8 &
    p1=$!
    dd if=/dev/urandom of=/dev/zvol/'$pool'/zvol16 &
    p2=$!
    dd if=/dev/urandom of=/dev/zvol/'$pool'/zvol32 &
    p3=$!
    dd if=/dev/urandom of=/dev/zvol/'$pool'/zvol64 &
    p4=$!;
    wait $p1; wait $p2; wait $p3; wait $p4'; done
