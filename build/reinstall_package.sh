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
	local pkg_path=`ls -1 ${NANO_OBJ}/ports/packages/*/All/${package}-*.txz | head -1`
	local pkg_name=`basename ${pkg_path}`

	scp ${pkg_path} ${host}:/tmp/${pkg_name}
	ssh -t ${host} pkg add -f /tmp/${pkg_name}
	
	return $?
}

main "$@"
