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
		"cat os-base/*/_.env" \
		"git status ." \
		"git diff" \
		"cd FreeBSD/src && git rev-parse HEAD" \
		"cd FreeBSD/src && git remote -v" \
		"cd FreeBSD/src && git status" \
		"cd FreeBSD/src && git diff HEAD" \
		; \
	do
		do_cmd "$cmd"
	done
) | bzip2 -c > $log 2>&1
info "Done! Please create a support ticket [at $AVATAR_SUPPORT_SITE], attach $log (in addition to any other failed build logs as noted by nanobsd, etc), and note that the issue is a build system issue."
