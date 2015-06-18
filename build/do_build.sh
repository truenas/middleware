#!/bin/sh
#
# See README for up to date usage examples.
# vim: syntax=sh noexpandtab
#

umask 022
cd "$(dirname "$0")/.."
TOP="$(pwd)"

. build/nano_env
. build/functions.sh

# Number of jobs to pass to make. Only applies to src so far.
MAKE_JOBS=$(( 2 * $(sysctl -n kern.smp.cpus) + 1 ))
if [ ${MAKE_JOBS} -gt 10 ]; then
	MAKE_JOBS=10
fi
export MAKE_JOBS

# Trace flags
TRACE=""

main()
{
	local _nanobsd="${AVATAR_ROOT}/build/nanobsd/nanobsd.sh"

	if freenas_legacy_build
	then
		MTREE_CMD=/usr/sbin/mtree-9
		export MTREE_CMD
	fi

	local _cmd="${_nanobsd} -c ${NANO_CFG_BASE}/${AVATAR_COMPONENT} ${NANO_ARGS} -w -k -j ${MAKE_JOBS}"
	echo ${_cmd}

	if sh ${TRACE} ${_cmd}
	then
		echo "${NANO_LABEL} ${_target} build PASSED"
	else
		error "${NANO_LABEL} ${_target} build FAILED; please check above log for more details"
	fi
	
	return $?
}

main "$@"
