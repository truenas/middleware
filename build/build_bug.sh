#!/bin/sh

do_cmd()
{
	echo "*********************** BEGIN $* ***********************"
	$*
	echo "*********************** END $* ***********************"
}

cd "$(dirname $0)/.."
. build/nano_env
. build/functions.sh

log="build_bug.$$.log.bz2"

info "grabbing build environment information; please wait.."
(
	for cmd in \
		"uname -a" \
		"set" \
		"cat obj.*/_.env" \
		"svn status ." \
		"svnversion FreeBSD/src" \
		"svn info FreeBSD/src" \
		"svn status FreeBSD/src" \
		"svn diff FreeBSD/src" \
		"cat patches/ports*.patch" \
		; \
	do
		do_cmd "$cmd"
	done
	# See: build/nano_env .
	if [ -z "$git" ]; then
		do_cmd "svn diff ."
	else
		do_cmd "git diff ."
	fi
) | bzip2 -c > $log 2>&1
info "Done! Please create a support ticket [at $AVATAR_SUPPORT_SITE], attach $log (in addition to any other failed build logs as noted by nanobsd, etc), and note that the issue is a build system issue."
