#!/bin/sh
#
# vim: syntax=sh noexpandtab
#

umask 022
cd "$(dirname "$0")/.."
TOP="$(pwd)"

. build/nano_env
. build/functions.sh

main()
{
	local host=$1
	local package=$2
	local pkg_paths=`ls -1 ${NANO_OBJ}/ports/packages/*/All/${package}*.txz`
	local pkg_names=""

	for p in ${pkg_paths}; do
		pkg_names="${pkg_names} /tmp/`basename $p`"
	done

	scp ${pkg_paths} ${host}:/tmp
	ssh -t ${host} pkg add -f ${pkg_names}
	
	return $?
}

main "$@"
