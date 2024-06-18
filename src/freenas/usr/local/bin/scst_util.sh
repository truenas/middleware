#!/bin/bash

force_close() {
	shopt -s nullglob
	for fc in /sys/kernel/scst_tgt/targets/iscsi/*/sessions/*/force_close ; do
		echo 1 > $fc &
	done
	wait
}

case "$1" in
    force-close)
        force_close
        rc=$?
        ;;
    *)
        echo "Usage: $0 {force-close}"
        exit 2
        ;;
esac

exit $rc

