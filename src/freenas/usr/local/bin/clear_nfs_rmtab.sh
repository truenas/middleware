#!/usr/bin/bash

# Clear rmtab at boot before NFS start.
# Purpose: Avoid accumulation of stale NFSv3 client entries.
# See NAS-131762

system_ready=$(midclt call system.ready)
if [[ "False" == "${system_ready}" ]]; then
    midclt call nfs.clear_nfs3_rmtab
fi
