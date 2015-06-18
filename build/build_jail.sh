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
. build/repos.sh

. build/nanobsd/nanobsd_funcs.sh

if freenas_legacy_build
then
	MTREE_CMD="/usr/sbin/mtree-9"
	export MTREE_CMD
fi

setup_and_export_internal_variables

# File descriptor 3 is used for logging output, see pprint
exec 3>&1

NANO_STARTTIME=`date +%s`
pprint 1 "NanoBSD image ${NANO_NAME} build starting"

trap on_exit EXIT

# Number of jobs to pass to make. Only applies to src so far.
MAKE_JOBS=$(( 2 * $(sysctl -n kern.smp.cpus) + 1 ))
if [ ${MAKE_JOBS} -gt 10 ]; then
        MAKE_JOBS=10
fi
export MAKE_JOBS

NANO_PMAKE="${NANO_PMAKE} -j ${MAKE_JOBS}"

mkdir -p ${MAKEOBJDIRPREFIX}
printenv > ${MAKEOBJDIRPREFIX}/_.env
make_conf_build
build_world
build_kernel

# Override NANO_WORLDDIR, so that we create
# the jail for building ports in a different
# place from the directory used for creating
# the final package.
NANO_WORLDDIR=${NANO_OBJ}/_.j
rm -fr ${NANO_WORLDDIR}
mkdir -p ${NANO_OBJ} ${NANO_WORLDDIR}
printenv > ${NANO_OBJ}/_.env
make_conf_install
install_world LOG=_.ij
install_etc LOG=_.etcj
setup_nanobsd_etc
install_kernel LOG=_.ikj

mkdir -p ${NANO_WORLDDIR}/wrkdirs
if freenas_legacy_build
then
	update_version_env "${FREEBSD_RELEASE_VERSION}"
fi
