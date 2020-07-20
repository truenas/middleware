#!/bin/sh

. /usr/local/share/system_info

VMCORE_FILE=/proc/vmcore
KDUMP_SCRIPT=/usr/sbin/kdump-config
KDUMP_DEFAULTS=/etc/default/kdump-tools
[ -r $KDUMP_DEFAULTS ] && . $KDUMP_DEFAULTS

# If no vmcore file exists, system is just booting and we should load the crash kernel
if [ ! -e "$VMCORE_FILE" -o ! -s "$VMCORE_FILE" ]; then
  echo "Starting kdump-tools"
  $KDUMP_SCRIPT load
  exit 0
fi

sys_pool=$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
    SELECT
        sys_pool
    FROM
        system_systemdataset
    ORDER BY
        -id
    LIMIT 1
  ")

if [ -z "$sys_pool" ]; then
  echo "No system dataset pool found. Aborting dump."
  reboot -f
fi

zpool list | grep -q "$sys_pool"
if [ $? -eq 1 ]; then
  echo "Importing $sys_pool"
  zpool import "$sys_pool" || { echo "Importing pool failed. Aborting dump."; reboot -f; }
fi

cores_dataset="$sys_pool/.system/cores"
$(zfs list -r "$sys_pool" | grep -q "$cores_dataset") || { echo "$cores_dataset not found. Aborting dump."; reboot -f; }

# Mounting cores system dataset
echo "Mounting $cores_dataset dataset"
mkdir -p /var/crash
mount -t zfs "$cores_dataset" /var/crash

echo "Starting dump"
$KDUMP_SCRIPT savecore
if [ $? -ne 0 -a -n "$KDUMP_FAIL_CMD" ]; then
  $KDUMP_FAIL_CMD;
else
  date -R;
  reboot -f;
fi
