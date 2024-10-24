#!/bin/bash

force_close() {
	shopt -s nullglob
	for fc in /sys/kernel/scst_tgt/targets/{iscsi,qla2x00t}/*/sessions/*/force_close ; do
		echo 1 > $fc &
	done
	wait
}

stop_alua() {
	shopt -s nullglob

	# Disable iSCSI
	if [ -f /sys/kernel/scst_tgt/targets/iscsi/enabled ]; then
		echo 0 > /sys/kernel/scst_tgt/targets/iscsi/enabled
	fi

	# Disable Fibre Channel (in parallel)
	for fc_e in /sys/kernel/scst_tgt/targets/qla2x00t/*/enabled ; do
		echo 0 > "$fc_e" &
	done
	wait

	# Turn off any cluster_mode in parallel
	for cm in /sys/kernel/scst_tgt/devices/*/cluster_mode ; do
		echo 0 > "$cm" &
	done
	wait
}

case "$1" in
    force-close)
        force_close
        rc=$?
        ;;
    stop-alua)
        stop_alua
        rc=$?
        ;;
    *)
        echo "Usage: $0 {force-close|stop-alua}"
        exit 2
        ;;
esac

exit $rc

