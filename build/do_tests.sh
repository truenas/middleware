#!/bin/sh
#
# See README for up to date usage examples.
# vim: syntax=sh noexpandtab
#

umask 022
cd "$(dirname "$0")/.."
TOP="$(pwd)"

# Sub-dir for storing testing repo
TESTDIR="freenas-tests"

# Repo for testing scripts
TESTREPO="https://github.com/iXsystems/ix-tests.git"

# Let the test scripts know this is FreeNAS 9
export FREENASLEGACY="YES"

main()
{
	if [ ! -d "$TESTDIR" ] ; then
		git clone --depth=1 $TESTREPO $TESTDIR
	else
		cd ${TESTDIR}
		git pull	
	fi

	cd ${TOP}
	touch ${TESTDIR}/freenas/freenas.cfg
	chmod 755 ${TESTDIR}/freenas/freenas.cfg

	cd ${TESTDIR}/freenas/scripts
	./2.runtests.sh ${TOP}/objs
	return $?
}

main "$@"
