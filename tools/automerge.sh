#!/bin/sh
#
# A basic svn automerger tool.
#
# Copyright (c) 2011-2012 iXsystems, Inc., All rights reserved.
#
# NOTES:
# 1. It's highly advised to run this with lockf, similar to the following:
#
# /usr/bin/lockf -k -t 600 /build/automerge/freenas/.old_version \
#	/bin/sh /build/automerge/freenas/ix/tools/automerge.sh
#
#    Otherwise 2+ instances of this script can stomp over one another, which
#    will result in interesting issues based on how svn locking works.
# 2. You should not run this script on a tainted workspace as it will whack
#    files not checked into svn.
#
# XXX: this script is far from perfect. It's just a stopgap to avoid having
#      to manually merge files in svn.
#
# Garrett Cooper, November 2011

export PATH=/bin:/usr/bin:/usr/local/bin

set -eu

# A graceful means for doing SVN because we ran into issues pulling from SF
# svn from time to time (high latency, large potential for partial merges).
_do() {
	local ec log tries

	log=log.$$

	ec=1
	tries=5

	: > $log
	while [ $tries -gt 0 ]; do
		$* > $log 2>&1
		if awk '$1 == "C" || $2 == "C" { exit 1; }' $log; then
			break
		elif ! grep -q 'svn: E' $log; then
			ec=0
			break
		fi
		: $(( tries -= 1 ))
	done
	cat $log
	rm -f $log
	return $ec
}

clean_svn() {
	_do svn cleanup $parent_branch
	_do svn cleanup $child_branch
	_do svn revert -R $child_branch
	_do svn status $child_branch | awk '$1 == "?" && $2 !~ /FreeBSD/ && $2 !~ /obj\./ { print $2 }' | xargs rm -Rf
}

usage() {
	cat <<EOF
usage: ${0##*/} [-D] base-dir parent-branch child-branch
EOF
	exit 1
}

honor_do_not_merge=true

while getopts 'D' optch; do
	case "$optch" in
	D)
		honor_do_not_merge=false
		;;
	*)
		usage
		;;
	esac
done

shift $(( $OPTIND - 1 ))

if [ $# -ne 3 ]; then
	usage
fi
base_dir=$1
parent_branch=$2
child_branch=$3

cd $base_dir
# XXX: doesn't work like expected.
#lockf -k -t 1 .old_version true
old_version=$(cat .old_version)
clean_svn
_do svn up --non-interactive $child_branch $parent_branch
_do svnversion $parent_branch > .new_version
new_version=$(cat .new_version)

# A tricky way to ensure that this is indeed a valid number.
: $(( old_version += 0 ))
[ $old_version -gt 0 ]

if [ $new_version -eq $old_version ]; then
	echo "${0##*/}: INFO: New and old version are the same; nothing to do."
	exit 0
elif [ $new_version -lt $old_version ]; then
	echo "${0##*/}: ERROR: New version older than old version?!?!"
	exit 1
fi

set +e

failed_a_merge=false
i=$old_version
while [ $i -le $new_version ]; do
	_do svn log --incremental -r$i $parent_branch > revlog
	if [ $? -eq 0 -a -s revlog ]; then
		if $honor_do_not_merge && grep -q '^Do-Not-Merge: ' revlog; then
			echo "Not merging r$i"
		else
			failed_merge=false

			# svn is stupid. Exit codes people!
			_do svn merge -c $i --dry-run $parent_branch $child_branch > merge-log
			if awk '$1 == "C" || $2 == "C" { exit 1; }' merge-log; then
				failed_merge=true
			else
				_do svn merge --non-interactive -c $i $parent_branch $child_branch > merge-log
				j=0
				(
				 echo "Automerging change r$i from $parent_branch to $child_branch"
				 cat revlog
				) > commit
				while [ -n "$(_do svn status $child_branch | awk '$1 != "?"')" -a $j -lt 5 ]; do
					_do svn ci --non-interactive -F commit $child_branch
					: $(( j += 1 ))
				done
				clean_svn
				if [ $j -eq 5 ]; then
					failed_merge=true
				fi
				_do svn up --non-interactive $child_branch
			fi
			if $failed_merge; then
				echo "${0##*/}: WARNING: couldn't automerge r$i -->"
				cat merge-log
				failed_a_merge=true
			fi
			rm merge-log
		fi
	elif [ -s revlog ]; then
		echo "Failed to get log for r$i"
		cat revlog
	fi
	: $(( i += 1 ))
done
mv .new_version .old_version
if $failed_a_merge; then
	exit 1
else
	exit 0
fi
